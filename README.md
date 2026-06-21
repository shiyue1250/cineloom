# Cineloom

Cineloom is a **Blender Video Sequence Editor add-on** that connects any
**OpenAI-SDK-compatible** generation backend (image / video / audio) into
Blender, so you can generate AI media and edit it on the timeline — all in one
place. Forked from [Pallaidium](https://github.com/tin2tin/Pallaidium)
(GPL-3.0-or-later).

It is a **bridge**, not an engine: Cineloom does not run models itself. You point
it at a backend that speaks the OpenAI `/v1` API — your own self-hosted GPU
service, or any online provider — and Cineloom translates between that API and
Blender's editor. The generation can live anywhere; the editing stays native on
your machine.

English · [中文](README.zh-CN.md)

![Blender 5.2+](https://img.shields.io/badge/Blender-5.2%2B-orange)
![License GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue)
![Any platform](https://img.shields.io/badge/Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-supported-5ad571)

## How it works

```
Blender (Windows / macOS / Linux, your machine)
  + Cineloom add-on
        │  OpenAI /v1  (HTTP)
        ▼
Any OpenAI-SDK-compatible backend
  - self-hosted GPU service, or
  - an online API provider
        │
   generate image / video / audio
        ▼
  result lands on the VSE timeline → edit, cut, export
```

- **Editing is local and native** — no remote desktop, no GPU needed on the
  editing machine.
- **Generation is remote** — wherever your backend runs.
- **Backend-agnostic** — anything that implements the OpenAI `/v1` dialect works.

## Install

1. Install Blender 5.2+ on your machine (Windows, macOS or Linux).
2. Clone this repo and install the add-on:
   `Edit ▸ Preferences ▸ Add-ons ▸ Install from Disk` → select the repo folder
   (or build a zip: `blender --command extension build`).
3. In **Edit ▸ Preferences ▸ Add-ons ▸ Cineloom**, set:
   - **Remote Backend URL** — e.g. `http://your-backend-host:PORT`
   - **API Key** — optional, sent as `Bearer` / `X-API-Key` / `?api_key`

The remote add-on code uses only the Python standard library, so no extra
packages are needed for the bridge to work on any OS.

## Backend API (the integration format)

Cineloom speaks the **OpenAI `/v1` dialect**. Any backend implementing these
endpoints can be used. Full request/response examples and the versioned contract
are in [`docs/BACKEND_CONTRACT.md`](docs/BACKEND_CONTRACT.md).

| Capability | Endpoint |
|---|---|
| Discover available models | `GET /v1/models` |
| Text/image → video | `POST /v1/videos` |
| Text → image | `POST /v1/images/generations` |
| Text → speech | `POST /v1/audio/speech` |
| Transcription (ASR) | `POST /v1/audio/transcriptions` |
| Upload a reference / control file | `POST /v1/files` |
| Poll an async job | `GET /v1/jobs/{id}` |
| Fetch a result | `GET /v1/files/{id}` |

Example — text-to-video request:

```http
POST /v1/videos
Content-Type: application/json

{ "model": "<from /v1/models>", "prompt": "a lighthouse in a storm at night",
  "width": 768, "height": 1280, "num_frames": 121, "seed": 7 }
```

→ `{ "id": "job_abc", "status": "queued" }` → poll `GET /v1/jobs/job_abc` →
download `GET /v1/files/<file_id>`.

## Capability coverage

Cineloom aims to cover, over the OpenAI `/v1` bridge, the generation types the
upstream Pallaidium add-on does locally. Status is tracked in
[`docs/CAPABILITIES.md`](docs/CAPABILITIES.md) — verified items are marked done;
the rest are the to-verify list.

> Cineloom also inherits Pallaidium's local-model plugins, which run on a GPU on
> the editing machine. Those still work if you have a local GPU, but the bridge
> (remote, any-OS, no local GPU) is the focus.

## Privacy & keys

Cineloom is a **local Blender add-on** — it runs entirely on your machine and
sends requests only to the backend URL you configure. The API key is stored in
your local Blender preferences (`userpref`) and is never uploaded anywhere by the
add-on. Treat that file as you would any local credential store.

## License & attribution

GPL-3.0-or-later, inherited from [Pallaidium](https://github.com/tin2tin/Pallaidium)
by *tintwotin*. Any distributed derivative stays open under the same license.
See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md); the original upstream readme
is preserved at [README.upstream.md](README.upstream.md).

Cineloom distributes code only, never model weights or backend services. Each
model carries its own license and is provided by whatever backend you connect to.
