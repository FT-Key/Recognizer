"""Errores del dominio de Recognizer."""


class RecognizerError(Exception):
    """Error base de la aplicacion."""


class ConfigError(RecognizerError):
    """La configuracion es invalida o no se pudo cargar."""


class CameraError(RecognizerError):
    """La camara no pudo abrirse o fallo durante la captura."""
