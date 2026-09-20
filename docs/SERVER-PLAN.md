# Plan servidor central — facial multi-PC (etapas 15e/15f)

Documento vivo del plan acordado para llevar el login facial a N PCs de empresa
conectados por internet a un solo backend. Sin implementar aún; al ejecutar las
etapas 15e/15f este archivo es la especificación de partida.

## 1. Topología decidida

- **API central (FastAPI) + Postgres** como única fuente de verdad. PCs = clientes
  finos con cómputo en el borde. Sin modo offline: **fail-closed** (sin red o sin
  JWT válido no hay login; solo identidad invitada viewer).
- **FastAPI** porque el proyecto ya es Python 3.12 + Pydantic v2 y el contrato de
  import-linter veta `fastapi` en `core` (`pyproject.toml`): el servidor entra como
  adaptador sin tocar el dominio. Stack: `FastAPI + SQLAlchemy 2 + Alembic +
  pgvector + uvicorn`; cliente PC: `httpx`.
- **Entidades como tablas SQL** (mapeo directo, dominio intacto):
  - `EnrolledFace` → `faces(face_id PK, name, embedding vector(512), samples,
    created_at, role, preview_ref, password_hash, idempotency_key UNIQUE)`.
  - `SessionRecord` → `sessions(token_hash PK, face_id FK, device_id,
    authenticated_at, expires_at, revoked)`. Reemplaza `session.json`.
  - `AccessEvent` → `access_log(id, ts, face_id, device_id, method, success,
    distance)`. Reemplaza `logins.jsonl` por equipo.
  - Nueva `devices(device_id PK, site, revoked)` para revocar una PC robada.
  - Fotos fuera de la BD: `preview_ref` → URL de storage (Supabase Storage 1 GB
    gratis / Cloudinary / S3). No BLOBs (500 MB del tier gratis se llenan rápido).

## 2. Enrolamiento distribuido (cómputo en edge, verdad en centro)

Lo pesado se queda en cada PC (captura, guía, InsightFace `buffalo_s`,
`EnrollmentBuilder` + `mean_embedding`, foto, validación de clave); lo crítico va
al servidor en **una sola llamada** `POST /faces` con el embedding final (~2-8 KB)
+ 1 PNG. Sin contradicción: la PC propone, el servidor dispone.

- `Idempotency-Key: uuid7` generado en la PC al iniciar: reintentos seguros sin
  duplicar (`UNIQUE(idempotency_key)` como árbitro final).
- `face_id` desde `SEQUENCE` del servidor (formato `F-%04d`); se elimina el
  `next_id()` "máx+1" del cliente (`file_face_repository.py`), que tiene carreras.
- Hash PBKDF2 (600k it) **en el servidor**; la clave viaja una vez por TLS.
  `verify_password` + dummy anti-enumeración (`core/domain/credentials.py`) se
  reutilizan en servidor.
- `allowed_roles` / `PolicyEngine.can_enroll` se evalúan **en servidor dentro de la
  transacción**; el cliente solo sugiere. Carrera "primer admin": transacción con
  tabla singleton `bootstrap` (`UPDATE ... WHERE done=false RETURNING`); el
  perdedor recibe `403 first-admin-taken`.
- Chequeo duplicado biométrico server-side con `FaceMatcher` (core puro) antes del
  `INSERT`: `409 Conflict` si distancia < umbral (política abierta: rechazar o
  avisar — decidir en 15e).
- Monitor distribuido = Postgres (`SEQUENCE` atómica + `UNIQUE` + transacción);
  un `Lock` de Python solo sirve in-process y no cruza la red.

## 3. Login online-obligatorio

- Facial: la PC extrae el query embedding local y hace `POST /identify
  {embedding, device_id}`; el servidor compara cosenos (microsegundos) y responde
  match + JWT corto (según `session_timeout_seconds`).
- Clave (15d): `POST /login-password {name_or_id, password}` → verifica en
  servidor con rate-limit + bloqueo temporal; no distinguir "usuario no existe".
- `role` siempre re-validado en servidor; logout = revocar en `sessions`.
- Nuevos adaptadores sobre los mismos puertos (`FaceRepository`,
  `IdentityProvider`): `ApiFaceRepository`, `ApiIdentityProvider`, `ApiAccessLog`
  (skill `scaling-adapters`; core intacto).

## 4. Hosting $0 para experimentar (decidido: Render + Neon)

- **Vercel / Netlify: no para la API** (static + serverless, timeout 10-60 s, FS
  efímero). Solo valdrían para un panel web estático futuro.
- **API en Render free** (512 MB, 750 h/mes; duerme a los 15 min sin tráfico;
  un servicio siempre-despierto ≈ 720 h/mes, cabe justo).
- **DB en Neon free** (0.5 GB, 100 CU-h/mes, scale-to-zero a los 5 min,
  `CREATE EXTENSION vector` soportado, sin caducidad) o Supabase free (500 MB +
  storage, pausa a los 7 días). **No usar el Postgres gratis de Render** (expira y
  borra a los 30 días).
- Salida de gratis: VPS (Hetzner ~4-5 €/mes u Oracle Always Free) con
  `docker compose (api + postgres + pgvector)`; Render pago mínimo ≈ 13 USD/mes.

## 5. Endpoint especializado `/ready` + monitor cada 5 min (decisión registrada)

`/health` (liveness barato, **sin DB**) se conserva para el balanceador. El
keep-alive usa un endpoint aparte porque mantiene **servidor y DB**:

- `GET /ready` → readiness: `SELECT 1` con `statement_timeout` corto (+ chequeo de
  storage opcional). 200 solo si hay DB; payload mínimo (`{"status":"ok"}`), sin
  versiones ni detalles internos.
- Monitor externo → `/ready` **cada 5 min** (decisión del usuario; UptimeRobot /
  cron-job.org / GitHub Actions `schedule` con `curl`, costo $0).
- Advertencia registrada: ping cada 5 min mantiene Neon casi siempre despierto y
  puede agotar las ~100 CU-h/mes gratis (0.25 CU × 720 h ≈ 180 CU-h → suspendido
  hasta el mes siguiente). Mitigaciones si ocurre: subir `/ready` a cada 10 min
  (Render sigue despierto —sleep 15 min— y Neon duerme/despierta entre pings,
  ~0.5 s) o aceptar el ciclo sleep/wake en experimento. En producción (plan pago
  sin sleep) el monitor pasa a ser solo observabilidad.

## 6. Protección de `/ready` (obligatoria por ser endpoint caliente)

Un endpoint que despierta API+DB es objetivo de abuso por script (flood de
peticiones). Capas acordadas para 15e/15f:

1. **Secreto de monitor**: cabecera `X-Monitor-Token` (secreto en variable de
   entorno, rotatable); sin token válido → `401` **antes** de tocar la DB.
2. **Rate-limit por IP** (p. ej. `slowapi`: `/ready` máx ~12 req/min por IP con
   `429` + `Retry-After`); límites más duros en `/identify` y `/login-password`.
3. **Query barata y acotada**: solo `SELECT 1` con `statement_timeout` (1-2 s);
   sin joins, sin lectura de embeddings ni fotos.
4. **Sin fuga de información**: respuesta mínima, sin stack traces (manejador
   global → `503` genérico), `Cache-Control: no-store`, no indexar (robots).
5. **Observabilidad**: log de `401/429` en `/ready` con alerta (picos = posible
   abuso); métrica de latencia para distinguir flood de caída real.
6. **Endurecimiento futuro (15f)**: allowlist de IPs del monitor si es fija,
   WAF/Cloudflare delante, JWT con `jti` + lista de revocación, backups cifrados.

## 7. Etapas y aceptación

- **15e — API + DB online-only**: endpoints (`/faces`, `/identify`,
  `/login-password`, `/logout`, `/faces/{id}/photo`, `/access`, `/health`,
  `/ready` protegido), idempotencia + secuencia + primer-admin atómico, adaptadores
  `Api*`, migración `data/faces/*.json + *.png`, config `backend: file|api`,
  `api_url`, `device_id`. Aceptación: 2 PCs enrolando en paralelo no duplican ni
  crean 2 admins; reintento con misma key no duplica; sin red no hay login; gate
  verde + `integration` contra API de test.
- **15f — Endurecimiento empresa**: rate-limit global, revocación de devices,
  fotos en S3/CDN, pgvector HNSW, paneles GUI contra API, métricas/backup,
  despliegue `docker compose`.

## 8. Decisiones abiertas (cerrar al iniciar 15e)

- `F-XXXX` secuencial vs UUID (secuencial legible, UUID sin coordinación).
- Duplicado biométrico: rechazar (`409`) o solo avisar.
- TTL de sesión en empresa (`session_timeout_seconds`).
- Intervalo `/ready`: 5 min (decidido) con fallback a 10 min si Neon agota CU.
