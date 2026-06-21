"""
Cineloom Remote · Storyboard (continuous multi-shot video)
==========================================================

Generate one continuous video from several shots. The main prompt describes the
opening frame; each shot below has its own prompt and duration. The backend
chains them into a seamless clip (``POST /v1/storyboard`` → poll → content).

Pick a storyboard-capable backend model in the panel (e.g. ltx-storyboard-msr or
a sulphur i2v variant).
"""

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...utils.helpers import solve_path, clean_filename
from ...models.remote_client import CineloomRemoteClient, RemoteConfig


class CineloomRemoteStoryboardPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/storyboard"
    DISPLAY_NAME = "Cineloom Remote · Storyboard (continuous)"
    MODEL_TYPE   = "video"
    BACKEND_MODES = {"storyboard", "i2v"}
    DESCRIPTION  = (
        "Continuous multi-shot video. The prompt sets the opening frame; add "
        "shots below, each with its own prompt and seconds. Pick a storyboard "
        "model (e.g. ltx-storyboard-msr)."
    )

    INPUTS      = InputSpec.PROMPT
    UI_SECTIONS = [UISection.PROMPT, UISection.SEED]
    PARAMS = ParamSpec()
    REQUIRED_PACKAGES: list = []
    requires_input_strip = False
    supports_inpaint     = False

    def draw_post_seed_ui(self, col, context):
        box = col.box()
        box.label(text="Shots (continuous):", icon="SEQUENCE")
        shots = context.scene.cineloom_shots
        for i, sh in enumerate(shots):
            row = box.row(align=True)
            row.prop(sh, "prompt", text="")
            row.prop(sh, "seconds", text="")
            row.operator("cineloom.shot_remove", text="", icon="X").index = i
        box.operator("cineloom.shot_add", text="Add Shot", icon="ADD")

    def load(self, prefs, scene, **kwargs):
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        shots = [
            {"prompt": s.prompt, "seconds": float(s.seconds)}
            for s in scene.cineloom_shots if s.prompt.strip()
        ]
        if not shots:
            raise RuntimeError(
                "Add at least one shot ('Add Shot'), each with a prompt."
            )
        payload = {"first_frame_prompt": inputs.prompt, "shots": shots}
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        if model:
            payload["model"] = model
        dst_path = solve_path(
            clean_filename(f"storyboard_{inputs.seed}_{inputs.prompt}") + ".mp4"
        )

        def _phase(label: str) -> None:
            self.set_phase(inputs, label)

        def _progress(done: int, total: int) -> None:
            if inputs.progress_fn is not None:
                inputs.progress_fn(done, total)

        return client.generate_storyboard(
            payload, dst_path, phase_fn=_phase, progress_fn=_progress
        )
