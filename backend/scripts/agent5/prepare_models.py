from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "900")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "120")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, expected: str | None, expected_size: int | None = None) -> bool:
    if not path.is_file():
        return False
    if expected_size is not None and path.stat().st_size != int(expected_size):
        return False
    return not expected or sha256(path).lower() == expected.lower()


def download_atomic(url: str, destination: Path, expected: str | None, expected_size: int | None = None, retries: int = 3) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if verify(destination, expected, expected_size):
        print(f"OK cached: {destination.name}")
        return
    destination.unlink(missing_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        temp = destination.with_suffix(destination.suffix + ".part")
        temp.unlink(missing_ok=True)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Agent5-model-installer/0.1"})
            with urllib.request.urlopen(request, timeout=180) as response, temp.open("wb") as output:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RuntimeError(f"HTTP {status} while downloading {destination.name}")
                content_length = response.headers.get("Content-Length")
                shutil.copyfileobj(response, output)
            if content_length and temp.stat().st_size != int(content_length):
                raise RuntimeError(f"incomplete download for {destination.name}: expected HTTP length {content_length}, got {temp.stat().st_size}")
            if not verify(temp, expected, expected_size):
                actual = sha256(temp)
                raise RuntimeError(
                    f"integrity mismatch for {destination.name}: sha256={actual}, size={temp.stat().st_size}"
                )
            os.replace(temp, destination)
            print(f"Downloaded: {destination.name} ({destination.stat().st_size:,} bytes)")
            return
        except Exception as exc:
            last_error = exc
            temp.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")



def prepare_speechbrain_local_aliases(destination: Path) -> None:
    """Create normal-file aliases expected by SpeechBrain on non-admin Windows.

    The pinned snapshot ships ``label_encoder.txt`` while the pretrainer maps it
    to ``label_encoder.ckpt``. A normal copy avoids Windows symlink privileges.
    """
    source = destination / "label_encoder.txt"
    alias = destination / "label_encoder.ckpt"
    if source.is_file():
        if not alias.is_file() or sha256(alias) != sha256(source):
            shutil.copy2(source, alias)

def download_hf_snapshot(item: dict, model_dir: Path) -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("huggingface-hub is required; run setup first") from exc
    destination = model_dir / item["destination"]
    required = item["required_files"]
    checksums = item.get("checksums", {})
    sizes = item.get("sizes", {})
    if all(verify(destination / name, checksums.get(name), sizes.get(name)) for name in required):
        prepare_speechbrain_local_aliases(destination)
        print(f"OK cached: {item['name']}")
        return
    destination.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    # A single worker is deliberately used on Windows/unstable office networks.
    # The Hugging Face local-dir cache keeps completed byte ranges between
    # attempts, while the explicit integrity check prevents a partial checkpoint
    # from ever being accepted as a model.
    for attempt in range(1, 7):
        try:
            print(f"{item['name']} download attempt {attempt}/6")
            snapshot_download(
                repo_id=item["repository"],
                revision=item["revision"],
                local_dir=str(destination),
                allow_patterns=required,
                max_workers=1,
            )
            missing = [name for name in required if not verify(destination / name, checksums.get(name), sizes.get(name))]
            if missing:
                raise RuntimeError(f"incomplete or invalid SpeechBrain snapshot files: {missing}")
            prepare_speechbrain_local_aliases(destination)
            print(f"Downloaded: {item['name']}")
            return
        except Exception as exc:
            last_error = exc
            if attempt < 6:
                wait_seconds = min(60, attempt * 10)
                print(f"Attempt {attempt} failed: {exc}. Retrying in {wait_seconds}s...", file=sys.stderr)
                time.sleep(wait_seconds)
    raise RuntimeError(f"SpeechBrain snapshot download failed after 6 attempts: {last_error}")


def _project_root() -> Path:
    # backend/scripts/agent5/prepare_models.py -> repo root
    return Path(__file__).resolve().parents[3]


def _model_dir(root: Path) -> Path:
    override = os.getenv("AGENT5_MODELS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return (root / "models" / "agent5").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and checksum Agent5 model files")
    parser.add_argument(
        "--root",
        type=Path,
        default=_project_root(),
        help="Repository root (defaults to Interview_Agentic_AI)",
    )
    parser.add_argument("--skip-anti-spoof", action="store_true")
    parser.add_argument("--skip-speaker", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    model_dir = _model_dir(root)
    manifest_path = model_dir / "model_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(
            f"Missing {manifest_path}. Expected models under models/agent5/ at repo root."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for item in manifest["models"]:
        if args.skip_anti_spoof and "MiniFAS" in item["name"]:
            print(f"Skipped optional: {item['name']}")
            continue
        if args.skip_speaker and item["source_type"] == "huggingface_snapshot":
            print(f"Skipped: {item['name']}")
            continue
        try:
            if item["source_type"] == "url":
                destination = model_dir / item["destination"]
                if args.verify_only:
                    if not verify(destination, item.get("sha256"), item.get("size_bytes")):
                        raise RuntimeError(f"missing or checksum mismatch: {destination}")
                    print(f"Verified: {destination.name}")
                else:
                    download_atomic(item["url"], destination, item.get("sha256"), item.get("size_bytes"))
            else:
                if args.verify_only:
                    dest = model_dir / item["destination"]
                    bad = [
                        name
                        for name in item["required_files"]
                        if not verify(dest / name, item.get("checksums", {}).get(name), item.get("sizes", {}).get(name))
                    ]
                    if bad:
                        raise RuntimeError(f"missing or checksum mismatch: {bad}")
                    prepare_speechbrain_local_aliases(dest)
                    print(f"Verified: {item['name']}")
                else:
                    download_hf_snapshot(item, model_dir)
        except Exception as exc:
            errors.append(f"{item['name']}: {exc}")
    if errors:
        print("Model preparation failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
