"""Tests del dominio de claves de respaldo (hash PBKDF2 y autenticacion).

Sin infraestructura: se usan iteraciones bajas para que el hashing sea rapido.
"""

from __future__ import annotations

import pytest

from recognizer.core.constants import PASSWORD_HASH_ALGORITHM
from recognizer.core.domain.credentials import (
    authenticate,
    hash_password,
    validate_password,
    verify_password,
)
from recognizer.core.domain.face import EnrolledFace, FaceEmbedding
from recognizer.core.domain.identity import Role
from recognizer.core.errors import ConfigError

EMBEDDING: FaceEmbedding = (1.0, 0.0)
SALT = b"0123456789abcdef"
ITERATIONS = 1000
CLAVE = "clave1"


def _face(
    face_id: str = "F-0001",
    name: str = "Ada",
    *,
    password: str | None = CLAVE,
) -> EnrolledFace:
    password_hash = (
        hash_password(password, salt=SALT, iterations=ITERATIONS) if password is not None else ""
    )
    return EnrolledFace(
        face_id=face_id,
        name=name,
        embedding=EMBEDDING,
        samples=5,
        created_at="2026-09-19T00:00:00+00:00",
        role=Role.OPERATOR,
        password_hash=password_hash,
    )


def test_hash_password_format_and_verify() -> None:
    encoded = hash_password(CLAVE, salt=SALT, iterations=ITERATIONS)

    parts = encoded.split("$")
    assert len(parts) == 4
    assert parts[0] == PASSWORD_HASH_ALGORITHM
    assert parts[1] == str(ITERATIONS)
    assert verify_password(CLAVE, encoded)


def test_verify_password_rejects_wrong_password() -> None:
    encoded = hash_password(CLAVE, salt=SALT, iterations=ITERATIONS)

    assert not verify_password("otra", encoded)


def test_verify_password_rejects_corrupt_hashes() -> None:
    assert not verify_password(CLAVE, "")
    assert not verify_password(CLAVE, "sin-separadores")
    assert not verify_password(CLAVE, "a$b$c$d")
    assert not verify_password(CLAVE, f"md5${ITERATIONS}$c2FsdA==$aGFzaA==")
    assert not verify_password(CLAVE, f"{PASSWORD_HASH_ALGORITHM}$0$c2FsdA==$aGFzaA==")
    assert not verify_password(CLAVE, f"{PASSWORD_HASH_ALGORITHM}${ITERATIONS}$%%%$%%%")
    assert not verify_password("", hash_password(CLAVE, salt=SALT, iterations=ITERATIONS))


def test_hash_password_random_salt_differs_but_verifies() -> None:
    first = hash_password(CLAVE, iterations=ITERATIONS)
    second = hash_password(CLAVE, iterations=ITERATIONS)

    assert first != second
    assert verify_password(CLAVE, first)
    assert verify_password(CLAVE, second)


def test_verify_password_other_iterations_does_not_match() -> None:
    encoded = hash_password(CLAVE, salt=SALT, iterations=ITERATIONS)
    tampered = encoded.replace(f"${ITERATIONS}$", f"${ITERATIONS + 1}$")

    assert not verify_password(CLAVE, tampered)


def test_hash_password_rejects_empty_password() -> None:
    with pytest.raises(ValueError, match="vacia"):
        hash_password("")


def test_hash_password_rejects_invalid_iterations() -> None:
    with pytest.raises(ValueError, match="iterations"):
        hash_password(CLAVE, iterations=0)


def test_hash_password_rejects_empty_salt() -> None:
    with pytest.raises(ValueError, match="sal"):
        hash_password(CLAVE, salt=b"", iterations=ITERATIONS)


def test_validate_password_accepts_long_enough() -> None:
    validate_password("abcd")
    validate_password("abcd", min_length=2)


def test_validate_password_rejects_short() -> None:
    with pytest.raises(ValueError, match="al menos"):
        validate_password("abc")


def test_validate_password_rejects_invalid_min_length() -> None:
    with pytest.raises(ConfigError, match="longitud minima"):
        validate_password("abcd", min_length=0)


def test_authenticate_by_name_is_case_insensitive() -> None:
    face = _face(name="Ada")

    assert authenticate((face,), name_or_id="aDa", password=CLAVE) is face
    assert authenticate((face,), name_or_id="  ADA  ", password=CLAVE) is face


def test_authenticate_by_id_is_case_insensitive() -> None:
    face = _face(face_id="F-0001")

    assert authenticate((face,), name_or_id="f-0001", password=CLAVE) is face


def test_authenticate_rejects_wrong_password() -> None:
    face = _face()
    mala = "mala"

    assert authenticate((face,), name_or_id="Ada", password=mala) is None


def test_authenticate_ignores_faces_without_password() -> None:
    face = _face(password=None)

    assert authenticate((face,), name_or_id="Ada", password=CLAVE) is None


def test_authenticate_empty_gallery_returns_none() -> None:
    assert authenticate((), name_or_id="Ada", password=CLAVE) is None


def test_authenticate_blank_query_or_password_returns_none() -> None:
    face = _face()

    assert authenticate((face,), name_or_id="   ", password=CLAVE) is None
    assert authenticate((face,), name_or_id="Ada", password="") is None


def test_authenticate_homonyms_picks_the_matching_password() -> None:
    clave_a = "primera1"
    clave_b = "segunda1"
    clave_c = "tercera1"
    first = _face("F-0001", "Ada", password=clave_a)
    second = _face("F-0002", "Ada", password=clave_b)

    assert authenticate((first, second), name_or_id="Ada", password=clave_a) is first
    assert authenticate((first, second), name_or_id="Ada", password=clave_b) is second
    assert authenticate((first, second), name_or_id="Ada", password=clave_c) is None
