"""
Cineloom remote backend client.
================================

The core Cineloom delta over upstream Pallaidium: generation can run on a
**remote GPU backend** instead of the local machine, so the editing host needs
no large GPU. The client speaks an OpenAI-compatible ``/v1`` dialect and works
against either:

* the bundled **Cineloom server** (``server/``, an LTX-2.3 diffusers service you
  self-host), or
* **any OpenAI-compatible ``/v1`` endpoint** you point it at.

Design constraints
------------------
* **Standard library only.** Blender's bundled Python may not ship ``requests``;
  everything here uses ``urllib`` + ``json`` so the addon never adds a runtime
  dependency just to talk to the backend.
* **Async-job aware.** Heavy video jobs return a job id; the client polls
  ``GET /v1/jobs/{id}`` until the job finishes, then downloads the artifact. If a
  backend answers synchronously (direct URL / file id / raw bytes) that path is
  handled too.
* **Flexible auth.** Bearer header, ``X-API-Key`` header and ``?api_key=`` query
  are all sent, so it fits whichever form your backend expects.

Endpoints used:
    POST /v1/videos                 text/image → video
    POST /v1/images/generations     text → image
    POST /v1/audio/speech           TTS
    POST /v1/audio/transcriptions   ASR (multipart)
    POST /v1/files                  upload a reference (multipart)
    GET  /v1/files/{id}             download an artifact
    GET  /v1/jobs/{id}              poll job status
    GET  /health                    liveness
"""

from __future__ import annotations

import io
import json
import os
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional


class RemoteBackendError(RuntimeError):
    """Raised for any non-recoverable remote-backend failure."""


# --------------------------------------------------------------------------- #
# Configuration resolution (preferences first, environment as fallback)
# --------------------------------------------------------------------------- #

DEFAULT_TIMEOUT = 30          # seconds for control-plane calls
DEFAULT_POLL_INTERVAL = 2.0   # seconds between job polls
DEFAULT_JOB_TIMEOUT = 1800    # 30 min hard cap for a single generation


@dataclass
class RemoteConfig:
    """Resolved connection settings for the remote backend."""

    base_url: str
    api_key: str = ""
    poll_interval: float = DEFAULT_POLL_INTERVAL
    job_timeout: int = DEFAULT_JOB_TIMEOUT

    @classmethod
    def from_prefs(
        cls,
        prefs: Any,
        url_attr: str = "cineloom_remote_url",
        env_url: str = "CINELOOM_REMOTE_URL",
        label: str = "Remote Backend URL",
    ) -> "RemoteConfig":
        """Build config from addon preferences, falling back to env vars.

        ``url_attr``/``env_url`` let the control plugin point at a different
        backend (the IC-LoRA control server) via its own preference field.
        The API key is shared. Environment fallbacks let plugins run headless.
        """
        base = (
            getattr(prefs, url_attr, "") or ""
        ).strip() or os.environ.get(env_url, "").strip()
        key = (
            getattr(prefs, "cineloom_remote_api_key", "") or ""
        ).strip() or os.environ.get("CINELOOM_REMOTE_API_KEY", "").strip()
        if not base:
            raise RemoteBackendError(
                f"{label} is not set. Open the Cineloom add-on preferences and "
                f"fill it in (e.g. http://your-gpu-host:8879), or set {env_url}."
            )
        return cls(base_url=base.rstrip("/"), api_key=key)


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

ProgressFn = Optional[Callable[[int, int], None]]
PhaseFn = Optional[Callable[[str], None]]


class CineloomRemoteClient:
    """Thin stdlib HTTP client for an OpenAI-compatible ``/v1`` backend."""

    def __init__(self, config: RemoteConfig):
        self.cfg = config

    # ---- low-level helpers -------------------------------------------- #

    def _url(self, path: str) -> str:
        url = f"{self.cfg.base_url}{path}"
        if self.cfg.api_key:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}api_key={urllib.parse.quote(self.cfg.api_key)}"
        return url

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {"Accept": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
            headers["X-API-Key"] = self.cfg.api_key
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        data: Optional[bytes] = None,
        content_type: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        expect_binary: bool = False,
    ):
        body = data
        headers = self._headers()
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type

        req = urllib.request.Request(
            self._url(path), data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                if expect_binary or (
                    raw and "application/json" not in ctype and not raw.lstrip().startswith(b"{")
                ):
                    return raw
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise RemoteBackendError(
                f"{method} {path} -> HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RemoteBackendError(
                f"Cannot reach remote backend at {self.cfg.base_url}: {exc.reason}"
            ) from exc

    @staticmethod
    def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
        """Encode a multipart/form-data body with stdlib only.

        ``fields`` maps name -> str. ``files`` maps name -> (filename, bytes).
        """
        boundary = f"----cineloom{uuid.uuid4().hex}"
        buf = io.BytesIO()
        for name, value in fields.items():
            buf.write(f"--{boundary}\r\n".encode())
            buf.write(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            )
            buf.write(f"{value}\r\n".encode())
        for name, (filename, content) in files.items():
            buf.write(f"--{boundary}\r\n".encode())
            buf.write(
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'.encode()
            )
            buf.write(b"Content-Type: application/octet-stream\r\n\r\n")
            buf.write(content)
            buf.write(b"\r\n")
        buf.write(f"--{boundary}--\r\n".encode())
        return buf.getvalue(), f"multipart/form-data; boundary={boundary}"

    # ---- public API --------------------------------------------------- #

    def health(self) -> dict:
        """Return the backend health payload (raises if unreachable)."""
        result = self._request("GET", "/health", timeout=10)
        return result if isinstance(result, dict) else {"raw": str(result)}

    def list_models(self) -> list:
        """Discover the backend's models via ``GET /v1/models`` (OpenAI-style).

        Returns a list of dicts, each at least ``{"id": ...}``; ``type`` and
        ``modes`` are used when present. Backend-agnostic — works against any
        compliant ``/v1`` service.
        """
        result = self._request("GET", "/v1/models", timeout=15)
        if isinstance(result, dict):
            data = result.get("data", result.get("models", []))
        else:
            data = result if isinstance(result, list) else []
        out = []
        for m in data:
            if isinstance(m, dict) and m.get("id"):
                out.append({
                    "id": m["id"],
                    "type": m.get("type", ""),
                    "modes": m.get("modes", []),
                })
            elif isinstance(m, str):
                out.append({"id": m, "type": "", "modes": []})
        return out

    def upload_file(self, filename: str, content: bytes, purpose: str = "reference") -> str:
        """Upload a reference file, returning its file id."""
        body, ctype = self._multipart(
            {"purpose": purpose}, {"file": (filename, content)}
        )
        result = self._request(
            "POST", "/v1/files", data=body, content_type=ctype, timeout=120
        )
        file_id = _extract_file_id(result)
        if not file_id:
            raise RemoteBackendError(f"Upload returned no file id: {result}")
        return file_id

    def download_to(self, file_ref: str, dest_path: str) -> str:
        """Download an artifact (file id or absolute URL) to ``dest_path``."""
        if file_ref.startswith("http://") or file_ref.startswith("https://"):
            url = file_ref
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=300) as resp, open(dest_path, "wb") as out:
                _copy_stream(resp, out)
            return dest_path
        raw = self._request(
            "GET", f"/v1/files/{file_ref}", timeout=300, expect_binary=True
        )
        if isinstance(raw, (bytes, bytearray)):
            with open(dest_path, "wb") as out:
                out.write(raw)
            return dest_path
        # Some backends answer with {"url": ...} for a file id.
        url = _extract_url(raw)
        if url:
            return self.download_to(url, dest_path)
        raise RemoteBackendError(f"Cannot download artifact {file_ref}: {raw}")

    def wait_for_job(
        self,
        job_id: str,
        *,
        progress_fn: ProgressFn = None,
        phase_fn: PhaseFn = None,
    ) -> dict:
        """Poll ``/v1/jobs/{id}`` until terminal; return the final job dict."""
        deadline = time.monotonic() + self.cfg.job_timeout
        last_phase = ""
        while True:
            job = self._request("GET", f"/v1/jobs/{job_id}", timeout=DEFAULT_TIMEOUT)
            status = str(job.get("status", "")).lower()
            phase = job.get("phase") or status
            if phase and phase != last_phase and phase_fn:
                phase_fn(str(phase))
                last_phase = phase
            if progress_fn and "progress" in job:
                try:
                    p = float(job["progress"])
                    progress_fn(int(p * 100), 100)
                except (TypeError, ValueError):
                    pass
            if status in ("succeeded", "completed", "success", "done"):
                return job
            if status in ("failed", "error", "cancelled", "canceled"):
                raise RemoteBackendError(
                    f"Remote job {job_id} {status}: {job.get('error', job)}"
                )
            if time.monotonic() > deadline:
                raise RemoteBackendError(
                    f"Remote job {job_id} timed out after {self.cfg.job_timeout}s"
                )
            time.sleep(self.cfg.poll_interval)

    def _submit_and_collect(
        self,
        path: str,
        payload: dict,
        dest_path: str,
        *,
        progress_fn: ProgressFn = None,
        phase_fn: PhaseFn = None,
    ) -> str:
        """POST a generation request, follow the job, download to dest_path.

        Handles three backend response shapes:
        1. async  -> {"id"/"job_id": ...}  then poll + download
        2. direct -> {"url"/"file_id"/"output": ...}
        3. raw    -> binary body written straight to dest_path
        """
        if phase_fn:
            phase_fn("Submitting")
        result = self._request("POST", path, json_body=payload, timeout=120)

        if isinstance(result, (bytes, bytearray)):
            with open(dest_path, "wb") as out:
                out.write(result)
            return dest_path

        job_id = result.get("id") or result.get("job_id") or result.get("task_id")
        # A direct artifact reference present immediately means no polling needed.
        direct = _extract_url(result) or _extract_file_id(result)
        status = str(result.get("status", "")).lower()
        if job_id and status not in ("succeeded", "completed", "success", "done") and not direct:
            if phase_fn:
                phase_fn("Generating (remote)")
            job = self.wait_for_job(
                job_id, progress_fn=progress_fn, phase_fn=phase_fn
            )
            direct = _extract_url(job) or _extract_file_id(job)
        if not direct:
            raise RemoteBackendError(
                f"Remote response had no artifact reference: {result}"
            )
        if phase_fn:
            phase_fn("Downloading")
        return self.download_to(direct, dest_path)

    # ---- typed generation calls --------------------------------------- #

    def generate_video(self, payload: dict, dest_path: str, **cb) -> str:
        return self._submit_and_collect("/v1/videos", payload, dest_path, **cb)

    def generate_image(self, payload: dict, dest_path: str, **cb) -> str:
        return self._submit_and_collect(
            "/v1/images/generations", payload, dest_path, **cb
        )

    def generate_speech(self, payload: dict, dest_path: str, **cb) -> str:
        return self._submit_and_collect(
            "/v1/audio/speech", payload, dest_path, **cb
        )

    def generate_control(
        self,
        video_path: str,
        fields: dict,
        dest_path: str,
        *,
        progress_fn: ProgressFn = None,
        phase_fn: PhaseFn = None,
    ) -> str:
        """IC-LoRA motion control: upload a reference video (multipart) + params
        to ``/v1/videos/control``, follow the job, download the result.

        ``fields`` are the form fields (prompt, control_strength, width, …).
        """
        if phase_fn:
            phase_fn("Uploading reference")
        with open(video_path, "rb") as fh:
            content = fh.read()
        body, ctype = self._multipart(
            {k: str(v) for k, v in fields.items()},
            {"file": (os.path.basename(video_path), content)},
        )
        result = self._request(
            "POST", "/v1/videos/control", data=body, content_type=ctype, timeout=180
        )
        job_id = result.get("id") or result.get("job_id")
        direct = _extract_url(result) or _extract_file_id(result)
        if job_id and not direct:
            job = self.wait_for_job(job_id, progress_fn=progress_fn, phase_fn=phase_fn)
            direct = _extract_url(job) or _extract_file_id(job)
        if not direct:
            raise RemoteBackendError(f"Control response had no artifact: {result}")
        if phase_fn:
            phase_fn("Downloading")
        return self.download_to(direct, dest_path)

    def transcribe(self, filename: str, content: bytes, model: str = "") -> str:
        """ASR: upload audio multipart, return the transcript text."""
        fields = {"model": model} if model else {}
        body, ctype = self._multipart(fields, {"file": (filename, content)})
        result = self._request(
            "POST", "/v1/audio/transcriptions", data=body,
            content_type=ctype, timeout=600,
        )
        if isinstance(result, (bytes, bytearray)):
            return result.decode("utf-8", "replace")
        return result.get("text") or result.get("transcript") or json.dumps(result)


# --------------------------------------------------------------------------- #
# small response-shape helpers (backends vary)
# --------------------------------------------------------------------------- #

def _extract_url(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in ("url", "output_url", "video_url", "audio_url", "image_url", "download_url"):
        val = obj.get(key)
        if isinstance(val, str) and val:
            return val
    # OpenAI-style nested data[0]
    data = obj.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return _extract_url(data[0])
    out = obj.get("output")
    if isinstance(out, dict):
        return _extract_url(out)
    return ""


def _extract_file_id(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in ("file_id", "id", "output_file_id", "result_file_id"):
        val = obj.get(key)
        # Avoid mistaking a job id for a file id at the top level.
        if isinstance(val, str) and val and key != "id":
            return val
    out = obj.get("output")
    if isinstance(out, dict):
        return _extract_file_id(out)
    return ""


def _copy_stream(src, dst, chunk: int = 1 << 16) -> None:
    while True:
        block = src.read(chunk)
        if not block:
            break
        dst.write(block)
