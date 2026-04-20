"""Log normalization for container execution traces.

Implements the circular-buffer truncation policy described in design-doc §3 §IV
and §8: retain the first 2 KB and last 5 KB of each execution stream; discard
the middle to prevent context bloat when feeding output to the parser and LLM.

Design-doc references:
    - Section 3 §IV: "Log Normalization: Circular Buffer truncates logs,
      retaining only the first 2KB and last 5KB of the execution trace."
    - Section 8: "Implement log normalization: circular buffer keeping
      first 2KB + last 5KB of execution trace"
"""

from __future__ import annotations

# Byte thresholds — spec-mandated (2 KB head, 5 KB tail).
HEAD_BYTES: int = 2 * 1024   # 2 048 bytes
TAIL_BYTES: int = 5 * 1024   # 5 120 bytes

# Separator inserted at the truncation point so parsers and LLMs can see
# that content was dropped and how much.
_SEPARATOR = "\n... [{n} bytes omitted] ...\n"


def normalize_logs(text: str) -> str:
    """Truncate *text* to HEAD_BYTES + TAIL_BYTES, discarding the middle.

    If the encoded length of *text* is at or below ``HEAD_BYTES + TAIL_BYTES``
    the input is returned unchanged.  Otherwise the head and tail are decoded
    independently (``errors="replace"`` guards against mid-character splits at
    the cut points) and joined by a human-readable separator that reports the
    number of omitted bytes.

    Working at the byte level (UTF-8) matches the spec's "2 KB / 5 KB" sizing
    and avoids the ambiguity of "character" in multi-byte encodings.
    """
    if not text:
        return text

    encoded = text.encode("utf-8")
    total = len(encoded)
    limit = HEAD_BYTES + TAIL_BYTES

    if total <= limit:
        return text

    head = encoded[:HEAD_BYTES].decode("utf-8", errors="replace")
    tail = encoded[total - TAIL_BYTES:].decode("utf-8", errors="replace")
    dropped = total - HEAD_BYTES - TAIL_BYTES

    return head + _SEPARATOR.format(n=dropped) + tail
