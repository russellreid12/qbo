const ROBOT_SERVICE_UUID = '7f4b0001-0c56-4a58-9b20-52d2b4f35a01';
const ROBOT_COMMAND_CHARACTERISTIC_UUID = '7f4b0002-0c56-4a58-9b20-52d2b4f35a01';
const ROBOT_DATA_CHARACTERISTIC_UUID = '7f4b0004-0c56-4a58-9b20-52d2b4f35a01';

export interface ClipInfo {
  name: string;
  size: number; // bytes
}

export class BleRobotClient {
  private device: BluetoothDevice | null = null;
  private characteristic: BluetoothRemoteGATTCharacteristic | null = null;
  private dataCharacteristic: BluetoothRemoteGATTCharacteristic | null = null;
  private heartbeatInterval: any = null;
  private writeQueue: (() => Promise<void>)[] = [];
  private isWriting: boolean = false;

  // File transfer state
  private clipChunks: Map<number, Uint8Array> = new Map();
  private clipResolve: ((blob: Blob) => void) | null = null;
  private clipReject: ((err: Error) => void) | null = null;
  private clipOnProgress: ((pct: number) => void) | null = null;
  private clipExpectedSize: number = 0;
  private clipReceivedBytes: number = 0;
  private clipTimeout: any = null;

  // Clip list state
  private listResolve: ((clips: ClipInfo[]) => void) | null = null;
  private listReject: ((err: Error) => void) | null = null;
  private listTimeout: any = null;

  // ─── Queue ────────────────────────────────────────────────────────────────

  private async processQueue() {
    if (this.isWriting || this.writeQueue.length === 0) return;
    this.isWriting = true;
    try {
      const task = this.writeQueue.shift();
      if (task) await task();
    } finally {
      this.isWriting = false;
      this.processQueue();
    }
  }

  // ─── Public API ───────────────────────────────────────────────────────────

  static isSupported(): boolean {
    return typeof navigator !== 'undefined' && 'bluetooth' in navigator;
  }

  async connect(): Promise<void> {
    if (!BleRobotClient.isSupported()) {
      throw new Error('Web Bluetooth is not available in this browser.');
    }

    this.device = await navigator.bluetooth.requestDevice({
      filters: [{ services: [ROBOT_SERVICE_UUID] }],
      optionalServices: [ROBOT_SERVICE_UUID],
    });

    this.device.addEventListener('gattserverdisconnected', () => {
      console.warn('BLE disconnected — clearing heartbeat');
      this.stopHeartbeat();
    });

    const gattServer = await this.device.gatt?.connect();
    if (!gattServer) {
      throw new Error('Failed to connect to robot GATT server.');
    }

    const service = await gattServer.getPrimaryService(ROBOT_SERVICE_UUID);
    this.characteristic = await service.getCharacteristic(ROBOT_COMMAND_CHARACTERISTIC_UUID);

    // Subscribe to DATA characteristic for file transfers
    try {
      this.dataCharacteristic = await service.getCharacteristic(ROBOT_DATA_CHARACTERISTIC_UUID);
      await this.dataCharacteristic.startNotifications();
      this.dataCharacteristic.addEventListener(
        'characteristicvaluechanged',
        this.handleDataNotification.bind(this)
      );
      console.log('BLE DATA characteristic subscribed');
    } catch (e) {
      console.warn('DATA characteristic not available (restart BleCmdServer.py to get it):', e);
    }

    this.startHeartbeat();
  }

  isConnected(): boolean {
    return Boolean(this.device?.gatt?.connected && this.characteristic);
  }

  hasDataChannel(): boolean {
    return this.dataCharacteristic !== null;
  }

  async disconnect(): Promise<void> {
    this.stopHeartbeat();
    if (this.dataCharacteristic) {
      try { await this.dataCharacteristic.stopNotifications(); } catch {}
    }
    this.device?.gatt?.disconnect();
    this.characteristic = null;
    this.dataCharacteristic = null;
  }

  async sendCommand(command: string): Promise<void> {
    if (!this.characteristic || !this.device?.gatt?.connected) {
      throw new Error('Robot is not connected.');
    }

    const payload = new TextEncoder().encode(command.trim());
    if (payload.byteLength === 0) {
      throw new Error('Command is empty.');
    }

    return new Promise<void>((resolve, reject) => {
      this.writeQueue.push(async () => {
        try {
          if (!this.characteristic || !this.device?.gatt?.connected) {
            throw new Error('Robot is not connected.');
          }
          await this.characteristic.writeValue(payload);
          resolve();
        } catch (e) {
          reject(e);
        }
      });
      this.processQueue();
    });
  }

  async startRecording(): Promise<void> {
    return this.sendCommand('REC_10');
  }

  /** Fetch the list of recorded clips from the robot via BLE. */
  async listClips(): Promise<ClipInfo[]> {
    if (!this.isConnected()) throw new Error('Robot is not connected.');
    if (!this.dataCharacteristic) throw new Error('DATA channel not available. Restart BleCmdServer.py.');

    return new Promise<ClipInfo[]>((resolve, reject) => {
      this.listResolve = resolve;
      this.listReject = reject;
      this.listTimeout = setTimeout(() => {
        this.listResolve = null;
        this.listReject = null;
        reject(new Error('Clip list request timed out after 15s'));
      }, 15_000);
      this.sendCommand('LIST_CLIPS').catch(reject);
    });
  }

  /**
   * Download a clip from the robot via BLE.
   * @param filename  e.g. 'qbo_clip_20240409_123456.mp4'
   * @param size      file size in bytes (from listClips)
   * @param onProgress optional callback with 0-100 progress
   */
  async downloadClip(
    filename: string,
    size: number,
    onProgress?: (pct: number) => void
  ): Promise<Blob> {
    if (!this.isConnected()) throw new Error('Robot is not connected.');
    if (!this.dataCharacteristic) throw new Error('DATA channel not available. Restart BleCmdServer.py.');

    // Pause heartbeat so it doesn't interfere with the download
    this.stopHeartbeat();
    this._resetClipState();
    this.clipExpectedSize = size;
    this.clipOnProgress = onProgress ?? null;

    return new Promise<Blob>((resolve, reject) => {
      this.clipResolve = resolve;
      this.clipReject = reject;
      // 5-minute timeout ceiling
      this.clipTimeout = setTimeout(() => {
        reject(new Error('Download timed out after 5 minutes'));
        this._resetClipState();
        this.startHeartbeat();
      }, 5 * 60 * 1_000);

      this.sendCommand(`GET_CLIP:${filename}`).catch((e) => {
        reject(e);
        this._resetClipState();
        this.startHeartbeat();
      });
    });
  }

  // ─── Heartbeat ────────────────────────────────────────────────────────────

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(async () => {
      try {
        if (this.isConnected()) {
          await this.sendCommand('-c nose -co none');
        }
      } catch (e) {
        console.warn('BLE Heartbeat failed:', e);
      }
    }, 5000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  // ─── DATA characteristic notifications ────────────────────────────────────

  private handleDataNotification(event: Event) {
    const value = (event.target as BluetoothRemoteGATTCharacteristic).value;
    if (!value || value.byteLength === 0) return;

    // Decode to text first to detect control messages
    const text = new TextDecoder('utf-8', { fatal: false }).decode(value);

    if (text.startsWith('LIST:')) {
      if (this.listTimeout) clearTimeout(this.listTimeout);
      try {
        const clips: ClipInfo[] = JSON.parse(text.slice(5));
        this.listResolve?.(clips);
      } catch {
        this.listReject?.(new Error('Failed to parse clip list JSON'));
      } finally {
        this.listResolve = null;
        this.listReject = null;
      }
      return;
    }

    if (text === 'CLIP_END') {
      this._finalizeClip();
      return;
    }

    if (text.startsWith('CLIP_ERR:')) {
      if (this.clipTimeout) clearTimeout(this.clipTimeout);
      this.clipReject?.(new Error(text.slice(9)));
      this._resetClipState();
      this.startHeartbeat();
      return;
    }

    // Binary chunk: first 4 bytes = big-endian sequence number, rest = data
    if (value.byteLength > 4) {
      const dv = new DataView(value.buffer, value.byteOffset, value.byteLength);
      const seq = dv.getUint32(0, false); // big-endian
      const chunkData = new Uint8Array(
        value.buffer,
        value.byteOffset + 4,
        value.byteLength - 4
      );
      this.clipChunks.set(seq, chunkData.slice());
      this.clipReceivedBytes += chunkData.byteLength;
      if (this.clipExpectedSize > 0) {
        const pct = Math.min(99, Math.round((this.clipReceivedBytes / this.clipExpectedSize) * 100));
        this.clipOnProgress?.(pct);
      }
    }
  }

  private _finalizeClip() {
    if (this.clipTimeout) clearTimeout(this.clipTimeout);
    const keys = Array.from(this.clipChunks.keys()).sort((a, b) => a - b);
    const blob = new Blob(keys.map(k => this.clipChunks.get(k)!), { type: 'video/mp4' });
    this.clipOnProgress?.(100);
    this.clipResolve?.(blob);
    this._resetClipState();
    this.startHeartbeat();
  }

  private _resetClipState() {
    this.clipChunks.clear();
    this.clipResolve = null;
    this.clipReject = null;
    this.clipOnProgress = null;
    this.clipExpectedSize = 0;
    this.clipReceivedBytes = 0;
    if (this.clipTimeout) {
      clearTimeout(this.clipTimeout);
      this.clipTimeout = null;
    }
  }
}

export const BLE_CONSTANTS = {
  ROBOT_SERVICE_UUID,
  ROBOT_COMMAND_CHARACTERISTIC_UUID,
  ROBOT_DATA_CHARACTERISTIC_UUID,
};

// Singleton instance to persist connection state across React page navigations
export const globalBleClient = new BleRobotClient();
