"""Claves de respaldo de los rostros enrolados (dominio puro).

Cada rostro puede llevar una clave para iniciar sesion cuando la camara no
funciona o el reconocimiento facial falla. El hash usa PBKDF2-HMAC-SHA256 con
sal aleatoria (biblioteca estandar) y se guarda como
``pbkdf2_sha256$<iteraciones>$<sal_b64>$<hash_b64>``; la verificacion compara en
tiempo constante con :func:`hmac.compare_digest`.

Sin infraestructura: solo ``hashlib``/``hmac``/``secrets``/``base64``.
"""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Iterable

from recognizer.core.constants import (
    DEFAULT_MIN_PASSWORD_LENGTH,
    PASSWORD_HASH_ALGORITHM,
    PASSWORD_HASH_ITERATIONS,
    PASSWORD_SALT_BYTES,
)
from recognizer.core.domain.face import EnrolledFace, normalize_national_id
from recognizer.core.errors import ConfigError

_HASH_SEPARATOR = "$"
_HASH_PARTS = 4
# Hash de referencia para igualar el tiempo cuando el usuario no existe (evita
# enumerar usuarios por latencia). Generado con la misma sal fija y el mismo
# numero de iteraciones que PASSWORD_HASH_ITERATIONS; no corresponde a ninguna
# clave real (nadie conoce su preimagen).
_DUMMY_HASH = (
    "pbkdf2_sha256$600000$AAAAAAAAAAAAAAAAAAAAAA==$SOT+9qSkktzhScMPYtseyFummUC+5MvYp6dNcPdDsQo="
)


def validate_password(password: str, *, min_length: int = DEFAULT_MIN_PASSWORD_LENGTH) -> None:
    """Valida que la clave cumpla la longitud minima.

    Raises:
        ConfigError: si ``min_length`` es invalido.
        ValueError: si la clave es mas corta que ``min_length``.
    """
    if min_length < 1:
        msg = f"La longitud minima de clave requiere >= 1 (llego {min_length})."
        raise ConfigError(msg)
    if len(password) < min_length:
        msg = f"La clave requiere al menos {min_length} caracteres."
        raise ValueError(msg)


def hash_password(
    password: str,
    *,
    salt: bytes | None = None,
    iterations: int = PASSWORD_HASH_ITERATIONS,
) -> str:
    """Devuelve el hash codificado de ``password`` (sal aleatoria si no se pasa).

    ``salt`` e ``iterations`` se inyectan en tests; en produccion se usa una sal
    aleatoria nueva por cada clave.

    Raises:
        ValueError: si la clave esta vacia o ``iterations`` es invalido.
    """
    if not password:
        msg = "La clave no puede estar vacia."
        raise ValueError(msg)
    if iterations < 1:
        msg = f"El hashing requiere iterations >= 1 (llego {iterations})."
        raise ValueError(msg)
    salt_bytes = salt if salt is not None else secrets.token_bytes(PASSWORD_SALT_BYTES)
    if not salt_bytes:
        msg = "La sal del hash no puede estar vacia."
        raise ValueError(msg)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    salt_b64 = base64.b64encode(salt_bytes).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return _HASH_SEPARATOR.join((PASSWORD_HASH_ALGORITHM, str(iterations), salt_b64, digest_b64))


def verify_password(password: str, encoded: str) -> bool:
    """Indica si ``password`` corresponde al hash codificado (False si corrupto)."""
    if not password or not encoded:
        return False
    parts = encoded.split(_HASH_SEPARATOR)
    if len(parts) != _HASH_PARTS:
        return False
    algorithm, iterations_text, salt_b64, digest_b64 = parts
    if algorithm != PASSWORD_HASH_ALGORITHM:
        return False
    try:
        iterations = int(iterations_text)
        if iterations < 1:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(digest_b64, validate=True)
    except (ValueError, TypeError):
        return False
    if not salt or not expected:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


def authenticate(faces: Iterable[EnrolledFace], *, user: str, password: str) -> EnrolledFace | None:
    """Busca por ID de rostro o DNI y verifica la clave; ``None`` si no coincide.

    El nombre ya no autentica (puede haber homonimos): solo ``face_id``
    (``F-0001``, case-insensitive) o DNI normalizado (se aceptan puntos y
    espacios al ingresarlo). Un rostro sin clave no puede autenticarse.
    """
    raw = (user or "").strip()
    if not raw or not password:
        return None
    query_id = raw.casefold()
    query_dni = normalize_national_id(raw)
    matched = False
    for face in faces:
        if not face.password_hash:
            continue
        by_id = face.face_id.casefold() == query_id
        by_dni = (
            bool(face.national_id)
            and bool(query_dni)
            and query_dni.isdigit()
            and face.national_id == query_dni
        )
        if not (by_id or by_dni):
            continue
        matched = True
        if verify_password(password, face.password_hash):
            return face
    if not matched:
        # Usuario inexistente: se verifica contra un hash dummy para que el
        # tiempo no delate si el ID/DNI esta enrolado.
        verify_password(password, _DUMMY_HASH)
    return None
