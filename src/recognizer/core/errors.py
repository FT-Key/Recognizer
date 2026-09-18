"""Errores del dominio de Recognizer."""


class RecognizerError(Exception):
    """Error base de la aplicacion."""


class ConfigError(RecognizerError):
    """La configuracion es invalida o no se pudo cargar."""


class CameraError(RecognizerError):
    """La camara no pudo abrirse o fallo durante la captura."""


class HandTrackerError(RecognizerError):
    """El detector de manos no pudo abrirse o fallo."""


class GestureClassifierError(RecognizerError):
    """El clasificador de gestos no pudo abrirse o fallo."""


class DetectorError(RecognizerError):
    """El detector de objetos no pudo abrirse o fallo."""


class ActionError(RecognizerError):
    """La accion local no pudo ejecutarse."""
