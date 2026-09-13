"""Construccion y ejecucion de pipelines de procesamiento."""

from dataclasses import dataclass

from recognizer.core.domain.frame import Frame
from recognizer.core.pipeline.context import FrameContext
from recognizer.core.pipeline.processor import Processor


@dataclass(frozen=True, slots=True)
class Pipeline:
    """Cadena de processors que se aplica en orden a cada fotograma."""

    processors: tuple[Processor, ...]

    def run(self, frame: Frame) -> FrameContext:
        """Ejecuta los processors en orden y devuelve el contexto final."""
        context = FrameContext(frame=frame)
        for processor in self.processors:
            context = processor.process(context)
        return context


class PipelineBuilder:
    """Acumula processors y produce un Pipeline inmutable."""

    def __init__(self) -> None:
        self._processors: list[Processor] = []

    def add(self, processor: Processor) -> "PipelineBuilder":
        """Agrega un processor al final de la cadena y devuelve este builder."""
        self._processors.append(processor)
        return self

    def build(self) -> Pipeline:
        """Construye el pipeline con los processors agregados."""
        return Pipeline(processors=tuple(self._processors))
