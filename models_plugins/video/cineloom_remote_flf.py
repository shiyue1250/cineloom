"""
Cineloom Remote · First → Last Frame
====================================

Interpolate a video between two still images. Pick a first-frame and a
last-frame image; the backend morphs from one to the other (the prompt guides
the motion). Both images are uploaded; the request carries ``reference_file_id``
(first) and ``last_frame_file_id`` (last).
"""

import os

import bpy

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...utils.helpers import solve_path, clean_filename
from ...models.remote_client import CineloomRemoteClient, RemoteConfig


class CineloomRemoteFLFPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/flf"
    DISPLAY_NAME = "Cineloom Remote · First→Last Frame"
    MODEL_TYPE   = "video"
    BACKEND_MODES = {"flf"}
    DESCRIPTION  = (
        "Interpolate a video between a first-frame and a last-frame image "
        "(prompt guides the motion). Pick the two images below."
    )

    INPUTS      = InputSpec.PROMPT
    UI_SECTIONS = [UISection.PROMPT, UISection.RESOLUTION, UISection.FRAMES, UISection.SEED]
    PARAMS = ParamSpec(width=768, height=1280, frames=121)
    REQUIRED_PACKAGES: list = []
    requires_input_strip = False
    supports_inpaint     = False

    def draw_post_seed_ui(self, col, context):
        box = col.box()
        box.label(text="Frames to interpolate:", icon="IMAGE_DATA")
        box.prop(context.scene, "cineloom_flf_first")
        box.prop(context.scene, "cineloom_flf_last")

    def load(self, prefs, scene, **kwargs):
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        first = bpy.path.abspath(getattr(scene, "cineloom_flf_first", "") or "")
        last = bpy.path.abspath(getattr(scene, "cineloom_flf_last", "") or "")
        if not (os.path.isfile(first) and os.path.isfile(last)):
            raise RuntimeError("Pick both a first-frame and a last-frame image.")
        self.set_phase(inputs, "Uploading frames")
        with open(first, "rb") as fh:
            fid_first = client.upload_file(os.path.basename(first), fh.read(), purpose="reference")
        with open(last, "rb") as fh:
            fid_last = client.upload_file(os.path.basename(last), fh.read(), purpose="reference")

        payload = {
            "prompt": inputs.prompt,
            "negative_prompt": inputs.neg_prompt or "blurry, low quality",
            "reference_file_id": fid_first,
            "last_frame_file_id": fid_last,
            "width": (inputs.width // 32) * 32,
            "height": (inputs.height // 32) * 32,
            "num_frames": int(inputs.frames),
            "fps": float(inputs.fps) if inputs.fps else 24.0,
            "num_inference_steps": int(inputs.steps) or 8,
            "seed": int(inputs.seed),
        }
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        if model:
            payload["model"] = model
        dst_path = solve_path(
            clean_filename(f"flf_{inputs.seed}_{inputs.prompt}") + ".mp4"
        )

        def _phase(label: str) -> None:
            self.set_phase(inputs, label)

        def _progress(done: int, total: int) -> None:
            if inputs.progress_fn is not None:
                inputs.progress_fn(done, total)

        return client.generate_video(
            payload, dst_path, phase_fn=_phase, progress_fn=_progress
        )
