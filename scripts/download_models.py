#!/usr/bin/env python3
"""
Cineloom — proxy-aware model weight downloader  (P1).

Downloads diffusers-format model weights from HuggingFace, working *around*
HF Xet/CAS large-file blocking that breaks plain ``snapshot_download`` on some
restricted networks:

    a mirror endpoint  → metadata only (Xet large files may still be blocked)
    real huggingface.co endpoint + an HTTP proxy → large files succeed

So this script forces the *real* endpoint and routes everything through the
HTTP proxy you pass with ``--proxy`` (point it at your own proxy).

Examples
--------
    # The LTX-2.3 distilled int8 model (≈41 GB), open network:
    python download_models.py \
        --repo OzzyGT/LTX-2.3-Distilled-1.1-sdnq-dynamic-int8 \
        --dest ~/ai-models/ltx23-distilled-int8

    # Behind a restricted network, via your own proxy:
    python download_models.py --proxy http://127.0.0.1:1081 \
        --repo OzzyGT/LTX-2.3-Distilled-1.1-sdnq-dynamic-int8 \
        --dest ~/ai-models/ltx23-distilled-int8
"""

from __future__ import annotations

import argparse
import os
import sys

# Default model coordinates.
DEFAULT_REPO = "OzzyGT/LTX-2.3-Distilled-1.1-sdnq-dynamic-int8"
DEFAULT_DEST = os.path.expanduser("~/ai-models/ltx23-distilled-int8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cineloom proxy-aware HF downloader")
    p.add_argument("--repo", default=DEFAULT_REPO, help="HuggingFace repo id")
    p.add_argument("--dest", default=DEFAULT_DEST, help="Local destination dir")
    p.add_argument(
        "--proxy",
        default=os.environ.get("CINELOOM_HF_PROXY", ""),
        help="HTTP(S) proxy for the real huggingface.co endpoint "
        "(needed to bypass Xet/CAS blocking). Empty = direct.",
    )
    p.add_argument(
        "--endpoint",
        default="https://huggingface.co",
        help="HF endpoint. Keep the real one when using --proxy; large Xet "
        "files are NOT available from hf-mirror.com.",
    )
    p.add_argument("--workers", type=int, default=4, help="Parallel download workers")
    p.add_argument(
        "--allow", nargs="*", default=None,
        help="Optional allow_patterns (e.g. '*.safetensors' 'model_index.json')",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Force the real endpoint; route through the proxy if given. This is the
    # exact combination verified to bypass HF Xet/CAS blocking.
    os.environ["HF_ENDPOINT"] = args.endpoint
    if args.proxy:
        os.environ["https_proxy"] = args.proxy
        os.environ["http_proxy"] = args.proxy
        os.environ["HTTPS_PROXY"] = args.proxy
        os.environ["HTTP_PROXY"] = args.proxy
        print(f"[cineloom] proxy: {args.proxy}")
    print(f"[cineloom] endpoint: {args.endpoint}")
    print(f"[cineloom] repo: {args.repo}")
    print(f"[cineloom] dest: {args.dest}")

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print(
            "[cineloom][error] huggingface_hub not installed. Run "
            "scripts/install_linux.sh first (or pip install huggingface_hub hf_xet).",
            file=sys.stderr,
        )
        return 1

    os.makedirs(args.dest, exist_ok=True)
    kwargs = dict(local_dir=args.dest, max_workers=args.workers)
    if args.allow:
        kwargs["allow_patterns"] = args.allow

    path = snapshot_download(args.repo, **kwargs)
    print(f"[cineloom] DONE -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
