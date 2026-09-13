# Plan web (futuro, etapa 5+)

No implementado todavía. Este documento fija la estrategia para no hipotecar el diseño.

## Objetivo
Permitir usar Recognizer de forma remota desde el navegador (la web envía frames y/o
recibe eventos) reutilizando el mismo núcleo, con roles y permisos.

## Estrategia
- El `core` ya es una librería sin dependencias de UI/SO: se reutiliza tal cual.
- Nuevo adaptador de entrada: `FrameSource` por WebSocket (JPEG) o WebRTC (video).
- Nuevo adaptador de salida: `ActionSink` remoto que reenvía acciones/eventos.
- Servidor: FastAPI + WebSocket. Los eventos del dominio son serializables a JSON.
- Identidad/roles: `IdentityProvider` + `PolicyEngine` (etapa 5) deciden quién puede
  ejecutar cada gesto; hoy existe la implementación `AllowAll`.

## Fases web
1. Endpoint de salud + streaming de eventos (solo observación).
2. Streaming de frames desde el navegador y reconocimiento en el servidor.
3. Autenticación, roles y permisos por gesto.
4. Despliegue (hosting, TLS, límites de ancho de banda).

## Riesgos
- Latencia y ancho de banda del video remoto.
- Privacidad: datos biométricos (rostro) y consentimiento; no subir embeddings a terceros.
- Permisos de cámara del navegador y contextos seguros (HTTPS).
