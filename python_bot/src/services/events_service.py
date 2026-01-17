from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Optional
from urllib.parse import unquote, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup, NavigableString
from src.logger import logger

_MSK_TZ = timezone(timedelta(hours=3))
_CACHE_TTL_SEC = 300
_MAX_EVENT_TEXT_LEN = 3000

_EVENT_KEYWORDS = (
    "событи",
    "мероприят",
    "форум",
    "встреч",
    "вебинар",
    "конференц",
    "съезд",
    "симпозиум",
    "конгресс",
    "кругл",
)
_PAST_MARKERS = (
    "прошел",
    "прошла",
    "прошли",
    "прошедш",
    "состоялся",
    "состоялась",
    "состоялось",
    "состоялись",
    "итоги",
)

_MONTHS_RU = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

_DATE_RE = re.compile(
    r"(\d{1,2})(?:\s*[–-]\s*(\d{1,2}))?\s+"
    r"(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
    r"(?:\s+(\d{4}))?",
    re.IGNORECASE,
)

_CACHE: dict[str, object] = {"value": None, "ts": None}


@dataclass(frozen=True)
class EventCard:
    text: str
    url: str
    is_past: bool
    image_urls: list[str]


def _is_event_text(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if "📅" in text:
        return True
    return any(key in lowered for key in _EVENT_KEYWORDS)


def _looks_past(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _PAST_MARKERS)


def _parse_event_date_range(text: str) -> Optional[tuple[date, date]]:
    if not text:
        return None
    match = _DATE_RE.search(text)
    if not match:
        return None
    start_day = int(match.group(1))
    end_day_raw = match.group(2)
    end_day = int(end_day_raw) if end_day_raw else start_day
    month_name = match.group(3).lower()
    month = _MONTHS_RU.get(month_name)
    if not month:
        return None
    year_raw = match.group(4)
    year = int(year_raw) if year_raw else datetime.now(_MSK_TZ).year
    try:
        start = date(year, month, start_day)
        end = date(year, month, end_day)
    except Exception:
        return None
    return start, end


def _render_plain_text(element) -> str:
    def _render_node(node) -> str:
        if isinstance(node, NavigableString):
            return unescape(str(node))
        name = getattr(node, "name", None)
        if name == "br":
            return "\n"
        if not name:
            return ""
        return "".join(_render_node(child) for child in node.children)

    text = "".join(_render_node(child) for child in element.children)
    return text.replace("\r", "").strip()


async def _fetch_channel_html(channel: str) -> str:
    url = f"https://t.me/s/{channel}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def _extract_posts(html_text: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html_text, "html.parser")
    posts: list[dict[str, object]] = []
    for msg in soup.select("div.tgme_widget_message"):
        data_post = msg.get("data-post", "")
        post_id = data_post.split("/")[-1] if data_post else ""
        text_el = msg.select_one(".tgme_widget_message_text")
        text = ""
        links: list[str] = []
        if text_el:
            text = _render_plain_text(text_el)
            links = [
                a.get("href", "").strip()
                for a in text_el.find_all("a")
                if a.get("href")
            ]
        image_urls: list[str] = []
        for photo_el in msg.select(".tgme_widget_message_photo_wrap"):
            if not photo_el or not photo_el.has_attr("style"):
                continue
            style = photo_el.get("style", "")
            match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
            if match:
                url = match.group(1).strip()
                if url:
                    image_urls.append(url)
        time_el = msg.select_one("time")
        published_at: Optional[datetime] = None
        if time_el and time_el.has_attr("datetime"):
            try:
                published_at = datetime.fromisoformat(time_el["datetime"])
            except Exception:
                published_at = None
        posts.append(
            {
                "post_id": post_id,
                "text": text,
                "links": links,
                "image_urls": image_urls,
                "published_at": published_at,
            }
        )
    return posts


def _pick_event_candidate(
    posts: list[dict[str, object]],
) -> Optional[dict[str, object]]:
    if not posts:
        return None
    now = datetime.now(_MSK_TZ).date()
    candidates = [p for p in posts if _is_event_text(str(p.get("text", "")))]
    if not candidates:
        return None
    upcoming: list[tuple[date, dict[str, object]]] = []
    dated: list[tuple[date, dict[str, object]]] = []
    for post in candidates:
        text = str(post.get("text", ""))
        date_range = _parse_event_date_range(text)
        if not date_range:
            continue
        _start, end = date_range
        dated.append((end, post))
        if end >= now and not _looks_past(text):
            upcoming.append((end, post))
    if upcoming:
        upcoming.sort(key=lambda item: item[0])
        return upcoming[0][1]
    if dated:
        dated.sort(key=lambda item: item[0], reverse=True)
        return dated[0][1]
    return None


def _build_event_card(
    *, channel: str, post: dict[str, object]
) -> Optional[EventCard]:
    def _normalize_url(raw: str) -> str:
        value = (raw or "").strip()
        if not value:
            return ""
        if value.startswith("tg://"):
            return value
        if not value.startswith(("http://", "https://")):
            return ""
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            return ""
        host = parsed.hostname or ""
        if not host:
            return ""
        try:
            host = unquote(host).encode("idna").decode("ascii")
        except Exception:
            pass
        netloc = host
        if parsed.port:
            netloc = f"{host}:{parsed.port}"
        return urlunparse(
            (
                parsed.scheme,
                netloc,
                parsed.path or "",
                parsed.params or "",
                parsed.query or "",
                parsed.fragment or "",
            )
        )

    post_id = str(post.get("post_id", "")).strip()
    text = str(post.get("text", "")).strip()
    if not text:
        return None
    post_url = f"https://t.me/{channel}/{post_id}" if post_id else ""
    date_range = _parse_event_date_range(text)
    now = datetime.now(_MSK_TZ).date()
    is_past = False
    if date_range:
        _start, end = date_range
        is_past = end < now
    if not is_past and _looks_past(text):
        is_past = True
    url = ""
    raw_links = post.get("links")
    if not isinstance(raw_links, list):
        raw_links = []
    links = [str(link).strip() for link in raw_links if str(link).strip()]
    for link in links:
        normalized = _normalize_url(link)
        if normalized:
            url = normalized
            break
    if not url:
        url = _normalize_url(post_url) or post_url

    def _clip_text(value: str, max_len: int) -> str:
        if len(value) <= max_len:
            return value
        clipped = value[:max_len]
        if "\n" in clipped:
            clipped = clipped.rsplit("\n", 1)[0]
        if len(clipped) < max_len * 0.5:
            clipped = value[:max_len]
        return clipped.rstrip() + "..."

    lines: list[str] = []
    lines.append(_clip_text(text, _MAX_EVENT_TEXT_LEN))
    raw_images = post.get("image_urls")
    if not isinstance(raw_images, list):
        raw_images = []
    image_urls = [_normalize_url(str(item)) for item in raw_images]
    image_urls = [item for item in image_urls if item]
    return EventCard(
        text="\n\n".join(lines),
        url=url,
        is_past=is_past,
        image_urls=image_urls,
    )


async def get_latest_event_card(
    channel: str = "rtedc_org",
) -> Optional[EventCard]:
    cached = _CACHE.get("value")
    ts = _CACHE.get("ts")
    now = datetime.now(_MSK_TZ)
    if cached and isinstance(ts, datetime):
        if (now - ts).total_seconds() <= _CACHE_TTL_SEC:
            return cached  # type: ignore[return-value]
    try:
        html_text = await _fetch_channel_html(channel)
        posts = _extract_posts(html_text)
        candidate = _pick_event_candidate(posts)
        if not candidate:
            return None
        card = _build_event_card(channel=channel, post=candidate)
        if card:
            _CACHE["value"] = card
            _CACHE["ts"] = now
        return card
    except Exception as exc:
        logger.warning("events_fetch_failed", error=str(exc))
        return None
