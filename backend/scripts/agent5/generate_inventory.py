from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_requirements(path: Path) -> list[dict[str, str]]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("--") or line.startswith("-r"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            items.append({"type": "library", "name": name, "version": version, "purl": f"pkg:pypi/{name.lower()}@{version}"})
    return items


def parse_npm_package(path: Path) -> list[dict[str, str]]:
    package = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict[str, str]] = []
    for scope, group in (("runtime", package.get("dependencies", {})), ("development", package.get("devDependencies", {}))):
        for name, version in sorted(group.items()):
            items.append({
                "type": "library",
                "name": name,
                "version": version,
                "scope": scope,
                "purl": f"pkg:npm/{name.replace('@', '%40')}@{version}",
            })
    return items


def main() -> int:
    components = parse_requirements(ROOT / "requirements.txt") + parse_requirements(ROOT / "requirements-dev.txt")
    components += parse_npm_package(ROOT / "frontend" / "package.json")
    models = json.loads((ROOT / "models" / "model_manifest.json").read_text(encoding="utf-8"))["models"]
    for model in models:
        components.append(
            {
                "type": "machine-learning-model",
                "name": model["name"],
                "version": model.get("revision", model.get("sha256", "pinned"))[:16],
                "license": model["license"],
                "source": model["source"],
            }
        )
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "Agent5", "version": "0.4.0"}},
        "components": components,
    }
    (ROOT / "docs" / "SBOM.cyclonedx.json").write_text(json.dumps(sbom, indent=2), encoding="utf-8")
    excluded = {".venv", "node_modules", ".git", "__pycache__", ".pytest_cache"}
    files = []
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in excluded for part in relative.parts):
            continue
        if relative.parts and relative.parts[0] == "storage" and path.name != ".gitkeep":
            continue
        if relative.as_posix() == "docs/PROJECT_FILE_MANIFEST.sha256":
            continue
        files.append(f"{sha256(path)}  {relative.as_posix()}")
    (ROOT / "docs" / "PROJECT_FILE_MANIFEST.sha256").write_text("\n".join(files) + "\n", encoding="utf-8")
    print(f"Wrote SBOM with {len(components)} components and manifest with {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
