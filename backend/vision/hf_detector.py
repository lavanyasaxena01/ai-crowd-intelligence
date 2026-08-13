"""
hf_detector.py

Real Hugging Face Hub object-detection integration for venue/crowd images.

Uses the Hub Inference API (no fake detections). Requires HF_TOKEN for
authenticated inference on gated/rate-limited endpoints.
"""

from __future__ import annotations

import io
import os
import tempfile
from typing import Any, Dict, List, Optional

from simulation.utils import get_logger

logger = get_logger(__name__)

DEFAULT_HF_MODEL = os.getenv("HF_MODEL", "facebook/detr-resnet-50")


def hf_config_status() -> Dict[str, Any]:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    model = os.getenv("HF_MODEL", DEFAULT_HF_MODEL)
    return {
        "configured": bool(token),
        "model": model,
        "provider": "huggingface_hub",
        "token_present": bool(token),
        "message": None if token else "Set HF_TOKEN in backend/.env to enable Hugging Face vision.",
    }


def analyze_crowd_image(image_bytes: bytes, score_threshold: float = 0.5) -> Dict[str, Any]:
    """
    Run Hugging Face object detection on an uploaded image.

    Returns people count and person detections from the Hub model.
    Raises RuntimeError with a clear message when configuration or inference fails.
    """
    status = hf_config_status()
    if not status["token_present"]:
        raise RuntimeError(
            "Hugging Face is not configured. Set HF_TOKEN in backend/.env "
            "(create a token at https://huggingface.co/settings/tokens)."
        )

    try:
        from huggingface_hub import InferenceClient
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Missing vision dependencies. Install with: pip install huggingface_hub Pillow"
        ) from exc

    model_id = status["model"]
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Invalid image upload: {exc}") from exc

    client = InferenceClient(model=model_id, token=token)
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        image.save(temp_path, format="JPEG")
        detections = client.object_detection(
            temp_path,
            model=model_id,
            threshold=score_threshold
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("HF inference failed: %s", exc)
        raise RuntimeError(
            f"Hugging Face inference failed for model '{model_id}': {exc}"
        ) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as cleanup_exc:
                logger.warning("Failed to clean up temp file %s: %s", temp_path, cleanup_exc)
    people: List[Dict[str, Any]] = []
    label_counts: Dict[str, int] = {}

    for det in detections or []:
        label = str(getattr(det, "label", None) or det.get("label") if isinstance(det, dict) else "object")
        score = float(getattr(det, "score", None) or (det.get("score") if isinstance(det, dict) else 0.0))
        box = getattr(det, "box", None) or (det.get("box") if isinstance(det, dict) else None)
        if score < score_threshold:
            continue
        label_counts[label] = label_counts.get(label, 0) + 1
        if label.lower() in ("person", "people", "human"):
            box_payload: Optional[Dict[str, float]] = None
            if box is not None:
                if isinstance(box, dict):
                    box_payload = {
                        "xmin": float(box.get("xmin", box.get("x_min", 0))),
                        "ymin": float(box.get("ymin", box.get("y_min", 0))),
                        "xmax": float(box.get("xmax", box.get("x_max", 0))),
                        "ymax": float(box.get("ymax", box.get("y_max", 0))),
                    }
                else:
                    box_payload = {
                        "xmin": float(getattr(box, "xmin", 0)),
                        "ymin": float(getattr(box, "ymin", 0)),
                        "xmax": float(getattr(box, "xmax", 0)),
                        "ymax": float(getattr(box, "ymax", 0)),
                    }
            people.append({"label": label, "score": round(score, 4), "box": box_payload})

    people_count = len(people)
    return {
        "status": "ok",
        "source": "huggingface",
        "model": model_id,
        "people_detected": people_count,
        "detections": people,
        "label_counts": label_counts,
        "score_threshold": score_threshold,
        "image_size": {"width": image.width, "height": image.height},
        "observation": (
            f"Detected {people_count} person(s) via Hugging Face model {model_id}."
            if people_count
            else f"No persons above threshold {score_threshold} detected by {model_id}."
        ),
    }
