"""Puerto de identidad y sesion facial.

La implementacion actual es `FileIdentityProvider` (sesion en
``data/faces/session.json`` junto al almacen de rostros). Una futura
`DbIdentityProvider` (SQLite/Postgres para login distribuido) solo tendria
que implementar este mismo puerto, sin tocar el dominio ni el launcher. El
modo sin login usa `AllowAllIdentityProvider` (Null Object).
"""

from typing import Protocol

from recognizer.core.domain.identity import Identity, Role


class IdentityProvider(Protocol):
    """Identidad actual derivada de la sesion facial persistida."""

    def current_identity(self) -> Identity:
        """Identidad de la sesion vigente o la invitada si no hay login."""
        ...

    def require_role(self, *roles: Role) -> Identity:
        """Identidad actual o falla con AuthError si su rol no esta incluido."""
        ...

    def refresh(self) -> Identity:
        """Relee la sesion del disco y devuelve la identidad vigente."""
        ...
