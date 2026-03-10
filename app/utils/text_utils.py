import re

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"')\]]+",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(text)


def truncate(text: str, max_length: int = 4000) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_messages_for_llm(
    messages: list[dict[str, str]], max_chars: int = 3000
) -> str:
    lines = []
    total = 0
    for msg in messages:
        line = f"[{msg['username']}]: {msg['text']}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def parse_json_from_llm(text: str) -> dict | None:
    try:
        import json
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        text = text.strip()
        return json.loads(text)
    except Exception:
        return None
