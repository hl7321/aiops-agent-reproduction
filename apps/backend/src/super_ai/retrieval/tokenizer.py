from __future__ import annotations

import re
import unicodedata

_SEGMENT = re.compile(
    r"(?P<cjk>[\u3400-\u4dbf\u4e00-\u9fff]+)"
    r"|(?P<ascii>[a-z0-9](?:[a-z0-9_.$-]*[a-z0-9])?)"
)


def tokenize_for_retrieval(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    for match in _SEGMENT.finditer(normalized):
        cjk = match.group("cjk")
        if cjk is not None:
            tokens.extend(cjk)
            tokens.extend(cjk[index : index + 2] for index in range(len(cjk) - 1))
            continue
        ascii_token = match.group("ascii")
        if ascii_token is not None:
            tokens.append(ascii_token)
    return tuple(tokens)
