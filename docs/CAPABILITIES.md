# Cineloom — Capability Coverage

Cineloom bridges generation **capabilities** to Blender over the OpenAI `/v1`
contract ([`BACKEND_CONTRACT.md`](BACKEND_CONTRACT.md)). The goal is to cover the
generation types the upstream Pallaidium add-on does locally, but as a backend-
agnostic bridge.

A capability is **verified** once it has been exercised end-to-end through the
bridge against a compatible backend. Unchecked items are the to-verify list.
(The specific *models* behind each capability are the backend's to provide;
Cineloom bridges the capability.)

## Video

- [x] Text → video
- [x] Image → video (first-frame condition)
- [x] Motion / structure control from a reference video — **Canny**
- [x] Continuous long video (segment chaining, seamless)
- [ ] Depth control
- [ ] Pose / OpenPose control (e.g. swap a character onto a reference's motion)
- [ ] Subject / identity-conditioned video
- [ ] Lip-sync
- [ ] Video super-resolution

## Image

- [x] Text → image
- [ ] Image → image
- [ ] ControlNet — Canny
- [ ] ControlNet — Depth
- [ ] Inpaint / image edit
- [ ] Relight
- [ ] Background removal
- [ ] Multi-image composition

## Audio

- [x] Text → speech (TTS)
- [ ] Voice cloning (speaker reference)
- [ ] Music generation
- [ ] Video → audio (foley)
- [ ] Stem separation

## Text

- [ ] Transcription → subtitle strips (ASR)
- [ ] Image / video captioning
- [ ] Prompt enhancement / rewriting

---

**Local fallback.** Cineloom also inherits Pallaidium's local-model plugins
(~40 models across the types above) that run on a GPU on the editing machine.
They remain available for users with a local GPU, but are independent of the
remote bridge tracked here. See the upstream
[Generation Matrix](../README.upstream.md) for that local roster.
