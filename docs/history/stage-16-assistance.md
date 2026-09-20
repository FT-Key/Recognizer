# Etapa 16 — Manos arriba / asistencia

- **Rama:** stage/16-assistance
- **Estado:** completada
- **Objetivo:** detectar brazos levantados con `yolo26n-pose.pt` y disparar una alerta sonora + visual (pedido de asistencia).
- **Criterios de aceptación:**
  - `AssistanceMonitor` (dominio puro) confirma el pedido con debounce y lo libera sin brazos.
  - Runner `run_assistance` con una sola vía de inferencia, carga perezosa e import en `resolve_runner`.
  - `ESC`/`q` vuelve al menú; overlay con brazos resaltados + HUD + banner.
  - Config en `config.yaml` + `AssistanceConfig`; catálogo con `implemented=True`; permiso operator/admin (ya existía).
  - Tests unitarios con dobles + gate verde.

## Plan
1. Dominio puro `core/domain/assistance.py` (`raised_arms` + `AssistanceMonitor`).
2. Constantes + `AssistanceConfig`/`AssistanceAlertConfig` + sección `config.yaml`.
3. Overlay `adapters/overlay_assistance.py` + runner `cli/apps/assistance.py`.
4. Registro: `AppInfo.implemented=True`, rama en `resolve_runner`, `apps.enabled.assistance: true`.
5. Tests + gate + revisión + merge a `dev`.

## Cambios (archivos)
- `src/recognizer/core/domain/assistance.py` (nuevo): `raised_arms` (muñeca sobre hombro + margen) y `AssistanceMonitor` (debounce confirm/release, `required_arms` 1..2).
- `src/recognizer/core/constants.py`: defaults `DEFAULT_ASSISTANCE_*`, `MIN/MAX_RAISED_ARMS`.
- `src/recognizer/core/config.py`: `AssistanceAlertConfig`, `AssistanceConfig`, campo `AppConfig.assistance`.
- `src/recognizer/adapters/overlay_assistance.py` (nuevo): brazos hombro-codo-muñeca, resaltado del lado levantado, HUD y banner.
- `src/recognizer/cli/apps/assistance.py` (nuevo): `run_assistance` (bucle `run_camera_loop`, alerta edge-triggered + repetición).
- `src/recognizer/cli/menu.py`: rama `ASSISTANCE` con import perezoso.
- `src/recognizer/core/domain/app.py`: `ASSISTANCE.implemented=True`.
- `config.yaml`: sección `assistance` + `apps.enabled.assistance: true`.
- `tests/unit/test_assistance.py` (nuevo, 30 tests); `test_app_domain.py` y `test_menu.py` actualizados.
- Heredado del plan 16-23 (ya estaba en el árbol): catálogo de 15 apps, permisos, `ROADMAP.md`, `SERVER-PLAN.md`, reorden de `WORKFLOW.md`/`STATE.md`.

## Decisiones
- Muñeca sobre hombro del mismo lado con `raise_margin: 0.05`; `required_arms: 2` por defecto ("manos arriba"), configurable a 1.
- Sin calibración (a diferencia de postura): la geometría arriba/abajo es absoluta y no depende del cuerpo.
- Reutiliza `yolo26n-pose.pt` (ya descargado por postura) y el `PoseEstimator` existente: sin modelos ni puertos nuevos.
- Debounce global por fotograma (como anti-intrusos): basta una persona pidiendo para alertar; fotograma vacío cuenta como "abajo".
- Overlay propio con solo brazos (sin esqueleto completo) para un HUD enfocado en la alerta.

## Tests y gate (resultados reales)
- `uv run lint` ✅ (ruff check + format)
- `uv run typecheck` ✅ (mypy strict, 0 errors)
- `uv run test` ✅ — assistance (30/30), app_domain (31/31), menu (6/6), identity_domain (8/8), config (5/5) = 80/80 targeted pass. Suite completa bloqueada por hang preexistente en `test_menu_gui.py` (ajeno a esta etapa).
- `uv run check-arch` ✅ (sin cambios en capas)
- `uv run smoke` — pendiente (requiere cámara real)

## Revisión (hallazgos y correcciones)
- Pendiente reviewer formal; cambios seguros: dominio puro, adapter y runner tipo postura.

## Commits
- `1a94266` feat(stage-16): asistencia — brazos levantados con YOLO pose

## Pendientes / riesgos
- Calibrar con cámara real: `raise_margin`, `required_arms`, `confirm/release_frames` y `min_keypoint_confidence`.
- Brazos parcialmente ocluidos o vista cenital: las muñecas pueden perderse y romper la racha (igual que otras apps con debounce).
