"""Contrato de un paso del pipeline."""

from typing import Protocol

from recognizer.core.pipeline.context import FrameContext


class Processor(Protocol):
    """Transforma un contexto de fotograma en otro."""

    def process(self, context: FrameContext) -> FrameContext:
        """Procesa el contexto y devuelve el contexto actualizado."""
        ...
