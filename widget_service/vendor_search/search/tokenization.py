"""Shared Jieba tokenization for queries and template metadata."""

from __future__ import annotations

import logging
import re

import jieba

jieba.setLogLevel(logging.WARNING)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*|[\u3400-\u9fff]+")


def normalize_text(text: str) -> str:
    """Apply only the approved lexical normalization; do not normalize Unicode."""

    return text.lower().strip()


def tokenize(text: str) -> list[str]:
    """Return deterministic, de-duplicated search tokens in source order."""

    normalized = normalize_text(text)
    result: list[str] = []
    seen: set[str] = set()
    for jieba_token in jieba.cut_for_search(normalized, HMM=False):
        for token in _TOKEN_RE.findall(jieba_token):
            if token and token not in seen:
                seen.add(token)
                result.append(token)
    return result


def token_index_text(description: str, tags: tuple[str, ...] | list[str]) -> str:
    return " ".join(tokenize(" ".join([description, *tags])))
