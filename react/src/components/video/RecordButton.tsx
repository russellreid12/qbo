import { useState, useEffect } from 'react';
import { BleRobotClient } from '../../services/bleRobot';

interface RecordButtonProps {
  bleClient: BleRobotClient;
}

export function RecordButton({ bleClient }: RecordButtonProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [countdown, setCountdown] = useState(10);

  const handleRecord = async () => {
    if (!bleClient.isConnected()) {
      alert('Please connect to the robot first.');
      return;
    }

    try {
      await bleClient.startRecording();
      setIsRecording(true);
      setCountdown(10);
    } catch (error) {
      console.error('Failed to start recording:', error);
      alert('Failed to start recording. Check console for details.');
    }
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isRecording && countdown > 0) {
      interval = setInterval(() => {
        setCountdown((c) => c - 1);
      }, 1000);
    } else if (countdown === 0) {
      setIsRecording(false);
      setCountdown(10);
    }
    return () => clearInterval(interval);
  }, [isRecording, countdown]);

  return (
    <div className="record-control">
      <button 
        className={`btn ${isRecording ? 'danger' : 'primary'}`} 
        onClick={handleRecord} 
        disabled={isRecording}
        style={{ width: '100%', position: 'relative', overflow: 'hidden' }}
      >
        {isRecording ? (
          <>
            <span className="btn-label">Recording: {countdown}s</span>
            <div 
              className="btn-progress" 
              style={{ 
                position: 'absolute', 
                bottom: 0, 
                left: 0, 
                height: '4px', 
                background: 'rgba(255,255,255,0.4)',
                width: `${(countdown / 10) * 100}%`,
                transition: 'width 1s linear'
              }} 
            />
          </>
        ) : (
          'Record 10s Clip'
        )}
      </button>
      <p className="hint" style={{ marginTop: '8px', textAlign: 'center' }}>
        Triggers hardware-accelerated H.264 capture on the Pi.
      </p>
    </div>
  );
}
