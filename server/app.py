"""
Cineloom remote generation server  (P2, server side)
=====================================================

A small, self-contained FastAPI service that wraps the **verified** diffusers
LTX-2.3 stack (docs §06③) and exposes an OpenAI-compatible ``/v1`` dialect so
the Blender add-on's "Cineloom Remote · LTX-2.3" model can generate on the GPU
server instead of the editing host.

Design
------
* One LTX-2.3 pipeline, loaded **once**, lazily on the first job.
* ``enable_model_cpu_offload()`` — the whole pipeline on CUDA OOMs at ~30 GB;
  offload keeps the peak at ~10–15 GB (verified).
* A single background worker processes one job at a time (the model is heavy and
  offload-bound; concurrency would only thrash). Extra jobs queue.
* Artifacts are mp4 files on disk; ``/v1/files/{id}`` streams them back.

Endpoints
---------
    GET  /health
    POST /v1/videos              {prompt, negative_prompt, width, height,
                                   num_frames, fps, num_inference_steps,
                                   guidance_scale, seed, strength, image_b64?}
                                   -> {id, status}
    GET  /v1/jobs/{id}           -> {status, progress, file_id?, error?}
    GET  /v1/files/{id}          -> video/mp4 bytes
    POST /v1/files               (multipart) -> {file_id}   (reference upload)

Auth (optional)
---------------
Set ``CINELOOM_API_KEY`` to require a key, accepted as ``Authorization: Bearer``,
``X-API-Key`` header, or ``?api_key=`` query. Unset ⇒ open (internal network).
"""

from __future__ import annotations

import base64
import os
import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_DIR = os.environ.get("CINELOOM_MODEL_DIR", "/model")
WORK_DIR = os.environ.get("CINELOOM_WORK_DIR", "/work")
API_KEY = os.environ.get("CINELOOM_API_KEY", "").strip()
# Hard ceilings (verified: 241 frames/10s OOMs; ~5-6s is the single-shot limit).
MAX_FRAMES = int(os.environ.get("CINELOOM_MAX_FRAMES", "161"))
MAX_PIXELS = int(os.environ.get("CINELOOM_MAX_PIXELS", str(768 * 1280)))

os.makedirs(WORK_DIR, exist_ok=True)
FILES_DIR = os.path.join(WORK_DIR, "files")
os.makedirs(FILES_DIR, exist_ok=True)

app = FastAPI(title="Cineloom Remote Generation Server", version="0.1.0")


# ---------------------------------------------------------------------------
# Job model + in-process queue
# ---------------------------------------------------------------------------

@dataclass
class Job:
    id: str
    status: str = "queued"          # queued | running | succeeded | failed
    phase: str = "queued"
    progress: float = 0.0
    file_id: Optional[str] = None
    error: Optional[str] = None
    created: float = field(default_factory=time.time)
    payload: dict = field(default_factory=dict)

    def public(self) -> dict:
        d = asdict(self)
        d.pop("payload", None)
        return d


_JOBS: dict[str, Job] = {}
_JOB_Q: "queue.Queue[str]" = queue.Queue()
_LOCK = threading.Lock()

# The pipeline is loaded once by the worker thread.
_PIPE = None
_PIPE_ERR: Optional[str] = None


class VideoRequest(BaseModel):
    model: str = "ltx-2.3"
    prompt: str = ""
    negative_prompt: str = (
        "bright, colorful, clean, two people, duplicate person, blurry, "
        "low quality, distorted, deformed"
    )
    width: int = 768
    height: int = 1280
    num_frames: int = 121
    fps: float = 24.0
    num_inference_steps: int = 8
    guidance_scale: float = 1.0
    seed: int = 7
    strength: float = 1.0
    image_b64: Optional[str] = Field(default=None, description="Base64 PNG first-frame condition")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _check_auth(request: Request) -> None:
    if not API_KEY:
        return
    presented = ""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        presented = auth[7:].strip()
    presented = presented or request.headers.get("x-api-key", "")
    presented = presented or request.query_params.get("api_key", "")
    if presented != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Pipeline loading + generation (verified recipe)
# ---------------------------------------------------------------------------

def _load_pipeline():
    """Load LTX-2.3 once. Mirrors the verified _ltx2_*.py scripts exactly."""
    global _PIPE, _PIPE_ERR
    if _PIPE is not None or _PIPE_ERR is not None:
        return
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    # SDNQ tries to JIT-compile a Triton probe on import; disable it (and the
    # Triton MM backend) so it falls back to PyTorch eager — same as the addon.
    os.environ.setdefault("SDNQ_USE_TORCH_COMPILE", "0")
    os.environ.setdefault("SDNQ_USE_TRITON_MM", "0")
    try:
        import torch
        import sdnq  # noqa: F401 — registers the sdnq int8 quantizer
        from diffusers.pipelines.ltx2.pipeline_ltx2_condition import (
            LTX2ConditionPipeline,
        )

        t0 = time.time()
        pipe = LTX2ConditionPipeline.from_pretrained(
            MODEL_DIR, torch_dtype=torch.bfloat16
        )
        # NOTE: never pipe.to("cuda") — the whole pipeline OOMs at ~30 GB.
        # Offload mode is configurable so the service can stay within whatever
        # the shared GPU has free:
        #   "model"      ~10-15 GB peak, faster (verified single-shot ≈92s/5s)
        #   "sequential" ~6-8 GB  peak, slower — the neighbour-friendly default
        offload = os.environ.get("CINELOOM_OFFLOAD", "sequential").lower()
        if offload == "model":
            pipe.enable_model_cpu_offload()
        else:
            pipe.enable_sequential_cpu_offload()
        try:
            pipe.vae.enable_tiling()
        except Exception:  # noqa: BLE001
            pass
        print(f"[cineloom] offload mode: {offload}", flush=True)
        _PIPE = pipe
        print(f"[cineloom] pipeline loaded in {time.time() - t0:.0f}s", flush=True)
    except Exception as exc:  # noqa: BLE001
        _PIPE_ERR = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()


def _align(req: VideoRequest) -> tuple[int, int, int]:
    """Apply the verified alignment + safety caps."""
    w = max(32, (req.width // 32) * 32)
    h = max(32, (req.height // 32) * 32)
    # Cap pixel budget by scaling down proportionally if needed.
    if w * h > MAX_PIXELS:
        scale = (MAX_PIXELS / (w * h)) ** 0.5
        w = max(32, (int(w * scale) // 32) * 32)
        h = max(32, (int(h * scale) // 32) * 32)
    target = min(req.num_frames, MAX_FRAMES)
    num_frames = max(9, ((target - 1) // 8) * 8 + 1)   # 8n+1
    return w, h, num_frames


def _run_job(job: Job) -> None:
    import torch
    from diffusers.pipelines.ltx2.pipeline_ltx2_condition import LTX2VideoCondition
    from diffusers.utils import export_to_video
    from PIL import Image

    req = VideoRequest(**job.payload)
    w, h, num_frames = _align(req)

    job.phase = "generating"
    total = max(1, req.num_inference_steps)

    def _cb(pipe, step, timestep, kw):
        job.progress = min(0.99, (step + 1) / total)
        return kw

    gen = torch.Generator("cpu").manual_seed(int(req.seed))
    call_kwargs = dict(
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        height=h,
        width=w,
        num_frames=num_frames,
        frame_rate=req.fps,
        num_inference_steps=req.num_inference_steps,
        guidance_scale=req.guidance_scale,
        generator=gen,
        callback_on_step_end=_cb,
    )

    # First-frame condition (img2vid). Pure t2v omits conditions.
    if req.image_b64:
        raw = base64.b64decode(req.image_b64)
        ref = Image.open(BytesIO(raw)).convert("RGB").resize((w, h))
        call_kwargs["conditions"] = [
            LTX2VideoCondition(frames=ref, index=0, strength=req.strength)
        ]

    out = _PIPE(**call_kwargs)
    vid = out.frames[0] if hasattr(out, "frames") else out[0]

    job.phase = "saving"
    file_id = f"{job.id}.mp4"
    dst = os.path.join(FILES_DIR, file_id)
    export_to_video(vid, dst, fps=req.fps)

    job.file_id = file_id
    job.progress = 1.0


def _worker() -> None:
    _load_pipeline()
    while True:
        job_id = _JOB_Q.get()
        job = _JOBS.get(job_id)
        if job is None:
            continue
        if _PIPE_ERR is not None:
            job.status, job.error, job.phase = "failed", _PIPE_ERR, "failed"
            continue
        try:
            job.status, job.phase = "running", "running"
            _run_job(job)
            job.status, job.phase = "succeeded", "done"
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.phase = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()


_WORKER = threading.Thread(target=_worker, daemon=True, name="cineloom-worker")
_WORKER.start()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_dir": MODEL_DIR,
        "pipeline_loaded": _PIPE is not None,
        "pipeline_error": _PIPE_ERR,
        "queued": _JOB_Q.qsize(),
        "auth_required": bool(API_KEY),
    }


@app.post("/v1/videos")
def create_video(req: VideoRequest, request: Request):
    _check_auth(request)
    if not req.prompt and not req.image_b64:
        raise HTTPException(status_code=400, detail="prompt or image_b64 is required")
    job = Job(id=uuid.uuid4().hex, payload=req.model_dump())
    with _LOCK:
        _JOBS[job.id] = job
    _JOB_Q.put(job.id)
    return JSONResponse({"id": job.id, "status": job.status})


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    _check_auth(request)
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.public()


@app.get("/v1/files/{file_id}")
def get_file(file_id: str, request: Request):
    _check_auth(request)
    # Prevent path traversal — only serve from FILES_DIR by basename.
    safe = os.path.basename(file_id)
    path = os.path.join(FILES_DIR, safe)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="file not found")
    media = "video/mp4" if safe.endswith(".mp4") else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=safe)


@app.post("/v1/files")
async def upload_file(request: Request, file: UploadFile = File(...), purpose: str = Form("reference")):
    _check_auth(request)
    file_id = f"ref_{uuid.uuid4().hex}_{os.path.basename(file.filename or 'upload')}"
    path = os.path.join(FILES_DIR, file_id)
    with open(path, "wb") as out:
        out.write(await file.read())
    return {"file_id": file_id, "purpose": purpose}
