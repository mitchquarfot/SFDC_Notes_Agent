from __future__ import annotations

import re


_VTT_HEADER_RE = re.compile(r"^\ufeff?WEBVTT.*?$", re.IGNORECASE | re.MULTILINE)
_VTT_TIMESTAMP_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}.*?$",
    re.MULTILINE,
)

_SRT_INDEX_RE = re.compile(r"^\d+\s*$", re.MULTILINE)
_SRT_TIMESTAMP_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}.*?$",
    re.MULTILINE,
)


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_vtt(text: str) -> str:
    t = text
    t = _VTT_HEADER_RE.sub("", t)
    t = _VTT_TIMESTAMP_RE.sub("", t)
    # Drop common cue settings lines (e.g. "align:start position:0%")
    t = re.sub(r"^(align|position|size|line):.*?$", "", t, flags=re.MULTILINE | re.IGNORECASE)
    return normalize_whitespace(t)


def strip_srt(text: str) -> str:
    t = text
    t = _SRT_INDEX_RE.sub("", t)
    t = _SRT_TIMESTAMP_RE.sub("", t)
    return normalize_whitespace(t)


def clean_transcript_text(filename: str, raw_text: str) -> str:
    lower = filename.lower()
    if lower.endswith(".vtt"):
        return strip_vtt(raw_text)
    if lower.endswith(".srt"):
        return strip_srt(raw_text)
    return normalize_whitespace(raw_text)

