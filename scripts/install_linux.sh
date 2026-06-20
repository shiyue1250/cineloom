#!/usr/bin/env bash
# =============================================================================
# Cineloom — Linux dependency installer  (P1: make Linux a first-class citizen)
# -----------------------------------------------------------------------------
# Replaces Pallaidium's fragile in-addon "Install dependencies" button with a
# stable, scriptable recipe that has been verified end-to-end on the target
# Linux GPU server (see docs/html/Cineloom-立项与实现路径.html §04 / §06③).
#
# Verified core stack:
#   torch 2.8 + cu12.8 · diffusers 0.38 · sdnq 0.2 · transformers 4.57 · opencv
#
# It installs into Blender's *bundled* Python so the add-on can import torch et al.
#
# Usage:
#   ./install_linux.sh --blender-python /path/to/blender/.../python3.11
#   ./install_linux.sh --blender /opt/blender/blender              # auto-detect py
#   ./install_linux.sh --core-only                                 # minimal LTX path
#   ./install_linux.sh --proxy http://127.0.0.1:1081 --full        # via proxy, full deps
#
# Options:
#   --blender-python PATH  Path to Blender's python binary (most reliable).
#   --blender PATH         Path to the blender executable (we derive its python).
#   --core-only            Install only the verified LTX-2.3 core (default).
#   --full                 Also install requirements_linux.txt (everything).
#   --proxy URL            HTTP(S) proxy for pip + HuggingFace (Great-Firewall path).
#   --torch-index URL      Override the torch wheel index (default: cu128).
#   --no-torch             Skip torch (already installed).
#   -h, --help             Show this help.
# =============================================================================
set -euo pipefail

# ---- defaults ---------------------------------------------------------------
BLENDER_PYTHON=""
BLENDER_BIN=""
MODE="core"                         # core | full
PROXY=""
TORCH_INDEX="https://download.pytorch.org/whl/cu128"
INSTALL_TORCH=1
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"

log()  { printf '\033[36m[cineloom]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[cineloom][warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[cineloom][error]\033[0m %s\n' "$*" >&2; exit 1; }

# ---- args -------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --blender-python) BLENDER_PYTHON="$2"; shift 2;;
    --blender)        BLENDER_BIN="$2"; shift 2;;
    --core-only)      MODE="core"; shift;;
    --full)           MODE="full"; shift;;
    --proxy)          PROXY="$2"; shift 2;;
    --torch-index)    TORCH_INDEX="$2"; shift 2;;
    --no-torch)       INSTALL_TORCH=0; shift;;
    -h|--help)        sed -n '2,40p' "$0"; exit 0;;
    *) die "Unknown option: $1 (use --help)";;
  esac
done

# ---- locate Blender's python ------------------------------------------------
detect_python() {
  if [[ -n "$BLENDER_PYTHON" ]]; then
    echo "$BLENDER_PYTHON"; return
  fi
  if [[ -n "$BLENDER_BIN" ]]; then
    # Ask Blender itself for its interpreter (most accurate).
    "$BLENDER_BIN" --background --factory-startup \
      --python-expr 'import sys;print("PYEXE="+sys.executable)' 2>/dev/null \
      | sed -n 's/^PYEXE=//p' | head -1
    return
  fi
  # Fall back to a bundled python next to a blender on PATH.
  local blender; blender="$(command -v blender || true)"
  if [[ -n "$blender" ]]; then
    local root; root="$(dirname "$(readlink -f "$blender")")"
    local py; py="$(find "$root" -maxdepth 4 -type f -name 'python3*' 2>/dev/null | head -1)"
    [[ -n "$py" ]] && { echo "$py"; return; }
  fi
  echo ""
}

PYBIN="$(detect_python)"
[[ -n "$PYBIN" && -x "$PYBIN" ]] || die \
  "Could not locate Blender's Python. Pass --blender-python /path/to/python3.x \
or --blender /path/to/blender."

log "Blender Python: $PYBIN"
"$PYBIN" --version

# ---- proxy / mirror env -----------------------------------------------------
PIP_PROXY_ARGS=()
if [[ -n "$PROXY" ]]; then
  log "Using proxy: $PROXY"
  export https_proxy="$PROXY" http_proxy="$PROXY" HTTPS_PROXY="$PROXY" HTTP_PROXY="$PROXY"
  PIP_PROXY_ARGS=(--proxy "$PROXY")
fi
# HF mirror is fine for metadata; large weights should go through --proxy
# (see download_models.py). Set a mirror only if the user has not set one.
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

PIP=("$PYBIN" -m pip "${PIP_PROXY_ARGS[@]}")

# ---- ensure pip -------------------------------------------------------------
if ! "$PYBIN" -m pip --version >/dev/null 2>&1; then
  log "Bootstrapping pip (ensurepip)…"
  "$PYBIN" -m ensurepip --upgrade || die "ensurepip failed"
fi
log "Upgrading pip/setuptools/wheel…"
"${PIP[@]}" install --upgrade "pip" "setuptools<70.0.0" wheel

# ---- torch (cu128) ----------------------------------------------------------
if [[ "$INSTALL_TORCH" -eq 1 ]]; then
  log "Installing torch 2.8 (cu12.8) from $TORCH_INDEX …"
  "${PIP[@]}" install --index-url "$TORCH_INDEX" \
    "torch==2.8.0" "torchvision" "torchaudio"
else
  warn "Skipping torch (--no-torch)."
fi

# ---- verified LTX-2.3 core --------------------------------------------------
log "Installing verified LTX-2.3 core stack…"
"${PIP[@]}" install \
  "diffusers==0.38.0" \
  "sdnq==0.2.0" \
  "transformers==4.57.1" \
  "accelerate" "safetensors" "peft" "tokenizers" \
  "huggingface_hub" "hf_xet" \
  "opencv-python-headless" "imageio" "imageio-ffmpeg" "pillow" "numpy" \
  "einops" "sentencepiece" "ftfy"

# ---- full deps (optional) ---------------------------------------------------
if [[ "$MODE" == "full" ]]; then
  REQ="$REPO_ROOT/requirements_linux.txt"
  [[ -f "$REQ" ]] || die "requirements_linux.txt not found at $REQ"
  log "Installing FULL Linux dependency set ($REQ) — this takes a while…"
  # Torch is already pinned above; let the rest resolve against it.
  "${PIP[@]}" install -r "$REQ" || warn \
    "Some packages in the full set failed; the LTX-2.3 core above is still usable."
fi

# ---- verify -----------------------------------------------------------------
log "Verifying core imports…"
"$PYBIN" - <<'PYEOF'
import importlib, sys
mods = ["torch", "diffusers", "sdnq", "transformers", "cv2", "PIL"]
ok = True
for m in mods:
    try:
        mod = importlib.import_module(m)
        v = getattr(mod, "__version__", "?")
        print(f"  ok  {m:<14} {v}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"  FAIL {m:<14} {type(e).__name__}: {e}")
try:
    import torch
    print(f"  cuda available: {torch.cuda.is_available()}")
except Exception:
    pass
sys.exit(0 if ok else 1)
PYEOF

log "Done. Next: download weights with scripts/download_models.py (proxy-aware),"
log "then enable the Cineloom add-on in Blender (Edit ▸ Preferences ▸ Add-ons)."
