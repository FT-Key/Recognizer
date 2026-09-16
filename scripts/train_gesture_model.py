"""Entrena un modelo de gestos personalizado con MediaPipe Model Maker.

Genera un archivo ``.task`` que la app web puede cargar via
``CONFIG.gestures.customModelUrl`` y la app de escritorio via
``gestures.model_path`` en config.yaml.

Requisitos (NO son dependencias del proyecto; se instalan aparte):
    uv pip install -r scripts/requirements-model-maker.txt

Estructura del dataset (una carpeta por gesto, con imagenes .jpg/.png):
    dataset/
        mi_gesto_a/  img1.jpg img2.jpg ...
        mi_gesto_b/  img1.jpg ...
        _neutral/    img1.jpg ...        # opcional: gesto de reposo

Uso:
    uv run python scripts/train_gesture_model.py --dataset dataset --epochs 10
    # Salida: models/custom_gesture_recognizer.task
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "dataset"
DEFAULT_OUTPUT = PROJECT_ROOT / "models"
EXPORTED_FILENAME = "custom_gesture_recognizer.task"
TRAIN_SPLIT = 0.8
VALIDATION_SPLIT = 0.5
DEFAULT_EPOCHS = 10
DEFAULT_BATCH_SIZE = 2
DEFAULT_LEARNING_RATE = 0.001
MISSING_DEPENDENCY_HINT = (
    "Falta mediapipe-model-maker. Instala las dependencias del entrenamiento con:\n"
    "    uv pip install -r scripts/requirements-model-maker.txt\n"
    "Nota: mediapipe-model-maker requiere TensorFlow y puede no estar disponible\n"
    "en todas las plataformas (probado en Linux/macOS; en Windows usa WSL)."
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entrena un modelo de gestos con Model Maker.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    return parser.parse_args()


def _validate_dataset(dataset: Path) -> None:
    if not dataset.is_dir():
        raise SystemExit(f"No existe el dataset: {dataset}")
    classes = [item for item in dataset.iterdir() if item.is_dir()]
    if len(classes) < 2:
        raise SystemExit(
            f"El dataset necesita al menos 2 carpetas de gestos en {dataset} "
            "(una por gesto, con imagenes dentro)."
        )
    print(f"Clases detectadas: {', '.join(sorted(c.name for c in classes))}")


def _import_model_maker() -> object:
    try:
        from mediapipe_model_maker import gesture_recognizer
    except ImportError as exc:
        raise SystemExit(MISSING_DEPENDENCY_HINT) from exc
    return gesture_recognizer


def _train(args: argparse.Namespace, gesture_recognizer: object) -> None:
    hparams = gesture_recognizer.HParams(
        export_dir=str(args.output),
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )
    print(f"Cargando dataset desde {args.dataset}...")
    data = gesture_recognizer.Dataset.from_folder(
        dirname=str(args.dataset),
        hparams=gesture_recognizer.HandDataPreprocessingParams(),
    )
    train_data, rest_data = data.split(TRAIN_SPLIT)
    validation_data, test_data = rest_data.split(VALIDATION_SPLIT)
    print(
        f"Split -> train: {len(train_data)}, validacion: {len(validation_data)}, "
        f"test: {len(test_data)}"
    )

    options = gesture_recognizer.GestureRecognizerOptions(hparams=hparams)
    print("Entrenando...")
    model = gesture_recognizer.GestureRecognizer.create(
        train_data=train_data,
        validation_data=validation_data,
        options=options,
    )

    loss, accuracy = model.evaluate(test_data, batch_size=1)
    print(f"Evaluacion -> loss: {loss:.4f}, accuracy: {accuracy:.4f}")

    args.output.mkdir(parents=True, exist_ok=True)
    model.export_model(filename=EXPORTED_FILENAME)
    exported = args.output / EXPORTED_FILENAME
    print(f"\nModelo exportado: {exported}")
    print("Web: define CONFIG.gestures.customModelUrl apuntando a ese archivo.")
    print("Escritorio: cambia gestures.model_path en config.yaml y declara custom_labels.")


def main() -> int:
    """Valida el dataset, entrena y exporta el modelo .task."""
    args = _parse_args()
    _validate_dataset(args.dataset)
    gesture_recognizer = _import_model_maker()
    _train(args, gesture_recognizer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
