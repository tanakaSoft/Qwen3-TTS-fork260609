# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Async TTS API server for Qwen3-TTS.
#
# Exposes the three generation modes (CustomVoice / VoiceDesign / VoiceClone)
# and an asynchronous fine-tuning workflow over HTTP, so that multiple apps
# (on Windows or inside WSL2) can share a single GPU-resident model server.
#
# Run (inside WSL2, with the qwen-tts env active):
#     pip install -r server/requirements-server.txt
#     python server/tts_server_async.py
# then open http://localhost:8001/docs for the interactive API.
#
# SPDX-License-Identifier: Apache-2.0
import base64
import gc
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from qwen_tts import Qwen3TTSModel

# --------------------------------------------------------------------------- #
# Configuration (override via environment variables)
# --------------------------------------------------------------------------- #
# Repository root = parent of this file's directory (server/..).
REPO_ROOT = Path(__file__).resolve().parent.parent

DEVICE = os.environ.get("QWEN_TTS_DEVICE", "cuda:0")
DTYPE = torch.bfloat16
# Eager (standard PyTorch) attention is the default: officially supported, zero
# native-dependency risk, and sufficient on RTX 5090 (32 GB). See FORK_CHANGES.md.
ATTN_IMPL = os.environ.get("QWEN_TTS_ATTN", "eager")

# Whisper auto-transcription (transformers backend, no extra native deps).
# Friendly model name; mapped to a HuggingFace id in server/tts_whisper.py.
WHISPER_MODEL = os.environ.get("QWEN_TTS_WHISPER", "large-v3")

TOKENIZER_MODEL = os.environ.get("QWEN_TTS_TOKENIZER", "Qwen/Qwen3-TTS-Tokenizer-12Hz")
BASE_MODEL = os.environ.get("QWEN_TTS_BASE", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
VOICE_DESIGN_MODEL = os.environ.get("QWEN_TTS_VOICE_DESIGN", "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign")
# Optional fine-tuned CustomVoice checkpoint to load at startup (may not exist yet).
CUSTOM_MODEL = os.environ.get("QWEN_TTS_CUSTOM", "")
# Official pretrained CustomVoice model (preset speakers). Selectable from the UI
# but not auto-loaded; downloaded from HuggingFace on first load.
CUSTOM_PRESET_MODEL = os.environ.get(
    "QWEN_TTS_CUSTOM_PRESET", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
)

# Which models to load at startup. Loading all three needs ~10GB VRAM; on smaller
# GPUs set e.g. QWEN_TTS_LOAD="voice_clone" to load a single model.
LOAD_MODELS = os.environ.get("QWEN_TTS_LOAD", "voice_design,voice_clone,custom").split(",")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("qwen_tts_server")

@asynccontextmanager
async def _lifespan(app: FastAPI):
    _startup()
    yield


app = FastAPI(
    title="Qwen3-TTS Async Server (fork)",
    description="CustomVoice / VoiceDesign / VoiceClone generation + async fine-tuning.",
    version="1.0",
    lifespan=_lifespan,
)

# Loaded models, keyed by role. None means "not loaded".
models: Dict[str, Optional[Qwen3TTSModel]] = {
    "custom": None,
    "voice_design": None,
    "voice_clone": None,
}

# Path/id of the currently loaded CustomVoice model (for /custom_models display).
_loaded_custom_path: Optional[str] = None

# Single GPU: serialize all generation/transcription so concurrent clients
# (the Web UI plus any other app on the machine) never run the model in
# parallel on the same device. FastAPI runs sync endpoints in a threadpool,
# so without this lock two requests could touch the GPU at once.
_GEN_LOCK = threading.Lock()

# Lazily-created Whisper transcriber (transformers backend). Loaded on first
# /auto_transcribe call so startup stays fast and VRAM is only used on demand.
_whisper = None  # type: ignore[var-annotated]
_whisper_lock = threading.Lock()

# In-memory fine-tuning job registry. Replace with a persistent store for prod.
finetune_jobs: Dict[str, Dict] = {}


def _get_whisper(model_name: Optional[str] = None):
    """Return a ready WhisperTranscriber, (re)loading if the model changed."""
    global _whisper
    from tts_whisper import WhisperTranscriber  # local import: optional feature

    target = model_name or WHISPER_MODEL
    with _whisper_lock:
        if _whisper is None or _whisper.model_name != target:
            if _whisper is not None:
                _whisper.unload()
            logger.info("Loading Whisper model: %s", target)
            _whisper = WhisperTranscriber(target, device=DEVICE, dtype=DTYPE)
        return _whisper


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_model(model_path: str) -> Qwen3TTSModel:
    return Qwen3TTSModel.from_pretrained(
        model_path,
        device_map=DEVICE,
        dtype=DTYPE,
        attn_implementation=ATTN_IMPL,
    )


def _encode_wav(wav: np.ndarray) -> str:
    """Encode a float waveform (-1..1) as base64 16-bit PCM."""
    pcm = np.clip(wav, -1.0, 1.0)
    audio_bytes = (pcm * 32767).astype(np.int16).tobytes()
    return base64.b64encode(audio_bytes).decode("utf-8")


# --------------------------------------------------------------------------- #
# Pydantic schemas
# --------------------------------------------------------------------------- #
class CustomVoiceRequest(BaseModel):
    text: str
    language: str = "Japanese"
    speaker: str = "speaker_custom"
    instruct: str = ""


class BatchCustomVoiceRequest(BaseModel):
    texts: List[str]
    language: str = "Japanese"
    speaker: str = "speaker_custom"
    instruct: str = ""


class VoiceDesignRequest(BaseModel):
    text: str
    instruct: str
    language: str = "Japanese"


class TTSResponse(BaseModel):
    audio_base64: str
    sample_rate: int
    method: str


class BatchTTSResponse(BaseModel):
    audios: List[str]
    sample_rate: int
    method: str


class TranscribeResponse(BaseModel):
    text: str
    model: str
    language: str


class LoadCustomModelRequest(BaseModel):
    # A fine-tuned checkpoint path (under outputs/) or a HuggingFace model id
    # (e.g. the official preset CustomVoice model).
    model: str


class FinetuneRequest(BaseModel):
    # Path to a RAW jsonl (audio/text/ref_audio); prepare_data.py is run automatically.
    train_jsonl: str
    output_model_name: str = "finetuned_model"
    batch_size: int = 32
    lr: float = 2e-6
    num_epochs: int = 10
    speaker_name: str = "speaker_custom"


class FinetuneJobResponse(BaseModel):
    job_id: str
    status: str
    progress: int


# --------------------------------------------------------------------------- #
# Startup (called from the FastAPI lifespan handler defined above)
# --------------------------------------------------------------------------- #
def _startup():
    _restore_finetune_jobs()
    logger.info("Loading Qwen3-TTS models (%s)...", ", ".join(LOAD_MODELS))

    if "voice_design" in LOAD_MODELS:
        logger.info("  - VoiceDesign: %s", VOICE_DESIGN_MODEL)
        models["voice_design"] = _load_model(VOICE_DESIGN_MODEL)

    if "voice_clone" in LOAD_MODELS:
        logger.info("  - VoiceClone (Base): %s", BASE_MODEL)
        models["voice_clone"] = _load_model(BASE_MODEL)

    if "custom" in LOAD_MODELS:
        if CUSTOM_MODEL and Path(CUSTOM_MODEL).exists():
            global _loaded_custom_path
            logger.info("  - CustomVoice (fine-tuned): %s", CUSTOM_MODEL)
            models["custom"] = _load_model(CUSTOM_MODEL)
            _loaded_custom_path = CUSTOM_MODEL
        else:
            logger.warning(
                "  - CustomVoice not loaded (set QWEN_TTS_CUSTOM to a checkpoint, "
                "or run /finetune_async to create one)."
            )

    logger.info("Startup complete.")


# --------------------------------------------------------------------------- #
# Health / metadata
# --------------------------------------------------------------------------- #
@app.get("/health")
def health_check():
    active = [j for j in finetune_jobs.values() if j["status"] in ("pending", "running")]
    return {
        "status": "ok",
        "device": DEVICE,
        "models": {k: v is not None for k, v in models.items()},
        "active_finetune_jobs": len(active),
    }


@app.get("/supported_speakers")
def supported_speakers():
    model = models["custom"] or models["voice_clone"]
    if model is None:
        raise HTTPException(status_code=503, detail="No model loaded")
    return {"speakers": model.get_supported_speakers()}


@app.get("/supported_languages")
def supported_languages():
    model = models["custom"] or models["voice_clone"] or models["voice_design"]
    if model is None:
        raise HTTPException(status_code=503, detail="No model loaded")
    return {"languages": model.get_supported_languages()}


# --------------------------------------------------------------------------- #
# CustomVoice (fine-tuned model)
# --------------------------------------------------------------------------- #
@app.post("/generate_custom_voice", response_model=TTSResponse)
def generate_custom_voice(req: CustomVoiceRequest):
    if models["custom"] is None:
        raise HTTPException(
            status_code=503,
            detail="Custom model not loaded. Run /finetune_async first, "
            "or start the server with QWEN_TTS_CUSTOM set.",
        )
    try:
        with _GEN_LOCK:
            wavs, sr = models["custom"].generate_custom_voice(
                text=req.text,
                speaker=req.speaker,
                language=req.language,
                instruct=req.instruct or None,
            )
        return TTSResponse(audio_base64=_encode_wav(wavs[0]), sample_rate=sr, method="custom_voice")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/batch_generate_custom_voice", response_model=BatchTTSResponse)
def batch_generate_custom_voice(req: BatchCustomVoiceRequest):
    if models["custom"] is None:
        raise HTTPException(status_code=503, detail="Custom model not loaded.")
    if not req.texts:
        raise HTTPException(status_code=400, detail="texts must be non-empty")
    try:
        n = len(req.texts)
        with _GEN_LOCK:
            wavs, sr = models["custom"].generate_custom_voice(
                text=req.texts,
                speaker=[req.speaker] * n,
                language=[req.language] * n,
                instruct=[req.instruct] * n,
            )
        return BatchTTSResponse(
            audios=[_encode_wav(w) for w in wavs], sample_rate=sr, method="custom_voice"
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------------------------------- #
# CustomVoice model management (list / load fine-tuned or preset models)
# --------------------------------------------------------------------------- #
def _list_finetuned_models() -> List[Dict]:
    """Scan outputs/ for fine-tuned checkpoints (latest epoch per model dir)."""
    out_root = REPO_ROOT / "outputs"
    found: List[Dict] = []
    if not out_root.exists():
        return found
    for model_dir in sorted(p for p in out_root.iterdir() if p.is_dir()):
        checkpoints = list(model_dir.glob("checkpoint-epoch-*"))
        if not checkpoints:
            continue
        # Pick the highest epoch number as the representative checkpoint.
        def _epoch(p: Path) -> int:
            try:
                return int(p.name.rsplit("-", 1)[-1])
            except ValueError:
                return -1
        latest = max(checkpoints, key=_epoch)
        found.append(
            {
                "name": f"{model_dir.name} (epoch {_epoch(latest)})",
                "path": str(latest),
                "type": "finetuned",
            }
        )
    return found


@app.get("/custom_models")
def custom_models():
    """List loadable CustomVoice models: fine-tuned checkpoints + official preset."""
    items = _list_finetuned_models()
    items.append(
        {
            "name": "Official CustomVoice (preset speakers)",
            "path": CUSTOM_PRESET_MODEL,
            "type": "preset",
        }
    )
    return {"models": items, "loaded": _loaded_custom_path}


@app.post("/load_custom_model")
def load_custom_model(req: LoadCustomModelRequest):
    """Load a fine-tuned checkpoint or preset model as the active CustomVoice model."""
    global _loaded_custom_path
    target = req.model.strip()
    if not target:
        raise HTTPException(status_code=400, detail="model must be non-empty")
    # Local paths must exist; HF ids (with '/') are downloaded on demand.
    is_local = ("/" in target or "\\" in target) and Path(target).exists()
    looks_like_hf_id = target.count("/") == 1 and not Path(target).exists()
    if not is_local and not looks_like_hf_id:
        raise HTTPException(status_code=400, detail=f"model not found: {target}")
    try:
        with _GEN_LOCK:
            # Free the current model first to reduce peak VRAM during the swap.
            models["custom"] = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            models["custom"] = _load_model(target)
            _loaded_custom_path = target
        speakers = None
        try:
            speakers = models["custom"].get_supported_speakers()
        except Exception:  # noqa: BLE001 - not all models expose preset speakers
            speakers = None
        logger.info("CustomVoice model loaded: %s", target)
        return {"status": "ok", "loaded": target, "speakers": speakers}
    except Exception as exc:  # noqa: BLE001
        _loaded_custom_path = None
        raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------------------------------- #
# VoiceDesign
# --------------------------------------------------------------------------- #
@app.post("/generate_voice_design", response_model=TTSResponse)
def generate_voice_design(req: VoiceDesignRequest):
    if models["voice_design"] is None:
        raise HTTPException(status_code=503, detail="VoiceDesign model not loaded.")
    try:
        with _GEN_LOCK:
            wavs, sr = models["voice_design"].generate_voice_design(
                text=req.text,
                instruct=req.instruct,
                language=req.language,
            )
        return TTSResponse(audio_base64=_encode_wav(wavs[0]), sample_rate=sr, method="voice_design")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------------------------------- #
# VoiceClone (reference audio uploaded as multipart form-data)
# --------------------------------------------------------------------------- #
@app.post("/generate_voice_clone", response_model=TTSResponse)
async def generate_voice_clone(
    text: str = Form(...),
    ref_text: str = Form(...),
    language: str = Form("Auto"),
    x_vector_only_mode: bool = Form(False),
    ref_audio: UploadFile = File(...),
):
    if models["voice_clone"] is None:
        raise HTTPException(status_code=503, detail="VoiceClone model not loaded.")

    suffix = Path(ref_audio.filename or "ref.wav").suffix or ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await ref_audio.read())
            tmp_path = tmp.name

        with _GEN_LOCK:
            wavs, sr = models["voice_clone"].generate_voice_clone(
                text=text,
                language=language,
                ref_audio=tmp_path,
                ref_text=ref_text,
                x_vector_only_mode=x_vector_only_mode,
            )
        return TTSResponse(audio_base64=_encode_wav(wavs[0]), sample_rate=sr, method="voice_clone")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# --------------------------------------------------------------------------- #
# Whisper auto-transcription (for VoiceClone reference text)
# --------------------------------------------------------------------------- #
@app.get("/whisper_models")
def whisper_models():
    """Selectable Whisper models (friendly name -> HuggingFace id)."""
    from tts_whisper import WHISPER_MODEL_MAP

    return {"default": WHISPER_MODEL, "models": list(WHISPER_MODEL_MAP.keys())}


@app.post("/auto_transcribe", response_model=TranscribeResponse)
async def auto_transcribe(
    audio: UploadFile = File(...),
    model: str = Form(""),
    language: str = Form(""),
):
    """Transcribe an uploaded audio clip to text (for filling VoiceClone ref_text)."""
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        transcriber = _get_whisper(model or None)
        with _GEN_LOCK:  # share the GPU lock with TTS generation
            text = transcriber.transcribe(tmp_path, language=language or None)
        return TranscribeResponse(
            text=text, model=transcriber.model_name, language=language or "auto"
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# --------------------------------------------------------------------------- #
# GPU stats (for the Settings tab; torch-only, no extra deps)
# --------------------------------------------------------------------------- #
@app.get("/gpu_stats")
def gpu_stats():
    if not torch.cuda.is_available():
        return {"available": False, "device": DEVICE}

    idx = torch.cuda.current_device() if DEVICE.startswith("cuda") else 0
    try:
        free_b, total_b = torch.cuda.mem_get_info(idx)
    except Exception:  # noqa: BLE001 - mem_get_info may be unavailable on some setups
        free_b = total_b = 0
    gib = 1024 ** 3
    allocated_b = torch.cuda.memory_allocated(idx)
    reserved_b = torch.cuda.memory_reserved(idx)
    return {
        "available": True,
        "device": DEVICE,
        "device_name": torch.cuda.get_device_name(idx),
        "total_gb": round(total_b / gib, 2),
        "free_gb": round(free_b / gib, 2),
        "used_gb": round((total_b - free_b) / gib, 2),
        "allocated_gb": round(allocated_b / gib, 2),
        "reserved_gb": round(reserved_b / gib, 2),
        "models_loaded": {k: v is not None for k, v in models.items()},
        "whisper_loaded": _whisper.model_name if _whisper is not None else None,
    }


@app.post("/clear_gpu_cache")
def clear_gpu_cache():
    """Free cached (unallocated) VRAM. Does not unload models."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Fine-tuning (async background job)
# --------------------------------------------------------------------------- #
def _persist_job(job: Dict) -> None:
    """Write the job dict to outputs/<model>/job.json so it survives restarts."""
    out_dir = job.get("output_dir")
    if not out_dir:
        return
    try:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / "job.json").write_text(
            json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("could not persist job %s: %s", job.get("job_id"), exc)


def _restore_finetune_jobs() -> None:
    """Reload persisted job states from outputs/*/job.json after a restart.

    Jobs that were pending/running when the server stopped are marked failed —
    their subprocesses died with the server.
    """
    out_root = REPO_ROOT / "outputs"
    if not out_root.exists():
        return
    for job_file in out_root.glob("*/job.json"):
        try:
            job = json.loads(job_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("skipping unreadable %s: %s", job_file, exc)
            continue
        job_id = job.get("job_id")
        if not job_id:
            continue
        if job.get("status") in ("pending", "running"):
            job["status"] = "failed"
            job["message"] = "Interrupted by server restart."
            job["updated_at"] = datetime.now().isoformat()
            _persist_job(job)
        finetune_jobs[job_id] = job
    if finetune_jobs:
        logger.info("Restored %d fine-tuning job(s) from outputs/.", len(finetune_jobs))


def _run_subprocess(cmd: List[str]) -> None:
    """Run a finetuning subprocess from the repo root, raising on failure.
    Works on both Windows and Unix (pathlib handles path separators).
    """
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )


def _run_finetune_task(job_id: str, req: FinetuneRequest):
    job = finetune_jobs[job_id]

    def update(status=None, progress=None, message=None, model_path=None):
        if status is not None:
            job["status"] = status
        if progress is not None:
            job["progress"] = progress
        if message is not None:
            job["message"] = message
        if model_path is not None:
            job["model_path"] = model_path
        job["updated_at"] = datetime.now().isoformat()
        _persist_job(job)

    try:
        update(status="running", progress=5, message="Validating input...")
        if not Path(req.train_jsonl).exists():
            raise FileNotFoundError(f"train_jsonl not found: {req.train_jsonl}")

        output_dir = REPO_ROOT / "outputs" / req.output_model_name
        output_dir.mkdir(parents=True, exist_ok=True)
        codes_jsonl = output_dir / "train_with_codes.jsonl"

        # Step 1: extract audio_codes
        update(progress=15, message="Preparing data (extracting audio codes)...")
        _run_subprocess(
            [
                sys.executable, "finetuning/prepare_data.py",
                "--device", DEVICE,
                "--tokenizer_model_path", TOKENIZER_MODEL,
                "--input_jsonl", req.train_jsonl,
                "--output_jsonl", str(codes_jsonl),
            ]
        )

        # Step 2: supervised fine-tuning
        update(progress=35, message="Fine-tuning (this may take a while)...")
        _run_subprocess(
            [
                sys.executable, "finetuning/sft_12hz.py",
                "--init_model_path", BASE_MODEL,
                "--output_model_path", str(output_dir),
                "--train_jsonl", str(codes_jsonl),
                "--batch_size", str(req.batch_size),
                "--lr", str(req.lr),
                "--num_epochs", str(req.num_epochs),
                "--speaker_name", req.speaker_name,
            ]
        )

        # Step 3: load the final checkpoint and swap it in as the active custom model
        update(progress=90, message="Loading fine-tuned checkpoint...")
        checkpoint = output_dir / f"checkpoint-epoch-{req.num_epochs - 1}"
        if not checkpoint.exists():
            raise FileNotFoundError(f"checkpoint not found: {checkpoint}")
        global _loaded_custom_path
        with _GEN_LOCK:
            models["custom"] = _load_model(str(checkpoint))
            _loaded_custom_path = str(checkpoint)

        update(
            status="completed",
            progress=100,
            message=f"Done. CustomVoice ready (speaker='{req.speaker_name}').",
            model_path=str(checkpoint),
        )
        logger.info("[%s] fine-tuning complete: %s", job_id, checkpoint)

    except Exception as exc:  # noqa: BLE001
        update(status="failed", progress=0, message=f"Error: {exc}")
        logger.error("[%s] fine-tuning failed: %s", job_id, exc)


@app.post("/upload_train_jsonl")
async def upload_train_jsonl(file: UploadFile = File(...)):
    """Save an uploaded training JSONL under outputs/uploads/ and return its path.

    Lets UI users pick a local file instead of typing a server-side path. The
    audio paths INSIDE the JSONL must still be readable by this server.
    """
    name = Path(file.filename or "train.jsonl")
    stem = "".join(c for c in name.stem if c.isalnum() or c in "-_") or "train"
    dest_dir = REPO_ROOT / "outputs" / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{stem}.jsonl"
    dest.write_bytes(await file.read())
    logger.info("Training JSONL uploaded: %s", dest)
    return {"path": str(dest)}


@app.post("/finetune_async", response_model=FinetuneJobResponse)
def finetune_async(req: FinetuneRequest, background_tasks: BackgroundTasks):
    if not Path(req.train_jsonl).exists():
        raise HTTPException(status_code=400, detail=f"train_jsonl not found: {req.train_jsonl}")

    job_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    finetune_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Queued.",
        "model_path": None,
        "output_dir": str(REPO_ROOT / "outputs" / req.output_model_name),
        "created_at": now,
        "updated_at": now,
    }
    _persist_job(finetune_jobs[job_id])
    background_tasks.add_task(_run_finetune_task, job_id, req)
    logger.info("[%s] fine-tuning queued", job_id)
    return FinetuneJobResponse(job_id=job_id, status="pending", progress=0)


@app.get("/finetune_status/{job_id}")
def finetune_status(job_id: str):
    if job_id not in finetune_jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return finetune_jobs[job_id]


@app.get("/finetune_jobs")
def list_finetune_jobs():
    return {"total": len(finetune_jobs), "jobs": list(finetune_jobs.values())}


if __name__ == "__main__":
    import uvicorn

    # Bind to localhost by default: the API has no authentication, so exposing
    # it to the LAN must be an explicit choice (set QWEN_TTS_HOST=0.0.0.0).
    host = os.environ.get("QWEN_TTS_HOST", "127.0.0.1")
    port = int(os.environ.get("QWEN_TTS_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)
