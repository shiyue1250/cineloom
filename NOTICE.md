# NOTICE — Cineloom

Cineloom is a fork of **Pallaidium** by *tintwotin*.

- Upstream: https://github.com/tin2tin/Pallaidium
- Upstream license: **GPL-3.0-or-later**
- Upstream copyright: © 2023–2026 tintwotin and Pallaidium contributors

Cineloom inherits the GPL-3.0-or-later license (copyleft): any distributed
derivative — Cineloom included — **must remain open source under the same license**.
See [LICENSE](LICENSE).

## What Cineloom changes relative to upstream

Cineloom keeps Pallaidium's AI↔VSE bridge (operators, the model-plugin
architecture, the UI, the batch queue) and adds three deltas:

1. **Linux as a first-class citizen** — a stable, verified dependency installer
   (`scripts/install_linux.sh`) replacing the upstream one-click button, plus a
   proxy-aware weight downloader (`scripts/download_models.py`).
2. **Editing/generation decoupling** — a **remote backend**: Blender edits on the
   desktop while generation requests are sent to a GPU server (the bundled
   Cineloom server, or any OpenAI-compatible `/v1` endpoint you run). See
   `models/remote_client.py`, `models_plugins/*/cineloom_remote_*.py`, and `server/`.
3. **Focus + quality** — a containerized LTX-2.3 generation service built from a
   verified diffusers/sdnq stack (`server/`).

## Trademarks / attribution

"Pallaidium" remains the name of the upstream project. Cineloom does not claim
endorsement by the upstream author. The original `README.md` content,
authorship, and copyright notices are preserved in the git history and credited
here per GPL §5 and common open-source courtesy.

## Third-party models

Cineloom distributes **code only**, never model weights. Each AI model carries
its own license (frequently non-commercial / research-only) and is downloaded
from its origin (e.g. HuggingFace) at the user's discretion — same approach as
upstream Pallaidium.
