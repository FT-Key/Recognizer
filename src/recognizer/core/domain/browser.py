"""Objetos de valor para el navegador controlado."""

from dataclasses import dataclass

from recognizer.core.errors import ConfigError


@dataclass(frozen=True, slots=True)
class TabKey:
    """Identificador de pestana registrada."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or self.value != self.value.strip():
            msg = f"El identificador de pestana no es valido: {self.value!r}"
            raise ConfigError(msg)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TabSpec:
    """Especificacion de una pestana registrada."""

    key: TabKey
    url: str
    match: str
