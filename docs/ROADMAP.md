# Roadmap de apps — Recognizer

Orden acordado con el usuario (2026-09-20): primero las implementadas, luego
las fáciles sin entrenamiento (etapas próximas), luego las intermedias, OCR
para el final y las que requieren entrenamiento con menor prioridad. La
prioridad va de la mano con la facilidad de implementación.

Fuente de verdad del orden en el menú: `DEFAULT_APPS` en
`src/recognizer/core/domain/app.py`.

## 1. Implementadas (menú, disponibles)

| # | App | Id | Estado |
|---|---|---|---|
| 1 | Reconocimiento de gestos | `gestures` | implementada |
| 2 | Contador de personas | `people_counter` | implementada |
| 3 | Anti-intrusos | `anti_intruder` | implementada |
| 4 | Postura ergonómica | `posture` | implementada |
| 5 | Reconocimiento facial | `face_auth` | implementada (enrolamiento) |
| 6 | Manos arriba / asistencia | `assistance` | implementada |
| 7 | Conteo de autos | `vehicle_counter` | implementada |
| 8 | Desenfoque privacidad | `privacy_blur` | implementada |

## 2. Fáciles — sin entrenamiento (etapas próximas)

| # | App | Id | Modelo pre-entrenado |
|---|---|---|---|
| 9 | Zona permanencia | `loitering` | `yolo26n.pt` + track (dwell por `track_id`) |

## 3. Intermedias — sin entrenamiento

| # | App | Id | Modelo pre-entrenado |
|---|---|---|---|
| 10 | Detector de caídas | `fall_detector` | `yolo26n-pose.pt` (aspecto + centro bajo + quietud) |
| 11 | Edad y género | `gender_age` | `buffalo_s` módulo `genderage` |
| 12 | Somnolencia | `drowsiness` | landmarks faciales / pose (EAR + MAR + cabeceo) |

## 4. Final — sin entrenamiento, dependencia nueva

| # | App | Id | Nota |
|---|---|---|---|
| 13 | OCR en vivo | `ocr_reader` | RapidOCR/EasyOCR CPU sobre ROI de YOLO; etapa propia |

## 5. Menor prioridad — requieren entrenamiento

| # | App | Id | Nota |
|---|---|---|---|
| 14 | Detector EPP (obra) | `ppe_detector` | dataset `construction-ppe` + fine-tune `yolo26n.pt` |
| 15 | Inventario por cámara | `inventory` | dataset propio + persistencia (`Repository`) |

## Reglas

- Una sola vía de inferencia por app; carga perezosa; `ESC`/`q` vuelve al menú.
- Viewer: `gestures`, `posture`. Operator: todo lo sin entrenamiento.
  Admin: todo (incluye EPP e inventario).
