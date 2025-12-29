from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class TmeParseResult:
    url: str
    username: Optional[str] = None  # without @


def parse_tme_url(raw: str) -> Optional[TmeParseResult]:
    """
    Parses `https://t.me/...` links.

    Supported:
    - https://t.me/<username>
    - https://t.me/<username>?start=...

    Not verifiable (no username):
    - https://t.me/+<invite>
    - https://t.me/joinchat/<invite>
    - https://t.me/c/<id>/<msg>
    """
    s = (raw or "").strip()
    if not s:
        return None
    if s.startswith("t.me/"):
        s = "https://" + s
    if not (s.startswith("http://") or s.startswith("https://")):
        return None

    try:
        u = urlparse(s)
    except Exception:
        return None

    host = (u.netloc or "").lower()
    if host not in {"t.me", "www.t.me"}:
        return None

    path = (u.path or "").strip("/")
    if not path:
        return None

    # invite / joinchat / internal message links are not verifiable by username
    if path.startswith("+") or path.startswith("joinchat/") or path.startswith("c/"):
        return TmeParseResult(url=s, username=None)

    # plain username
    username = path.split("/", 1)[0].strip()
    if not username:
        return None
    if username.startswith("+"):
        return TmeParseResult(url=s, username=None)
    # strip leading @ if someone pasted it into URL (rare)
    username = username.lstrip("@")
    if not username:
        return None
    return TmeParseResult(url=s, username=username)


