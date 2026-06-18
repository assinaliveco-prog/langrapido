from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ConversationStyle:
    urgency: Literal["low", "normal", "high"]
    target_chars: int
    formality: Literal["low", "medium", "high"]
    mirror_emojis: bool
    max_questions: int


@dataclass(frozen=True)
class MessageTiming:
    thinking_seconds: float
    typing_seconds: float


URGENT_MARKERS = {
    "agora",
    "ainda hoje",
    "hj",
    "rápido",
    "rapido",
    "urgente",
    "pressa",
}
FORMAL_MARKERS = {
    "boa tarde",
    "bom dia",
    "boa noite",
    "poderia",
    "por favor",
    "senhor",
    "senhora",
    "gostaria",
}
INFORMAL_MARKERS = {"vc", "tb", "blz", "mano", "tlg", "kk", "pq"}
EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF]",
    flags=re.UNICODE,
)


def infer_style(text: str) -> ConversationStyle:
    normalized = " ".join(text.lower().split())
    urgent = len(text.strip()) <= 40 or any(
        marker in normalized for marker in URGENT_MARKERS
    )
    if any(marker in normalized for marker in FORMAL_MARKERS):
        formality: Literal["low", "medium", "high"] = "high"
    elif any(re.search(rf"\b{re.escape(marker)}\b", normalized) for marker in INFORMAL_MARKERS):
        formality = "low"
    else:
        formality = "medium"

    return ConversationStyle(
        urgency="high" if urgent else "normal",
        target_chars=180 if urgent else 320,
        formality=formality,
        mirror_emojis=bool(EMOJI_PATTERN.search(text)),
        max_questions=1,
    )


def split_semantically(
    text: str,
    max_chunks: int = 3,
    target_chars: int = 180,
) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    if len(normalized) <= target_chars:
        return [normalized]

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]
    if len(sentences) == 1:
        return [normalized]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        remaining_slots = max_chunks - len(chunks)
        if current and len(candidate) > target_chars and remaining_slots > 1:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)

    while len(chunks) > max_chunks:
        tail = f"{chunks[-2]} {chunks[-1]}"
        chunks[-2:] = [tail]
    return chunks


def safe_typo(
    text: str,
    probability: float,
    seed: int | None = None,
) -> str:
    bounded_probability = max(0.0, min(0.05, probability))
    if bounded_probability == 0:
        return text

    rng = random.Random(seed)
    if rng.random() >= bounded_probability:
        return text

    candidates: list[re.Match[str]] = []
    for match in re.finditer(r"\b[a-záàâãéêíóôõúç]{5,}\b", text):
        token = match.group(0)
        if token[0].isupper():
            continue
        candidates.append(match)
    if not candidates:
        return text

    match = rng.choice(candidates)
    token = match.group(0)
    index = rng.randint(1, len(token) - 2)
    chars = list(token)
    chars[index - 1], chars[index] = chars[index], chars[index - 1]
    changed = "".join(chars)
    return f"{text[:match.start()]}{changed}{text[match.end():]}"


def timing_for(text: str) -> MessageTiming:
    character_count = len(text.strip())
    thinking = min(2.5, max(0.4, 0.45 + character_count * 0.008))
    typing = min(8.0, max(0.8, character_count / 18))
    return MessageTiming(
        thinking_seconds=round(thinking, 2),
        typing_seconds=round(typing, 2),
    )
