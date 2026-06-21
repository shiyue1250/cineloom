"""
Cineloom Remote · Video (remote backend)
========================================

One video model for the remote backend. Two ways to use it, same entry:

  * **No reference video** → plain text → video. Type a prompt and generate;
    POSTed to ``/v1/videos`` and the clip is downloaded onto the timeline.
  * **A reference video strip selected** → motion / structure control. The
    reference's camera/subject motion drives a freshly generated scene (the
    prompt sets the new look); the reference is uploaded and the request carries
    ``control_file_id`` + ``control_type``.

No local GPU is needed — set the backend URL in add-on preferences and pick the
specific backend model in the panel's Backend Model menu.
"""

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...utils.helpers import solve_path, clean_filename
from ...models.remote_client import CineloomRemoteClient, RemoteConfig

# control_strength for motion control: low enough to follow structure without
# tracing it literally (verified value).
_CONTROL_STRENGTH = 0.2


class CineloomRemoteVideoPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/ltx-2.3"
    DISPLAY_NAME = "Cineloom Remote · Video (GPU server)"
    MODEL_TYPE   = "video"
    DESCRIPTION  = (
        "Text → video on your remote backend. Optionally select a reference "
        "video strip to drive the motion/structure (IC-LoRA control). No local "
        "GPU needed; set the URL in preferences and pick the Backend Model."
    )

    # Inputs are optional and select the mode: a reference video → motion
    # control; a source image → image2video; neither → text2video.
    INPUTS      = InputSpec.PROMPT | InputSpec.NEG_PROMPT | InputSpec.VIDEO | InputSpec.IMAGE
    UI_SECTIONS = [
        UISection.PROMPT, UISection.NEG_PROMPT, UISection.VIDEO_STRIP, UISection.IMAGE_STRIP,
        UISection.RESOLUTION, UISection.FRAMES, UISection.STEPS, UISection.SEED,
    ]
    PARAMS = ParamSpec(width=768, height=1280, frames=121, steps=8, guidance=1.0, strength=1.0)
    REQUIRED_PACKAGES: list = []

    requires_input_strip = False     # the reference video is optional
    supports_inpaint     = False
    supports_img2img     = False

    def load(self, prefs, scene, **kwargs):
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        self.set_phase(inputs, "Preparing request")
        payload = {
            "prompt": inputs.prompt,
            "negative_prompt": inputs.neg_prompt or "blurry, low quality, distorted, watermark, text",
            "width": (inputs.width // 32) * 32,
            "height": (inputs.height // 32) * 32,
            "num_frames": int(inputs.frames),
            "fps": float(inputs.fps) if inputs.fps else 24.0,
            "num_inference_steps": int(inputs.steps) or 8,
            "guidance_scale": float(inputs.guidance) or 1.0,
            "seed": int(inputs.seed),
        }
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        if model:
            payload["model"] = model
        dst_path = solve_path(
            clean_filename(f"remote_{inputs.seed}_{inputs.prompt}") + ".mp4"
        )

        def _phase(label: str) -> None:
            self.set_phase(inputs, label)

        def _progress(done: int, total: int) -> None:
            if inputs.progress_fn is not None:
                inputs.progress_fn(done, total)

        # A reference video strip → motion/structure control.
        if inputs.video_path:
            payload["control_type"] = (getattr(scene, "cineloom_control_type", "") or "canny")
            payload["control_strength"] = _CONTROL_STRENGTH
            return client.generate_control(
                inputs.video_path, payload, dst_path, phase_fn=_phase, progress_fn=_progress
            )

        # A source image → image2video. The backend wants the image uploaded as
        # a reference file (reference_file_id), not inlined.
        if inputs.image is not None:
            import os
            import tempfile
            from io import BytesIO
            _phase("Uploading source image")
            buf = BytesIO()
            inputs.image.convert("RGB").save(buf, format="PNG")
            fid = client.upload_file("source.png", buf.getvalue(), purpose="reference")
            payload["reference_file_id"] = fid

        return client.generate_video(
            payload, dst_path, phase_fn=_phase, progress_fn=_progress
        )
