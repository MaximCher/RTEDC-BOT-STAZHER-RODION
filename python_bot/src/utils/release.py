from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ReleaseInfo:
    sha: Optional[str] = None
    deployed_at_utc: Optional[str] = None
    source: str = "none"


def read_release_file(path: str = "/app/.release") -> ReleaseInfo:
    """
    Reads release metadata written by CI/CD on the server.

    Expected format (simple key=value lines):
      sha=<git sha>
      deployed_at_utc=<ISO timestamp>
    """
    p = Path(path)
    if not p.exists():
        return ReleaseInfo(source="missing")

    sha: Optional[str] = None
    deployed_at_utc: Optional[str] = None

    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().lower()
            v = v.strip()
            if k == "sha":
                sha = v or None
            elif k in ("deployed_at_utc", "deployed_at"):
                deployed_at_utc = v or None
    except Exception:
        return ReleaseInfo(source="error")

    return ReleaseInfo(sha=sha, deployed_at_utc=deployed_at_utc, source="file")


