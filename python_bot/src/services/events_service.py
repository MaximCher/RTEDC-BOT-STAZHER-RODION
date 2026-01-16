from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import unescape
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from src.logger import logger

_MSK_TZ = timezone(timedelta(hours=3))
_CACHE_TTL_SEC = 300

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


def _is_event_text(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if "📅" in text:
        return True
    return any(key in lowered for key in _EVENT_KEYWORDS)


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
            text = text_el.get_text("\n").strip()
            links = [
                a.get("href", "").strip()
                for a in text_el.find_all("a")
                if a.get("href")
            ]
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
                "text": unescape(text),
                "links": links,
                "published_at": published_at,
            }
        )
    return posts


def _pick_event_candidate(posts: list[dict[str, object]]) -> Optional[dict[str, object]]:
    if not posts:
        return None
    now = datetime.now(_MSK_TZ).date()
    candidates = [p for p in posts if _is_event_text(str(p.get("text", "")))]
    if not candidates:
        return None
    upcoming: list[tuple[date, dict[str, object]]] = []
    for post in candidates:
        date_range = _parse_event_date_range(str(post.get("text", "")))
        if not date_range:
            continue
        _start, end = date_range
        if end >= now:
            upcoming.append((end, post))
    if upcoming:
        upcoming.sort(key=lambda item: item[0])
        return upcoming[0][1]
    candidates.sort(
        key=lambda item: item.get("published_at") or datetime.min,
        reverse=True,
    )
    return candidates[0]


def _build_event_card(
    *, channel: str, post: dict[str, object]
) -> Optional[EventCard]:
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
    url = ""
    links = [str(l).strip() for l in post.get("links", []) if str(l).strip()]
    if links:
        url = links[0]
    if not url:
        url = post_url
    lines: list[str] = []
    if is_past:
        lines.append(
            "⚠️ Мероприятие уже прошло. Мы обновим карточку, как появится следующее."
        )
    lines.append("Ближайшее мероприятие СРВТ:")
    lines.append(text)
    if url and url not in text:
        lines.append(f"Подробнее и регистрация: {url}")
    return EventCard(text="\n\n".join(lines), url=url, is_past=is_past)


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
