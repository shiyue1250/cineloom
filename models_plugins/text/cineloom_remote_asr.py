"""
Cineloom Remote · Transcribe (ASR)
==================================

Speech-to-text on a remote backend via ``POST /v1/audio/transcriptions``
(OpenAI format). Select a sound (or video) strip; its transcript is inserted as
a text strip. Pick the backend ASR model in the panel's Model menu.
"""

import os

from ...models.base import ModelPlugin, InputSpec, ModelInputs
from ...models.remote_client import CineloomRemoteClient, RemoteConfig


class CineloomRemoteASRPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/asr"
    DISPLAY_NAME = "Cineloom Remote · Transcribe (ASR)"
    MODEL_TYPE   = "text"
    DESCRIPTION  = (
        "Transcribe a selected sound/video strip on a remote backend "
        "(OpenAI /v1/audio/transcriptions). The transcript becomes a text strip."
    )

    INPUTS      = InputSpec(0)        # the plugin reads the selected strip's audio
    UI_SECTIONS: list = []
    REQUIRED_PACKAGES: list = []
    requires_input_strip = True
    supports_batch = False

    def load(self, prefs, scene, **kwargs):
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        path = inputs.audio_ref or inputs.video_path
        if not path or not os.path.isfile(path):
            raise RuntimeError("Select a sound or video strip to transcribe.")
        self.set_phase(inputs, "Transcribing")
        with open(path, "rb") as fh:
            content = fh.read()
        # The text Model menu holds chat models; ASR uses the backend's default
        # transcription model, so we don't pass one here.
        return client.transcribe(os.path.basename(path), content, "")
