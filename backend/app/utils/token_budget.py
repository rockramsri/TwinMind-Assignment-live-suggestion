from __future__ import annotations


def estimate_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    # Light approximation suitable for budgeting and truncation.
    return max(1, int(len(stripped.split()) * 1.3))


def clamp_text_to_token_cap(text: str, cap: int) -> str:
    if cap <= 0:
        return ""
    words = text.split()
    if not words:
        return ""
    allowed_words = max(1, int(cap / 1.3))
    if len(words) <= allowed_words:
        return text
    return " ".join(words[:allowed_words])


def fit_sections_to_cap(
    sections: list[tuple[str, str]],
    cap: int,
) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    used = 0
    for name, content in sections:
        section_cost = estimate_tokens(content)
        if used + section_cost <= cap:
            selected.append((name, content))
            used += section_cost
            continue
        remaining = cap - used
        if remaining <= 0:
            break
        trimmed = clamp_text_to_token_cap(content, remaining)
        if trimmed:
            selected.append((name, trimmed))
        break
    return selected
