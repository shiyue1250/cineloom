# Cineloom Backend Contract — `v0.1`

This is the API a backend must implement so the Cineloom add-on can drive it. It
follows the **OpenAI `/v1` dialect**. Any service that satisfies this contract —
self-hosted or online — can be used as a Cineloom backend; Cineloom mentions no
specific provider.

The contract is **versioned**. Cineloom announces the version it expects; a
backend may advertise the versions it supports via `GET /v1/health`.

## Conventions

- Base URL: `http://<host>:<port>` — the user configures this.
- **Auth** (optional): the add-on sends the key three ways; accept any one:
  `Authorization: Bearer <key>`, `X-API-Key: <key>`, or `?api_key=<key>`.
- **Async jobs**: heavy generations return `{ "id": "<job_id>", "status": "queued" }`.
  The add-on polls `GET /v1/jobs/{id}` until a terminal status, then downloads the
  artifact. A backend may instead answer synchronously with a direct
  `url` / `file_id` — the add-on handles both.
- Times in seconds, sizes `/32`-aligned, `num_frames` as `8n+1` where relevant.

## `GET /v1/health`

```json
{ "status": "ok", "contract_versions": ["v0.1"] }
```

## `GET /v1/models` — discovery (required)

The add-on calls this on connect and periodically, to populate the model list.

```json
{ "data": [
  { "id": "ltx-video",  "type": "video", "modes": ["t2v", "i2v", "control"] },
  { "id": "flux",       "type": "image", "modes": ["t2i", "i2i"] },
  { "id": "tts-voice",  "type": "audio", "modes": ["tts"] },
  { "id": "asr",        "type": "text",  "modes": ["transcription"] }
] }
```

- `type` ∈ `video | image | audio | text`.
- `modes` is optional metadata; `control` signals motion/structure control support.

## `POST /v1/videos` — text/image → video

```json
{ "model": "ltx-video", "prompt": "...", "negative_prompt": "...",
  "width": 768, "height": 1280, "num_frames": 121, "fps": 24,
  "seed": 7, "strength": 1.0,
  "image_b64": "<base64 PNG, optional first-frame condition>" }
```

→ `{ "id": "<job_id>", "status": "queued" }`

### Motion / structure control (optional `control` mode)

To support reference-driven control (the camera motion / structure of one video
guiding a freshly generated scene), accept on `/v1/videos`:

```json
{ "model": "ltx-video", "prompt": "...",
  "control_file_id": "<id from POST /v1/files>",
  "control_type": "canny" ,            // canny | depth | pose
  "control_strength": 0.2 }
```

For **continuous long video** beyond a single clip, the backend should chain
internally (each segment continues from the previous one's last frame) and return
one seamless result. A `last-frame` accessor and/or a storyboard endpoint is a
clean way to expose this.

## `POST /v1/images/generations` — text → image

```json
{ "model": "flux", "prompt": "...", "negative_prompt": "...",
  "width": 1024, "height": 1024, "num_inference_steps": 20,
  "guidance_scale": 4.0, "seed": 0 }
```

→ async job, or `{ "data": [ { "url": "..." } ] }` (OpenAI-style).

## `POST /v1/audio/speech` — text → speech

```json
{ "model": "tts-voice", "input": "hello", "voice": "default",
  "response_format": "wav", "speed": 1.0,
  "speaker_reference_id": "<optional file_id for voice cloning>" }
```

## `POST /v1/audio/transcriptions` — ASR (multipart)

`multipart/form-data` with `file=<audio>` and `model=<id>` →
`{ "text": "..." }`.

## `POST /v1/files` — upload a reference / control file (multipart)

`multipart/form-data` with `file=<...>` and `purpose=<reference|control|speaker_reference>`
→ `{ "file_id": "<id>" }`.

## `GET /v1/jobs/{id}` — poll an async job

```json
{ "id": "<job_id>", "status": "running",
  "phase": "generating", "progress": 0.5,
  "file_id": null, "error": null }
```

- `status` ∈ `queued | running | succeeded | failed`.
- On `succeeded`, return `file_id` (and optionally `control_file_id` for the
  control map, so the add-on can show what guided the generation).
- `progress` ∈ `[0,1]`, `phase` is a free-text label shown in the UI.

## `GET /v1/files/{id}` — download an artifact

Returns the binary (e.g. `video/mp4`, `image/png`, `audio/wav`).

---

A backend only needs to implement the endpoints for the capabilities it offers;
`GET /v1/models` should advertise exactly what it supports, and Cineloom adapts.
