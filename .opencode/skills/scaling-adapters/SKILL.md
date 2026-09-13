---
name: scaling-adapters
description: Úsala SOLO al añadir puertos/adaptadores, roles/permisos o integraciones externas (acciones del sistema, web/red) en Recognizer. Dispara con "adaptador", "puerto", "rol", "política", "FastAPI", "WebSocket", "escalar".
---

# Añadir un puerto/adaptador sin romper la escalabilidad

1. Define el `Protocol` en `core/ports/` con vocabulario del dominio (sin tipos de
   librerías externas).
2. Implementa el adaptador en `adapters/` (único lugar con `cv2`, `mediapipe`, `pynput`,
   `subprocess` o red).
3. Inyección por constructor; el wiring va en `bootstrap.py`/CLI (composition root).
4. Si entra una librería externa nueva, añade o ajusta el contrato de import-linter en
   `pyproject.toml` (`include_external_packages = true` ya está activo).
5. Tests: doble/fake del puerto en unitarios; integración marcada `@pytest.mark.integration`.
6. Patrones: aplica la regla de admisión de `docs/ARCHITECTURE.md`. Si el patrón no
   cumple (2+ implementaciones, aislar dependencia, o doble en tests), no se usa.
7. Roles/permisos futuros: `IdentityProvider` como puerto y `PolicyEngine` como Strategy en
   core; el MVP usa `AllowAllIdentity`/`AllowAllPolicy`. El core jamás se condiciona a una
   identidad concreta.
8. Web futura: el servidor será otro adaptador (`FrameSource` por WebSocket/WebRTC,
   `ActionSink` remoto) sobre el mismo core. Ver `docs/WEB-PLAN.md`.
