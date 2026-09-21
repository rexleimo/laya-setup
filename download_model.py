#!/usr/bin/env python3
"""Download Laya checkpoints from HuggingFace into ./models/laya.

Default source is the HF mirror (HF_ENDPOINT=https://hf-mirror.com), which works
from mainland China. Only the requested checkpoint is fetched:

  english          -> models/laya/                    (~840 MB)
  multilingual     -> models/laya/multilingual/       (~650 MB)
  typed-decisions  -> models/laya/typed-decisions/    (~840 MB)
  all              -> everything in the repo          (~2.5 GB)
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DEST = os.path.join(HERE, "models", "laya")
REPO = "convaiinnovations/laya"

INCLUDES = {
    "english": [
        "model.safetensors",
        "rl_agent_config.json",
        "encoder/config.json",
        "tokenizer/*",
    ],
    "multilingual": ["multilingual/*"],
    "typed-decisions": ["typed-decisions/*"],
}
REQUIRED = {
    "english": ["model.safetensors", "rl_agent_config.json", "encoder/config.json", "tokenizer/tokenizer.json"],
    "multilingual": ["multilingual/model.safetensors", "multilingual/rl_agent_config.json"],
    "typed-decisions": ["typed-decisions/model.safetensors", "typed-decisions/rl_agent_config.json"],
}


def download(variant, dest, repo):
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    from huggingface_hub import snapshot_download

    kwargs = {"repo_id": repo, "local_dir": dest}
    if variant != "all":
        kwargs["allow_patterns"] = INCLUDES[variant]
        if variant == "english":
            kwargs["ignore_patterns"] = ["multilingual/*", "typed-decisions/*"]
    t0 = time.time()
    path = snapshot_download(**kwargs)
    print("snapshot ready in %.0fs: %s" % (time.time() - t0, path))
    return path


def verify(variant, dest):
    if variant == "all":
        variant = "english"
    missing = [
        f for f in REQUIRED[variant] if not os.path.exists(os.path.join(dest, f))
    ]
    if missing:
        print("MISSING FILES: %s" % ", ".join(missing), file=sys.stderr)
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--variant",
        default="english",
        choices=["english", "multilingual", "typed-decisions", "all"],
    )
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args()

    if os.path.exists(os.path.join(args.dest, "model.safetensors")) and args.variant == "english":
        print("english checkpoint already present at %s" % args.dest)
        return 0

    print("endpoint : %s" % os.environ.get("HF_ENDPOINT", "https://hf-mirror.com"))
    print("repo     : %s (variant=%s)" % (args.repo, args.variant))
    print("dest     : %s" % args.dest)
    try:
        download(args.variant, args.dest, args.repo)
    except Exception as exc:
        print("download failed: %s" % exc, file=sys.stderr)
        print(
            "tips: check the network; or set another mirror, e.g.\n"
            "  set HF_ENDPOINT=https://hf-mirror.com\n"
            "ModelScope also hosts the repo: https://www.modelscope.cn/models/convaiinnovations/laya",
            file=sys.stderr,
        )
        return 1
    if not verify(args.variant, args.dest):
        return 1
    size_gb = sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, fs in os.walk(args.dest)
        for f in fs
        if f.endswith(".safetensors")
    ) / 1e9
    print("OK - %.2f GB of weights on disk" % size_gb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
