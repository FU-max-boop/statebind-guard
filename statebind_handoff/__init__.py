"""StateBind Guard handoff tooling."""

from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
import re


def _resolve_version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject.exists():
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    try:
        return package_version("statebind-guard")
    except PackageNotFoundError:
        pass
    return "0.0.0"


__version__ = _resolve_version()
