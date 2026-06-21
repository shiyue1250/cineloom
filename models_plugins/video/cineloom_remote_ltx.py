"""
Cineloom Remote · LTX-2.3 video (self-hosted remote backend)
============================================================

The flagship of Cineloom's remote backend: text/image → video runs on a GPU
server, not the editing host. Select this model and the editor needs no large
GPU — generation is POSTed to ``/v1/videos`` and the finished clip is downloaded
onto the VSE timeline.

Mirrors the verified diffusers LTX-2.3 stack (``server/app.py``): portrait
768×1280, 8-step distilled, frame_rate 24, optional first-frame condition.
"""

from io import BytesIO

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...utils.helpers import solve_path, clean_filename
from ...models.remote_client import CineloomRemoteClient, RemoteConfig


class CineloomRemoteLTXPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/ltx-2.3"
    DISPLAY_NAME = "Cineloom Remote · LTX-2.3 (GPU server)"
    MODEL_TYPE   = "video"
    DESCRIPTION  = (
        "Text/image → video on your remote GPU backend (the bundled Cineloom "
        "server or any OpenAI-compatible /v1 endpoint). No local GPU needed. "
        "Set the URL in add-on preferences."
    )

    INPUTS      = InputSpec.PROMPT | InputSpec.NEG_PROMPT | InputSpec.IMAGE
    UI_SECTIONS = [
        UISection.PROMPT, UISection.NEG_PROMPT, UISection.IMAGE_STRIP,
        UISection.RESOLUTION, UISection.FRAMES, UISection.STEPS,
        UISection.IMAGE_STRENGTH, UISection.SEED,
    ]
    # Verified defaults: portrait 768×1280, 5s@24, 8-step distilled.
    PARAMS = ParamSpec(width=768, height=1280, frames=121, steps=8, guidance=1.0, strength=1.0)

    # No local ML packages required — generation happens on the server.
    REQUIRED_PACKAGES: list = []

    # The remote backend handles img2img/inpaint variation via the strength
    # knob; we never spin up a local pipeline.
    supports_inpaint = False

    def load(self, prefs, scene, **kwargs):
        """'Loading' a remote model just builds the HTTP client."""
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        # Fail fast with a clear message if the backend is unreachable.
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        self.set_phase(inputs, "Preparing request")

        # Use the backend model chosen in preferences (populated by Test
        # Connection); omit it entirely so the backend defaults when unset.
        payload = {
            "prompt": inputs.prompt,
            "negative_prompt": inputs.neg_prompt,
            "width": (inputs.width // 32) * 32,
            "height": (inputs.height // 32) * 32,
            "num_frames": int(inputs.frames),
            "fps": float(inputs.fps) if inputs.fps else 24.0,
            "num_inference_steps": int(inputs.steps) or 8,
            "guidance_scale": float(inputs.guidance) or 1.0,
            "seed": int(inputs.seed),
            "strength": float(inputs.strength),
        }

        model = (getattr(prefs, "cineloom_video_model", "") or "").strip()
        if model:
            payload["model"] = model

        # First-frame condition (img2vid). Encode inline as base64 PNG so the
        # whole job is one request; the server decodes image_b64.
        if inputs.image is not None:
            payload["image_b64"] = _pil_to_b64_png(inputs.image)

        dst_path = solve_path(
            clean_filename(f"remote_{inputs.seed}_{inputs.prompt}") + ".mp4"
        )

        def _phase(label: str) -> None:
            self.set_phase(inputs, label)

        def _progress(done: int, total: int) -> None:
            if inputs.progress_fn is not None:
                inputs.progress_fn(done, total)

        return client.generate_video(
            payload, dst_path, phase_fn=_phase, progress_fn=_progress
        )


def _pil_to_b64_png(image) -> str:
    """Encode a PIL image as a base64 PNG string (stdlib only)."""
    import base64

    buf = BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
