from __future__ import annotations

import re
from typing import List


_PARENS_RE = re.compile(r"\(([^()]*)\)")
_SLASH_SPLIT_RE = re.compile(r"\s*/\s*")


def extract_quick_choices(question_text: str) -> List[str]:
    """
    Extract 2–3 short, explicit answer options from a question text.

    We intentionally only return choices when the set is small (2–3) to avoid
    overwhelming the user or creating misleading "suggestions" for free-form inputs.
    """
    raw = (question_text or "").strip()
    if not raw:
        return []

    candidates: List[str] = []

    # Prefer explicit "(a/b/c)" patterns (usually written by authors).
    parens = _PARENS_RE.findall(raw)
    if parens:
        # The last parentheses group is typically the actual options hint.
        candidates.append(parens[-1])

    # Fallback: patterns like "Срочность: сейчас / сегодня / не срочно"
    if ":" in raw and "/" in raw:
        tail = raw.split(":", 1)[-1].strip()
        if tail:
            candidates.append(tail)

    # Another fallback: "напишите: новый / рефинанс" (without parentheses sometimes)
    if " / " in raw or "/" in raw:
        candidates.append(raw)

    for cand in candidates:
        if "/" not in cand:
            continue
        parts = [
            p.strip().strip(" .;:!?\"'«»()[]{}")
            for p in _SLASH_SPLIT_RE.split(cand)
        ]
        parts = [p for p in parts if p]

        # Keep only short options (avoid parsing examples like "да/нет/в процессе + ...").
        cleaned: List[str] = []
        for p in parts:
            # Normalize common instruction prefixes inside options
            # e.g. "напишите: новый / рефинанс" -> "новый", "рефинанс"
            pl = p.lower()
            if "напишите" in pl and ":" in p:
                p = p.split(":", 1)[-1].strip()

            # Stop early if it looks like a combined or multi-part instruction.
            # Allow suffix "+" (e.g. "месяц+") but reject "в процессе + сегодня".
            if "+" in p:
                if " + " in p:
                    cleaned = []
                    break
                if not p.endswith("+"):
                    cleaned = []
                    break
                # keep "месяц+"

            if len(p) > 28:
                cleaned = []
                break
            cleaned.append(p)

        unique: List[str] = []
        for p in cleaned:
            if p not in unique:
                unique.append(p)

        if 2 <= len(unique) <= 3:
            return unique

    return []


