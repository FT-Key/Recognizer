"""Punto de entrada del ejecutable empaquetado con PyInstaller.

PyInstaller necesita un script de arranque (no un modulo) para el Analysis.
Delegamos en el CLI real para no duplicar logica.
"""

import sys

from recognizer.cli.app import main

if __name__ == "__main__":
    sys.exit(main())
