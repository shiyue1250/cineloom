"""
Cineloom Remote · text → image (self-hosted remote backend)
===========================================================

Generate reference frames / stills on a remote backend via
``POST /v1/images/generations``. Returns the downloaded PNG file path (the
queue inserts it as an image strip) — no local image library required, keeping
the bridge stdlib-only.
"""

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...models.remote_client import CineloomRemoteClient, RemoteConfig
from ...utils.helpers import solve_path, clean_filename


class CineloomRemoteImagePlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/image"
    DISPLAY_NAME = "Cineloom Remote · Image (GPU server)"
    MODEL_TYPE   = "image"
    BACKEND_MODES = {"t2i", "i2i"}
    DESCRIPTION  = (
        "Text → image on your remote GPU backend (the bundled Cineloom server "
        "or any OpenAI-compatible /v1 endpoint). No local GPU needed. Set the "
        "URL in add-on preferences."
    )

    INPUTS      = InputSpec.PROMPT | InputSpec.NEG_PROMPT
    UI_SECTIONS = [
        UISection.PROMPT, UISection.NEG_PROMPT, UISection.RESOLUTION,
        UISection.STEPS, UISection.GUIDANCE, UISection.SEED,
    ]
    PARAMS = ParamSpec(width=1024, height=1024, steps=20, guidance=4.0)
    REQUIRED_PACKAGES: list = []
    supports_inpaint = False
    supports_img2img = False

    def load(self, prefs, scene, **kwargs):
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs):
        self.set_phase(inputs, "Preparing request")
        payload = {
            "prompt": inputs.prompt,
            "negative_prompt": inputs.neg_prompt,
            "width": int(inputs.width),
            "height": int(inputs.height),
            "num_inference_steps": int(inputs.steps),
            "guidance_scale": float(inputs.guidance),
            "seed": int(inputs.seed),
        }
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        if model:
            payload["model"] = model

        dst_path = solve_path(
            clean_filename(f"remote_img_{inputs.seed}_{inputs.prompt}") + ".png"
        )

        def _phase(label: str) -> None:
            self.set_phase(inputs, label)

        return client.generate_image(payload, dst_path, phase_fn=_phase)
