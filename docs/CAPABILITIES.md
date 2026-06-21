# Cineloom — Capability Coverage

Cineloom bridges generation **capabilities** to Blender over the OpenAI `/v1`
contract ([`BACKEND_CONTRACT.md`](BACKEND_CONTRACT.md)). A capability is
**verified** once it has been exercised end-to-end through the bridge against a
compatible backend.

## Video

- [x] Text → video
- [x] Image → video (uploads the source as a reference file)
- [x] Motion / structure control from a reference video — **Canny** (selectable
      Canny / Depth / Pose; depth & pose need backend preprocessors)
- [x] Continuous long video (segment chaining, seamless)
- [x] First/last-frame interpolation (flf) — two image pickers → `reference_file_id`
      + `last_frame_file_id`
- [x] Storyboard (multi-shot continuous video) — shot-list editor → `/v1/storyboard`
- [ ] Subject / identity-conditioned video
- [ ] Lip-sync
- [ ] Video super-resolution

## Image

- [x] Text → image
- [ ] Image → image
- [ ] ControlNet — Canny / Depth
- [ ] Inpaint / image edit
- [ ] Relight
- [ ] Background removal

## Audio

- [x] Text → speech (TTS)
- [ ] Voice cloning (speaker reference)
- [ ] Music generation
- [ ] Video → audio (foley)
- [ ] Stem separation

## Text

- [x] Text generation / chat (`/v1/chat/completions`)
- [x] Transcription → text (ASR, `/v1/audio/transcriptions`)
- [ ] Image / video captioning
- [ ] Prompt enhancement / rewriting

---

Picker hygiene: the Model menu shows only models whose `modes` the add-on can
drive (video = t2v/i2v/control, image = t2i, audio = tts, text = chat/asr);
others are hidden until handled. The Engine picker appears when a type has
several remote engines (text = chat + ASR).

**Local fallback.** Cineloom also inherits Pallaidium's local-model plugins,
available when "Show local models" is enabled in preferences.
