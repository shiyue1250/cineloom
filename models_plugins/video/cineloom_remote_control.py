"""
Cineloom Remote · Motion Control (IC-LoRA Union-Control)
========================================================

Generate a new scene that **follows a reference video's motion and structure**.
Select a VIDEO strip as the reference; the add-on uploads it to the backend
(`POST /v1/files`) and submits `POST /v1/videos` with `control_file_id` +
`control_type` + `control_strength`. The backend extracts the control sequence
and generates with structure/motion control. The prompt decides what the new
scene looks like; the reference decides how the camera/subject moves.

Examples: a real drone canyon clip → a new stylised canyon flythrough that
follows the same flight path; a dance clip → a different character doing the same
moves. Uses the main Remote Backend URL — control rides on `/v1/videos`.
"""

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...utils.helpers import solve_path, clean_filename
from ...models.remote_client import CineloomRemoteClient, RemoteConfig


class CineloomRemoteControlPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/control"
    DISPLAY_NAME = "Cineloom Remote · Motion Control (IC-LoRA)"
    MODEL_TYPE   = "video"
    DESCRIPTION  = (
        "Generate a new scene that follows a reference video's motion/structure "
        "(remote, via /v1/videos control). Select a video strip as the reference; "
        "the prompt sets the new look. Uses the Remote Backend URL in preferences."
    )

    INPUTS      = InputSpec.PROMPT | InputSpec.NEG_PROMPT | InputSpec.VIDEO
    UI_SECTIONS = [
        UISection.PROMPT, UISection.NEG_PROMPT, UISection.VIDEO_STRIP,
        UISection.RESOLUTION, UISection.FRAMES, UISection.IMAGE_STRENGTH, UISection.SEED,
    ]
    # Portrait default matches typical phone reference clips; control_strength 0.2
    # (mapped from the strength slider) follows structure without copying it.
    PARAMS = ParamSpec(width=576, height=1024, frames=97, strength=0.2)
    REQUIRED_PACKAGES: list = []

    requires_input_strip = True     # always needs the reference video strip
    supports_inpaint     = False
    supports_img2img     = False
    uses_strip_power     = False

    def load(self, prefs, scene, **kwargs):
        # Control rides on the main backend's /v1/videos — same Remote Backend URL.
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        if not inputs.video_path:
            raise RuntimeError(
                "Select a VIDEO strip as the motion-control reference, then Generate."
            )
        self.set_phase(inputs, "Preparing request")
        payload = {
            "prompt": inputs.prompt,
            "negative_prompt": inputs.neg_prompt or "blurry, low quality, distorted, watermark, text",
            "control_type": "canny",        # canny | depth | pose (backend capability)
            "control_strength": float(inputs.strength),
            "width": (inputs.width // 32) * 32,
            "height": (inputs.height // 32) * 32,
            "num_frames": int(inputs.frames),
            "seed": int(inputs.seed),
        }
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        if model:
            payload["model"] = model        # the discovered model picked in the panel
        dst_path = solve_path(
            clean_filename(f"control_{inputs.seed}_{inputs.prompt}") + ".mp4"
        )

        def _phase(label: str) -> None:
            self.set_phase(inputs, label)

        def _progress(done: int, total: int) -> None:
            if inputs.progress_fn is not None:
                inputs.progress_fn(done, total)

        return client.generate_control(
            inputs.video_path, payload, dst_path, phase_fn=_phase, progress_fn=_progress
        )
