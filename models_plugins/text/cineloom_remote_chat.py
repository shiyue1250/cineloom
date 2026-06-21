"""
Cineloom Remote · Text (remote backend)
=======================================

The single text bridge. Cineloom routes by what you give it:

  * a selected sound / video strip → transcription (ASR,
    ``POST /v1/audio/transcriptions``) → the transcript becomes a text strip
  * otherwise → chat / text generation (``POST /v1/chat/completions``) from the
    prompt

Pick a chat model for generation; transcription uses the backend's default ASR
model. All over the OpenAI `/v1` dialect.
"""

import os

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...models.remote_client import CineloomRemoteClient, RemoteConfig


class CineloomRemoteTextPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/text"
    DISPLAY_NAME = "Cineloom Remote · Text"
    MODEL_TYPE   = "text"
    BACKEND_MODES = {"chat", "asr"}
    DESCRIPTION  = (
        "Text on a remote backend: type a prompt to generate text, or select a "
        "sound/video strip to transcribe it. OpenAI /v1."
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
        # A selected sound / video strip → transcription.
        audio = inputs.audio_ref or inputs.video_path
        if audio and os.path.isfile(audio):
            self.set_phase(inputs, "Transcribing")
            with open(audio, "rb") as fh:
                return client.transcribe(os.path.basename(audio), fh.read(), "")

        # Otherwise generate text from the prompt.
        self.set_phase(inputs, "Generating")
        payload = {"messages": [{"role": "user", "content": inputs.prompt}]}
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        if model:
            payload["model"] = model
        return client.chat(payload)
