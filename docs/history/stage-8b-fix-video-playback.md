# Etapa 8b — Fix: el video sigue reproduciéndose al volver al inicio

- **Rama:** stage/8b-fix-video-playback
- **Estado:** completada
- **Objetivo:** al volver el video al inicio con el script `video_start.ps1`, que siga
  reproduciéndose en lugar de quedar en pausa.

## Problema
El script hacía un clic en el centro del video para asegurar el foco; en YouTube ese clic
alterna play/pausa, así que el video saltaba a 0:00 pero quedaba pausado.

## Cambios
- `scripts/actions/video_start.ps1`: se elimina el clic de foco (causa de la pausa) y los
  helpers de ratón asociados; se pulsa `0` con la ventana al frente.
- Red de seguridad: tras el salto se consulta el estado de la sesión de media de Chrome
  (GSMTC) y, si quedó en `Paused`, se envía la tecla multimedia play/pausa para reanudar.

## Resultado
El video vuelve a 0:00 y continúa reproduciéndose. Verificación manual pendiente
(ver `docs/PENDING-TESTS.md`).

## Commits
_(pendiente)_
