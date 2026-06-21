"""
Cineloom Remote · text → speech (self-hosted remote backend)
============================================================

Text-to-speech on your remote GPU backend via ``POST /v1/audio/speech``.
Returns a .wav path (the framework inserts it as a SOUND strip), matching the
local audio-plugin contract. Works against any OpenAI-compatible ``/v1`` TTS
endpoint you run.
"""

from ...models.base import ModelPlugin, InputSpec, UISection, ParamSpec, ModelInputs
from ...utils.helpers import solve_path, clean_filename
from ...models.remote_client import CineloomRemoteClient, RemoteConfig


class CineloomRemoteTTSPlugin(ModelPlugin):
    MODEL_ID     = "cineloom-remote/tts"
    DISPLAY_NAME = "Cineloom Remote · TTS (GPU server)"
    MODEL_TYPE   = "audio"
    DESCRIPTION  = (
        "Text → speech on your remote GPU backend (any OpenAI-compatible /v1 "
        "TTS endpoint). No local GPU needed. Set the URL in add-on preferences."
    )

    INPUTS      = InputSpec.PROMPT | InputSpec.AUDIO_REF
    UI_SECTIONS = [
        UISection.PROMPT, UISection.AUDIO_REF, UISection.SPEED, UISection.SEED,
    ]
    PARAMS = ParamSpec(audio_length=5.0)
    REQUIRED_PACKAGES: list = []
    supports_batch = False

    def load(self, prefs, scene, **kwargs):
        client = CineloomRemoteClient(RemoteConfig.from_prefs(prefs))
        client.health()
        return client

    def generate(self, client: CineloomRemoteClient, inputs: ModelInputs, scene, prefs) -> str:
        self.set_phase(inputs, "Preparing request")
        payload = {
            "input": inputs.prompt,
            "speed": float(inputs.speed) if inputs.speed else 1.0,
            "response_format": "wav",
        }
        # Voice is backend/model-specific; omit it so the backend uses its default
        # unless the user set one. (Sending an unknown voice id is a 400.)
        voice = (getattr(scene, "cineloom_tts_voice", "") or "").strip()
        if voice:
            payload["voice"] = voice
        model = (getattr(scene, "cineloom_backend_model", "") or "").strip()
        if model:
            payload["model"] = model

        # Optional speaker reference for voice cloning, uploaded if provided.
        if inputs.audio_ref:
            try:
                with open(inputs.audio_ref, "rb") as fh:
                    ref_id = client.upload_file(
                        "speaker_ref.wav", fh.read(), purpose="speaker_reference"
                    )
                payload["speaker_reference_id"] = ref_id
            except OSError:
                pass

        dst_path = solve_path(
            clean_filename(f"remote_tts_{inputs.seed}_{inputs.prompt}") + ".wav"
        )

        def _phase(label: str) -> None:
            self.set_phase(inputs, label)

        return client.generate_speech(payload, dst_path, phase_fn=_phase)
