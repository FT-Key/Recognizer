/**
 * useCamera — gestiona getUserMedia, la lista de cámaras y el ciclo del stream.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { CONFIG } from '../lib/config.js';

export function useCamera(videoRef) {
  const streamRef = useRef(null);
  const [devices, setDevices] = useState([]);
  const [deviceId, setDeviceId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);

  const stop = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
    setStatus('idle');
  }, [videoRef]);

  const refreshDevices = useCallback(async () => {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices(all.filter((device) => device.kind === 'videoinput'));
    } catch (err) {
      setError(String(err?.message ?? err));
    }
  }, []);

  const start = useCallback(
    async (id) => {
      setStatus('requesting');
      setError(null);
      stop();
      const video = {
        facingMode: CONFIG.camera.facingMode,
        width: CONFIG.camera.width,
        height: CONFIG.camera.height,
      };
      const constraints = { video: id ? { deviceId: { exact: id } } : video, audio: false };
      try {
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setStatus('ready');
        await refreshDevices();
      } catch (err) {
        const denied = err?.name === 'NotAllowedError';
        setStatus(denied ? 'denied' : 'error');
        setError(
          denied
            ? 'Permiso de cámara denegado. Habilítalo en el navegador para usar los gestos.'
            : String(err?.message ?? err),
        );
      }
    },
    [refreshDevices, stop, videoRef],
  );

  useEffect(() => () => stop(), [stop]);

  return { devices, deviceId, setDeviceId, status, error, start, stop };
}
