import { GestureDisplay } from './GestureDisplay.jsx';

export function CameraPanel({
  videoRef,
  canvasRef,
  devices,
  deviceId,
  onSelectDevice,
  cameraStatus,
  cameraError,
  onRequestCamera,
  gesture,
}) {
  const ready = cameraStatus === 'ready';
  const message =
    cameraStatus === 'denied' || cameraStatus === 'error'
      ? cameraError
      : 'Activa la cámara para empezar a usar los gestos.';

  return (
    <section className="panel">
      <h2>Cámara</h2>
      <div className="camera-container">
        <video ref={videoRef} autoPlay playsInline muted />
        <canvas ref={canvasRef} />
        {!ready && (
          <div className="camera-placeholder">
            <div>
              <p>{message}</p>
              <button type="button" className="btn btn-primary" onClick={onRequestCamera}>
                Activar cámara
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="controls">
        <select
          value={deviceId ?? ''}
          onChange={(event) => onSelectDevice(event.target.value)}
          disabled={devices.length === 0}
        >
          {devices.length === 0 && <option value="">Sin cámaras</option>}
          {devices.map((device, index) => (
            <option key={device.deviceId || index} value={device.deviceId}>
              {device.label || `Cámara ${index + 1}`}
            </option>
          ))}
        </select>
      </div>

      <GestureDisplay gesture={gesture} />
    </section>
  );
}
