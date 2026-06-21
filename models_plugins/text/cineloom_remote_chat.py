"""
Cineloom Remote · Text (chat)
=============================

Text generation on a remote backend via ``POST /v1/chat/completions`` (OpenAI
chat format). Type a prompt; the assistant reply is inserted as a text strip.
Pick the backend chat model in the panel's Model menu.
"""

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...models.remote_client import CineloomRemoteClient, RemoteConfig


class CineloomRemoteChatPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/chat"
    DISPLAY_NAME = "Cineloom Remote · Text (chat)"
    MODEL_TYPE   = "text"
    BACKEND_MODES = {"chat"}
    DESCRIPTION  = (
        "Text generation on a remote backend (OpenAI /v1/chat/completions). "
        "Type a prompt; the reply becomes a text strip. Pick the backend model "
        "in the panel."
    )

    INPUTS      = InputSpec.PROMPT
    UI_SECTIONS = [UISection.PROMPT]
    PARAMS = ParamSpec()
    REQUIRED_PACKAGES: list = []
    supports_batch = False

    def load(self, prefs, scene, **kwargs):
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        self.set_phase(inputs, "Generating")
        payload = {"messages": [{"role": "user", "content": inputs.prompt}]}
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        if model:
            payload["model"] = model
        return client.chat(payload)   # str → the queue inserts it as a text strip
