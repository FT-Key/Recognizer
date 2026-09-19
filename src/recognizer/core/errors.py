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


class PoseEstimatorError(RecognizerError):
    """El estimador de pose no pudo abrirse o fallo."""


class FaceRecognizerError(RecognizerError):
    """El reconocedor facial no pudo abrirse o fallo."""


class FaceRepositoryError(RecognizerError):
    """El almacen de rostros enrolados no pudo leerse o escribirse."""


class ActionError(RecognizerError):
    """La accion local no pudo ejecutarse."""
