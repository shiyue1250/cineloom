<h1 align="center">Cineloom</h1>

<p align="center"><b>Model-agnostic AI film-assembly workbench for the Blender Video Sequence Editor.</b><br/>
Linux-first · remote-capable · GPL-3.0.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Blender-5.2%2B-orange" alt="Blender 5.2+">
  <img src="https://img.shields.io/badge/Linux-first-5ad571" alt="Linux-first">
  <img src="https://img.shields.io/badge/License-GPL--3.0--or--later-blue" alt="GPL-3.0-or-later">
  <img src="https://img.shields.io/badge/forked%20from-Pallaidium-violet" alt="forked from Pallaidium">
</p>

<p align="center"><b>English</b> · <a href="README.zh-CN.md">中文</a></p>

<hr>

> **Cineloom is a fork of [Pallaidium](https://github.com/tin2tin/Pallaidium) by *tintwotin*** (GPL-3.0-or-later).
> It keeps Pallaidium's AI↔VSE bridge and adds three deltas: **Linux as a
> first-class citizen**, an **editing/generation decoupling** (remote GPU
> backend), and a **focused, quality-first** LTX-2.3 path. See [NOTICE.md](NOTICE.md).

You only truly understand how your film should have been made once it is
finished. Cineloom turns that insight into a workflow: generate shots with AI,
voice them, caption them, and **edit on a professional timeline** — all inside
Blender's Video Sequence Editor.

Its value is **not any single model**. Models only get stronger; Cineloom is the
**model-agnostic assembly layer** around them — generation, dubbing, subtitles,
editing, pacing, sync, export — organized into one smooth film pipeline. Models
are pluggable parts: LTX-2.3 today, the next thing tomorrow, **swap a plugin,
the framework stays.**

## Why Cineloom (the three deltas over Pallaidium)

| Delta | What it means |
|---|---|
| **① Linux, first-class** | A stable, verified dependency installer (`scripts/install_linux.sh`) replacing the fragile in-addon button, plus a proxy-aware weight downloader (`scripts/download_models.py`). Verified end-to-end on a Linux GPU server. |
| **② Editing ⇄ generation decoupled** | A **remote backend**: Blender edits on the desktop (no big GPU needed) while generation is POSTed to a GPU server. Pick a *"Cineloom Remote · …"* model and the request goes to the bundled [Cineloom server](#cineloom-generation-server-serversrc) you self-host, or **any OpenAI-compatible `/v1` endpoint** you point it at. |
| **③ Focus + quality** | A containerized LTX-2.3 generation service built from a verified `diffusers` + `sdnq` int8 stack. |

## Architecture

```
┌─ Linux desktop / workstation (has display) ─┐        ┌─ GPU server (headless) ──────────┐
│  Blender VSE + Cineloom add-on              │        │  Cineloom server  (server/)      │
│   • timeline editing · subtitles · dubbing  │  /v1   │   diffusers LTX-2.3 + sdnq int8  │
│   • "Cineloom Remote · …" models  ──────────┼──────▶ │   POST /v1/videos → mp4          │
│   • no large GPU required                   │ ◀──────┤   (or any OpenAI /v1 backend)    │
└─────────────────────────────────────────────┘ files  └──────────────────────────────────┘
```

The editing host stays light; the heavy work lives on the server. A single
preference (Remote Backend URL) switches generation from local to remote.

## Install (Linux)

### 1. Blender ≥ 5.2

Download the official Linux build (`blender-x.y-linux-x64.tar.xz`) and extract —
no system install needed.

### 2. The Cineloom add-on

Clone this repo and zip the add-on (the repo root *is* the extension; `server/`,
`scripts/`, `docs/` are excluded by `blender_manifest.toml`):

```bash
git clone https://github.com/shiyue1250/cineloom.git
# In Blender: Edit ▸ Preferences ▸ Add-ons ▸ Install from Disk ▸ select the repo folder
# (or build a .zip with: blender --command extension build)
```

### 3. Dependencies (verified recipe)

Instead of the fragile one-click button, run the installer against Blender's
bundled Python:

```bash
# Core LTX-2.3 path only (recommended to start):
scripts/install_linux.sh --blender /path/to/blender --core-only

# Behind the Great Firewall, route pip + HF through a proxy:
scripts/install_linux.sh --blender /path/to/blender --proxy http://127.0.0.1:1081

# Everything (full requirements_linux.txt):
scripts/install_linux.sh --blender /path/to/blender --full
```

Verified core stack: `torch 2.8 + cu12.8 · diffusers 0.38 · sdnq 0.2 ·
transformers 4.57 · opencv`.

### 4. Weights (proxy-aware)

```bash
# Direct (open network):
python scripts/download_models.py \
  --repo OzzyGT/LTX-2.3-Distilled-1.1-sdnq-dynamic-int8 \
  --dest ~/ai-models/ltx23-distilled-int8

# Behind a restricted network, route through your own HTTP proxy:
python scripts/download_models.py --proxy http://127.0.0.1:1081 \
  --repo OzzyGT/LTX-2.3-Distilled-1.1-sdnq-dynamic-int8 \
  --dest ~/ai-models/ltx23-distilled-int8
```

> Some networks block HuggingFace's Xet/CAS large-file transport. In that case
> point `--proxy` at your own HTTP proxy against the real `huggingface.co`
> endpoint; the downloader handles the rest.

## Remote backend

In **Edit ▸ Preferences ▸ Add-ons ▸ Cineloom**, set:

* **Remote Backend URL** — the address of *your own* backend, e.g.
  `http://your-gpu-host:8879` (the bundled Cineloom server you self-host) or any
  OpenAI-compatible `/v1` endpoint you run.
* **Remote API Key** — optional; sent as `Bearer` / `X-API-Key` / `?api_key`.

Then, in the Cineloom panel, pick a model whose name starts with **"Cineloom
Remote · …"**:

| Model | Endpoint | Output |
|---|---|---|
| Cineloom Remote · LTX-2.3 | `POST /v1/videos` | video strip |
| Cineloom Remote · Image | `POST /v1/images/generations` | image strip |
| Cineloom Remote · TTS | `POST /v1/audio/speech` | sound strip |

Generation now runs on the server; the finished file is downloaded onto the
timeline. (Local models continue to work unchanged — Cineloom only *adds* the
remote option.)

## Cineloom generation server (`server/`)

A self-contained FastAPI service wrapping the verified LTX-2.3 stack. It is
**safe for a shared host**: unique container/image/port, GPU-pinned, model
mounted read-only, nothing else touched.

```bash
cp server/.env.example server/.env      # set GPU, model path, optional API key
docker compose -f server/docker-compose.yml up -d --build
curl http://localhost:8879/health
```

* Pin a GPU with `CINELOOM_GPU` (default `2`).
* `CINELOOM_OFFLOAD=sequential` (~6–8 GB peak, neighbour-friendly) or `model`
  (~10–15 GB, faster).
* `POST /v1/videos` → `{id}`; poll `GET /v1/jobs/{id}`; fetch `GET /v1/files/{id}`.

See [`server/README.md`](server/README.md) for details.

## Project status

This is an early fork (`v0.1.0`). The remote-backend video path is verified
end-to-end on a Linux GPU server (LTX-2.3 int8, sequential offload, async job →
downloaded mp4). Implementation roadmap and rationale:
[`docs/html/Cineloom-立项与实现路径.html`](docs/html/Cineloom-立项与实现路径.html).

| Phase | Status |
|---|---|
| P0 Fork + rebrand to Cineloom | ✅ |
| P1 Linux dependency installer | ✅ |
| P2 Remote backend (add-on + server) | ✅ verified (video) |
| P3 Focus + quality refinement | in progress |
| P4 Open-source release | this repo |

Remote ASR/subtitle routing and broader remote model coverage are planned (the
local Pallaidium paths remain available in the meantime).

## License & attribution

Cineloom is **GPL-3.0-or-later**, inherited from Pallaidium (copyleft): any
distributed derivative must stay open under the same license. See
[LICENSE](LICENSE), [NOTICE.md](NOTICE.md), and the preserved upstream readme at
[README.upstream.md](README.upstream.md).

Cineloom distributes **code only** — never model weights. Each AI model carries
its own license (often non-commercial / research-only) and is downloaded from
its origin at the user's discretion.

Upstream: **[tin2tin/Pallaidium](https://github.com/tin2tin/Pallaidium)** by
*tintwotin* — thank you for the bridge between AI and the Blender VSE.
