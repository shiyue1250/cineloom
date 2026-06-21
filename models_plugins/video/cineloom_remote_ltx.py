"""
Cineloom Remote · Video (remote backend)
========================================

The single video bridge. You pick a video **model** (the name tells you what it
does — text2video, image2video, storyboard, first→last frame, …); Cineloom reads
that model's modes and automatically drives the right inputs and request:

  * storyboard model → a shot list → continuous multi-shot video
  * first→last-frame model → two image pickers → interpolation
  * a reference **video** strip selected → motion / structure control
  * a source **image** strip selected → image2video
  * otherwise → text2video

All over the OpenAI `/v1` dialect. Set the backend URL in preferences.
"""

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...utils.helpers import solve_path, clean_filename
from ...models.remote_client import CineloomRemoteClient, RemoteConfig

_CONTROL_STRENGTH = 0.2


def _modes(scene):
    from ...ui.cineloom_jobs import model_modes
    return model_modes((getattr(scene, "cineloom_backend_model", "") or "").strip())


class CineloomRemoteVideoPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/video"
    DISPLAY_NAME = "Cineloom Remote · Video"
    MODEL_TYPE   = "video"
    BACKEND_MODES = {"t2v", "i2v", "control", "storyboard", "flf"}
    DESCRIPTION  = (
        "Video generation on a remote backend. Pick a model; Cineloom adapts the "
        "inputs to it (text2video, image2video, storyboard, first→last frame, "
        "motion control). No local GPU needed; set the URL in preferences."
    )

    INPUTS      = InputSpec.PROMPT | InputSpec.NEG_PROMPT | InputSpec.VIDEO | InputSpec.IMAGE
    UI_SECTIONS = [
        UISection.PROMPT, UISection.NEG_PROMPT, UISection.VIDEO_STRIP, UISection.IMAGE_STRIP,
        UISection.RESOLUTION, UISection.FRAMES, UISection.STEPS, UISection.SEED,
    ]
    PARAMS = ParamSpec(width=768, height=1280, frames=121, steps=8, guidance=1.0, strength=1.0)
    REQUIRED_PACKAGES: list = []
    requires_input_strip = False
    supports_inpaint     = False
    supports_img2img     = False

    def draw_post_seed_ui(self, col, context):
        modes = _modes(context.scene)
        if "flf" in modes:
            box = col.box()
            box.label(text="Frames to interpolate:", icon="IMAGE_DATA")
            box.prop(context.scene, "cineloom_flf_first")
            box.prop(context.scene, "cineloom_flf_last")
            return
        # Storyboard-capable models (i2v variants / storyboard) → a shot list.
        # Leave it empty to generate a single clip instead.
        if modes & {"storyboard", "i2v"}:
            box = col.box()
            box.label(text="Storyboard shots (empty = single clip):", icon="SEQUENCE")
            box.prop(context.scene, "cineloom_sb_size", text="Aspect")
            for i, sh in enumerate(context.scene.cineloom_shots):
                sb = box.box()
                hdr = sb.row(align=True)
                hdr.label(text="Shot %d" % (i + 1))
                hdr.prop(sh, "source", text="")
                hdr.operator("cineloom.shot_remove", text="", icon="X").index = i
                sb.prop(sh, "prompt", text="Motion")
                row = sb.row(align=True)
                row.prop(sh, "seconds", text="Sec")
                row.prop(sh, "transition", text="")
                if sh.source == "new_scene":
                    sb.prop(sh, "scene_prompt", text="Scene")
                    sb.prop(sh, "scene_image", text="Scene img")
                sb.prop(sh, "last_frame", text="Last frame")
                sb.prop(sh, "narration", text="Narration")
            box.operator("cineloom.shot_add", text="Add Shot", icon="ADD")

    def load(self, prefs, scene, **kwargs):
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        self.set_phase(inputs, "Preparing request")
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        modes = _modes(scene)
        dst_path = solve_path(clean_filename(f"remote_{inputs.seed}_{inputs.prompt}") + ".mp4")

        def _phase(label: str) -> None:
            self.set_phase(inputs, label)

        def _progress(done: int, total: int) -> None:
            if inputs.progress_fn is not None:
                inputs.progress_fn(done, total)

        # Shots present (on a storyboard-capable model) → continuous multi-shot.
        shot_items = [s for s in scene.cineloom_shots if s.prompt.strip()]
        if shot_items and (modes & {"storyboard", "i2v"}):
            import os
            import bpy

            def _upload(path):
                ap = bpy.path.abspath(path or "")
                if ap and os.path.isfile(ap):
                    with open(ap, "rb") as fh:
                        return client.upload_file(os.path.basename(ap), fh.read(), purpose="reference")
                return None

            self.set_phase(inputs, "Preparing shots")
            shots = []
            for s in shot_items:
                shot = {"prompt": s.prompt, "seconds": float(s.seconds),
                        "source": s.source, "transition": s.transition}
                if s.narration.strip():
                    shot["narration"] = s.narration
                if s.source == "new_scene":
                    if s.scene_prompt.strip():
                        shot["scene_prompt"] = s.scene_prompt
                    sid = _upload(s.scene_image)
                    if sid:
                        shot["scene_image"] = sid
                lid = _upload(s.last_frame)
                if lid:
                    shot["last_frame"] = lid
                shots.append(shot)
            payload = {
                "first_frame_prompt": inputs.prompt,
                "shots": shots,
                "size": getattr(scene, "cineloom_sb_size", "16:9"),
                "seed": int(inputs.seed),
            }
            if model:                       # the selected model is the shot_model
                payload["model"] = model
            return client.generate_storyboard(payload, dst_path, phase_fn=_phase, progress_fn=_progress)

        # Per the backend's /v1/videos schema: frame count is `length` (8n+1);
        # width/height apply to t2v only (i2v follows the source image); the
        # backend video pipeline has no steps/guidance knobs.
        base = {
            "prompt": inputs.prompt,
            "negative_prompt": inputs.neg_prompt or "blurry, low quality, distorted, watermark, text",
            "width": (inputs.width // 32) * 32,
            "height": (inputs.height // 32) * 32,
            "length": int(inputs.frames),
            "fps": float(inputs.fps) if inputs.fps else 24.0,
            "seed": int(inputs.seed),
        }
        if model:
            base["model"] = model

        # First→last frame model → interpolate between two images.
        if "flf" in modes:
            import os
            import bpy
            first = bpy.path.abspath(getattr(scene, "cineloom_flf_first", "") or "")
            last = bpy.path.abspath(getattr(scene, "cineloom_flf_last", "") or "")
            if not (os.path.isfile(first) and os.path.isfile(last)):
                raise RuntimeError("Pick both a first-frame and a last-frame image for this model.")
            _phase("Uploading frames")
            with open(first, "rb") as fh:
                base["reference_file_id"] = client.upload_file(os.path.basename(first), fh.read(), purpose="reference")
            with open(last, "rb") as fh:
                base["last_frame_file_id"] = client.upload_file(os.path.basename(last), fh.read(), purpose="reference")
            return client.generate_video(base, dst_path, phase_fn=_phase, progress_fn=_progress)

        # A reference video strip → motion / structure control.
        if inputs.video_path:
            base["control_type"] = (getattr(scene, "cineloom_control_type", "") or "canny")
            base["control_strength"] = _CONTROL_STRENGTH
            return client.generate_control(inputs.video_path, base, dst_path, phase_fn=_phase, progress_fn=_progress)

        # A source image → image2video (uploaded as a reference file).
        if inputs.image is not None:
            from io import BytesIO
            _phase("Uploading source image")
            buf = BytesIO()
            inputs.image.convert("RGB").save(buf, format="PNG")
            base["reference_file_id"] = client.upload_file("source.png", buf.getvalue(), purpose="reference")
            return client.generate_video(base, dst_path, phase_fn=_phase, progress_fn=_progress)

        # Text → video.
        return client.generate_video(base, dst_path, phase_fn=_phase, progress_fn=_progress)
