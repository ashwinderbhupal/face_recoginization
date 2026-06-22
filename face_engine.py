"""
Face detection + embedding engine built on InsightFace (ArcFace + RetinaFace).

Provides a lazily-initialized singleton so the (heavy) ONNX models load only once
per process, plus small helpers for embeddings and similarity.
"""

import contextlib
import io
import os
import sys

import numpy as np

import config

_app = None  # cached FaceAnalysis instance
_dlls_registered = False


def _register_cuda_dlls():
    """
    Put the nvidia-*-cu12 pip packages' bin folders on the DLL search path.

    cuDNN 9 lazily loads helper DLLs (cudnn_engines_*.dll) at runtime via
    LoadLibrary, so the directories must be registered, not just preloaded.
    """
    global _dlls_registered
    if _dlls_registered:
        return
    _dlls_registered = True
    try:
        import nvidia
    except ImportError:
        return
    base = os.path.dirname(nvidia.__file__)
    bin_dirs = [
        os.path.join(base, d, "bin")
        for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d, "bin"))
    ]
    for d in bin_dirs:
        try:
            os.add_dll_directory(d)
        except (OSError, AttributeError):
            pass
    if bin_dirs:
        os.environ["PATH"] = os.pathsep.join(bin_dirs) + os.pathsep + os.environ.get("PATH", "")
_extra_modules = []  # modules requested on top of config.ALLOWED_MODULES (e.g. genderage)


def request_modules(modules):
    """Ask for extra sub-models (e.g. ['genderage']) before the app is built."""
    global _extra_modules
    for m in modules:
        if m not in _extra_modules:
            _extra_modules.append(m)


def _select_providers():
    """Prefer GPU execution providers when available, falling back to CPU."""
    _register_cuda_dlls()
    import onnxruntime as ort

    # Load CUDA / cuDNN DLLs shipped via the nvidia-*-cu12 pip packages so the
    # CUDA execution provider can initialize without a system CUDA install.
    try:
        ort.preload_dlls()
    except Exception:
        pass

    # Quiet onnxruntime's per-session "Applied providers" info spam.
    ort.set_default_logger_severity(3)

    available = ort.get_available_providers()
    # TensorRT needs extra libraries we don't ship; don't offer it.
    available = [p for p in available if p != "TensorrtExecutionProvider"]
    preferred = ["CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"]
    chosen = [p for p in preferred if p in available]
    return chosen or ["CPUExecutionProvider"]


def get_app():
    """Return a ready-to-use InsightFace FaceAnalysis app (loaded once)."""
    global _app
    if _app is None:
        # Imported lazily so that --help and pure DB commands stay fast.
        from insightface.app import FaceAnalysis

        modules = list(config.ALLOWED_MODULES) + _extra_modules
        providers = _select_providers()
        on_gpu = providers[0] != "CPUExecutionProvider"
        # ctx_id >= 0 tells InsightFace to use the GPU; -1 forces CPU.
        ctx_id = 0 if on_gpu else -1
        device = "GPU" if on_gpu else "CPU"
        print(f"Loading face model '{config.MODEL_NAME}' ({', '.join(modules)}) "
              f"on {device} via {providers[0]}...")
        try:
            # InsightFace prints "find model" / "model ignore" lines via print();
            # swallow that chatter so only our status lines show.
            with contextlib.redirect_stdout(io.StringIO()):
                _app = FaceAnalysis(
                    name=config.MODEL_NAME,
                    allowed_modules=modules,
                    providers=providers,
                )
                _app.prepare(ctx_id=ctx_id, det_size=config.DET_SIZE)
        except Exception as exc:  # pragma: no cover - environment dependent
            print(f"ERROR: could not initialize InsightFace: {exc}")
            sys.exit(1)
        print("Model ready.")
    return _app


def detect_faces(image_bgr):
    """
    Run detection + embedding on a BGR image (OpenCV format).

    Returns a list of insightface Face objects, filtered by detector confidence.
    Each face exposes: .bbox, .kps, .det_score, .normed_embedding, .age, .sex
    """
    app = get_app()
    faces = app.get(image_bgr)
    return [f for f in faces if f.det_score >= config.MIN_DET_SCORE]


def largest_face(faces):
    """Return the face with the biggest bounding box, or None."""
    if not faces:
        return None

    def area(f):
        x1, y1, x2, y2 = f.bbox
        return (x2 - x1) * (y2 - y1)

    return max(faces, key=area)


def cosine_similarity(a, b):
    """Cosine similarity between two embedding vectors."""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    return float(np.dot(a, b) / denom)
