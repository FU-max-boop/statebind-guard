"""StateBind Guard handoff tooling."""

from pathlib import Path
import re


SOURCE_VERSION = "0.1.31"


def _resolve_version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject.exists():
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return SOURCE_VERSION


__version__ = _resolve_version()
