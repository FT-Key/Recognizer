"""Accion nula para gestos sin mapeo (Null Object)."""

from recognizer.core.domain.action import Action, ActionContext


class NoOpAction(Action):
    """No hace nada; es el fallback de los gestos sin accion configurada."""

    def execute(self, context: ActionContext) -> None:
        """Ignora la ejecucion."""
        del context
