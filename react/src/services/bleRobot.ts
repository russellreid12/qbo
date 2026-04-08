const ROBOT_SERVICE_UUID = '7f4b0001-0c56-4a58-9b20-52d2b4f35a01';
const ROBOT_COMMAND_CHARACTERISTIC_UUID = '7f4b0002-0c56-4a58-9b20-52d2b4f35a01';

export class BleRobotClient {
  private device: BluetoothDevice | null = null;
  private characteristic: BluetoothRemoteGATTCharacteristic | null = null;

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

    const gattServer = await this.device.gatt?.connect();
    if (!gattServer) {
      throw new Error('Failed to connect to robot GATT server.');
    }

    const service = await gattServer.getPrimaryService(ROBOT_SERVICE_UUID);
    this.characteristic = await service.getCharacteristic(ROBOT_COMMAND_CHARACTERISTIC_UUID);
  }

  isConnected(): boolean {
    return Boolean(this.device?.gatt?.connected && this.characteristic);
  }

  async disconnect(): Promise<void> {
    this.device?.gatt?.disconnect();
    this.characteristic = null;
  }

  async sendCommand(command: string): Promise<void> {
    if (!this.characteristic || !this.device?.gatt?.connected) {
      throw new Error('Robot is not connected.');
    }

    const payload = new TextEncoder().encode(command.trim());
    if (payload.byteLength === 0) {
      throw new Error('Command is empty.');
    }

    await this.characteristic.writeValue(payload);
  }

  async startRecording(): Promise<void> {
    // Send the specialized commandREC_30 to trigger a 30s hardware-accelerated clip
    return this.sendCommand('REC_30');
  }
}

export const BLE_CONSTANTS = {
  ROBOT_SERVICE_UUID,
  ROBOT_COMMAND_CHARACTERISTIC_UUID,
};

// Singleton instance to persist connection state across React page navigations
export const globalBleClient = new BleRobotClient();
