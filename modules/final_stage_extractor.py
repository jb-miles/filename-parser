#!/usr/bin/env python3
"""
Final-stage extraction for sequence, group, and title.

Scope rules:
- Directory-agnostic: operates only on the filename token stream (no parent folder data).
- Runs after studio/date/studio code/performers have been extracted.

Heuristics are conservative by design to avoid inventing misleading titles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .tokenizer import TokenizationResult
from .trimmer import Trimmer


@dataclass(frozen=True)
class LabeledSequenceMatch:
    key: str
    number: int
    start: int
    end: int


class FinalStageExtractor:
    """
    Extract sequence/group/title together in the final stage.

    The extractor:
    - extracts explicitly-labeled sequence numbers (scene/part/episode/vol/disc)
    - infers group vs title from token order and sequence marker position
    - builds a title from remaining unconsumed tokens, or synthesizes one
    """

    _MEANINGFUL_WORD_RE = re.compile(r"\b[a-zA-Z]{2,}\b")
    _NUMERIC_ONLY_RE = re.compile(r"^\d+$")
    _LEADING_NUMBER_RE = re.compile(r"^\s*(\d{1,3})\s+(.+?)\s*$")
    _SEAN_CODY_CODE_RE = re.compile(r"^sc-?\d{4}$", re.IGNORECASE)

    def __init__(self) -> None:
        self.trimmer = Trimmer()
        self._sequence_patterns = self._build_sequence_patterns()

    def process(self, result: TokenizationResult) -> TokenizationResult:
        if not result.tokens:
            result.sequence = None
            result.group = None
            if not getattr(result, "title", None):
                result.title = None
            return result

        sequence: Dict[str, int] = dict(result.sequence or {})
        group_value: Optional[str] = result.group

        # Pass 1: explicit sequence markers + strong group/title hints inside tokens.
        group_value = self._extract_labeled_sequences(result, sequence, group_value)

        # Pass 2: conservative bare-number sequence inference from structure.
        self._infer_bare_scene_numbers(result, sequence)

        # Pass 3: choose group + title from remaining tokens, or synthesize title.
        group_value, title_value = self._finalize_group_and_title(result, sequence, group_value)

        result.sequence = sequence or None
        result.group = group_value
        result.title = title_value
        result.pattern = self._rebuild_pattern_for_title(result.pattern, result.tokens)
        return result

    def _build_sequence_patterns(self) -> List[Tuple[str, re.Pattern[str]]]:
        patterns: List[Tuple[str, re.Pattern[str]]] = []

        def add(key: str, expr: str) -> None:
            patterns.append((key, re.compile(expr, re.IGNORECASE)))

        # Explicit labels (preferred).
        add("scene", r"\b(?:scene|sc)\b[.\s-]?#?\s*(\d+)\b")
        add("part", r"\b(?:part|pt)\b[.\s-]?#?\s*(\d+)\b")
        add("episode", r"\b(?:episode|ep)\b[.\s-]?#?\s*(\d+)\b")
        add("volume", r"\b(?:volume|vol)\b[.\s-]?#?\s*(\d+)\b")
        add("disc", r"\b(?:disc|disk|cd)\b[.\s-]?#?\s*(\d+)\b")

        # Shorthand forms (more ambiguous, applied after explicit labels).
        add("scene", r"\bs[.\s-]?#?\s*(\d+)\b")
        add("part", r"\bp[.\s-]?#?\s*(\d+)\b")
        add("episode", r"\be[.\s-]?#?\s*(\d+)\b")
        add("volume", r"\bv[.\s-]?#?\s*(\d+)\b")

        return patterns

    def _extract_labeled_sequences(
        self,
        result: TokenizationResult,
        sequence: Dict[str, int],
        group_value: Optional[str],
    ) -> Optional[str]:
        consumed_types = {"path", "date", "studio", "studio_code", "performers"}

        for token in result.tokens or []:
            if token.type in consumed_types:
                continue

            original = token.value or ""
            if not original.strip():
                continue

            # Avoid misclassifying Sean Cody codes as scene numbers.
            if self._SEAN_CODY_CODE_RE.match(original.strip()):
                continue

            matches = self._find_labeled_sequences(original)
            if not matches:
                continue

            # Update sequence dict (last match wins per key).
            for match in matches:
                sequence[match.key] = match.number

            # Use the rightmost match for group/title splitting heuristics.
            primary = max(matches, key=lambda m: (m.end, m.start))
            prefix_raw = original[: primary.start].strip()
            suffix_raw = original[primary.end :].strip()

            prefix = self._remove_sequence_markers(prefix_raw)
            suffix = self._remove_sequence_markers(suffix_raw)

            prefix = self._clean_text(prefix)
            suffix = self._clean_text(suffix)

            # Scene/volume/episode/disc markers at the end typically indicate group.
            group_markers = {"scene", "volume", "episode", "disc"}

            if prefix and not suffix:
                if primary.key in group_markers and group_value is None:
                    group_value = prefix
                    token.type = "sequence"
                elif primary.key == "part":
                    # Text + part number is usually a title, not a group.
                    token.value = prefix
                else:
                    token.value = prefix
                    token.type = "sequence"
                continue

            if not prefix and suffix:
                # Sequence marker before text usually indicates title (not group).
                token.value = suffix
                continue

            if prefix and suffix:
                if primary.key in group_markers and group_value is None:
                    group_value = prefix
                token.value = suffix
                continue

            # Marker-only token (e.g., "Scene 3").
            token.type = "sequence"

        return group_value

    def _infer_bare_scene_numbers(self, result: TokenizationResult, sequence: Dict[str, int]) -> None:
        """
        Infer scene numbers from bare numeric tokens only when structure strongly supports it.

        Supported structures:
        - separate numeric token between text tokens: "<text> <number> <text>"
        """
        if "scene" in sequence:
            return

        consumed_types = {"path", "date", "studio", "studio_code", "performers", "sequence"}

        # Numeric-only token between meaningful text tokens.
        candidates: List[int] = []
        tokens = result.tokens or []
        for idx, token in enumerate(tokens):
            if token.type in consumed_types:
                continue
            if not (token.value or "").strip():
                continue
            candidates.append(idx)

        numeric_candidates = [
            idx for idx in candidates if self._is_numeric_only((tokens[idx].value or "").strip())
        ]

        # Be conservative: only infer when there's exactly one numeric candidate.
        if len(numeric_candidates) != 1:
            return

        num_idx = numeric_candidates[0]
        position = candidates.index(num_idx)

        def meaningful_at(candidate_position: int) -> bool:
            if candidate_position < 0 or candidate_position >= len(candidates):
                return False
            token = tokens[candidates[candidate_position]]
            return self._is_meaningful_text((token.value or "").strip())

        # "<text> <number> <text>"
        if 0 < position < len(candidates) - 1 and meaningful_at(position - 1) and meaningful_at(position + 1):
            self._consume_numeric_scene_token(tokens[num_idx], sequence)
            return

    def _rebuild_pattern_for_title(self, pattern: Optional[str], tokens: Optional[List]) -> Optional[str]:
        if not pattern or not tokens:
            return pattern

        title_indices: set[int] = set()
        real_idx = 0
        for token in tokens:
            if getattr(token, "type", None) == "path":
                continue
            if getattr(token, "type", None) == "title":
                title_indices.add(real_idx)
            real_idx += 1

        if not title_indices:
            return pattern

        def replace_placeholder(match: re.Match[str]) -> str:
            idx = int(match.group(1))
            if idx in title_indices:
                return "{title}"
            return match.group(0)

        return re.sub(r"\{token(\d+)\}", replace_placeholder, pattern)

    def _consume_numeric_scene_token(self, token, sequence: Dict[str, int]) -> None:
        value = (token.value or "").strip()
        if not self._is_numeric_only(value):
            return
        if len(value) > 3:
            return
        try:
            sequence["scene"] = int(value)
        except ValueError:
            return
        token.type = "sequence"

    def _finalize_group_and_title(
        self,
        result: TokenizationResult,
        sequence: Dict[str, int],
        group_value: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        consumed_types = {"path", "date", "studio", "studio_code", "performers", "sequence"}

        remaining = [
            token
            for token in (result.tokens or [])
            if token.type not in consumed_types and (token.value or "").strip()
        ]

        meaningful = [t for t in remaining if self._is_meaningful_text((t.value or "").strip())]

        # If multiple plausible title tokens remain and group is not set, treat the
        # first as group and the remaining as title.
        title_tokens: List = []
        if group_value is None and len(meaningful) >= 2:
            group_value = self._clean_text(meaningful[0].value)
            meaningful[0].type = "group"
            title_tokens = meaningful[1:]
        else:
            title_tokens = meaningful

        # Title from remaining unconsumed tokens.
        if title_tokens:
            for t in title_tokens:
                t.type = "title"
            if len(title_tokens) == 1:
                return group_value, self._clean_text(title_tokens[0].value)
            return group_value, self._clean_text(" ".join(self._clean_text(t.value) for t in title_tokens))

        # No suitable title tokens remain.
        seq_number = self._primary_sequence_number(sequence)
        if group_value and seq_number is not None:
            return group_value, f"{group_value}, Scene {seq_number}"

        performer_title = self._title_from_performers(result)
        if performer_title:
            return group_value, performer_title

        return group_value, None

    def _primary_sequence_number(self, sequence: Dict[str, int]) -> Optional[int]:
        for key in ("scene", "episode", "part", "volume", "disc"):
            if key in sequence:
                return sequence[key]
        return None

    def _title_from_performers(self, result: TokenizationResult) -> Optional[str]:
        performer_tokens = [t.value for t in (result.tokens or []) if t.type == "performers" and t.value.strip()]
        if not performer_tokens:
            return None

        names: List[str] = []
        for token_value in performer_tokens:
            for name in token_value.split(","):
                cleaned = self._clean_text(name)
                if cleaned:
                    names.append(cleaned)

        if not names:
            return None
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} & {names[1]}"
        return f"{', '.join(names[:-1])} & {names[-1]}"

    def _find_labeled_sequences(self, text: str) -> List[LabeledSequenceMatch]:
        matches: List[LabeledSequenceMatch] = []
        for key, pattern in self._sequence_patterns:
            for match in pattern.finditer(text):
                try:
                    number = int(match.group(1))
                except (TypeError, ValueError):
                    continue
                matches.append(
                    LabeledSequenceMatch(
                        key=key,
                        number=number,
                        start=match.start(),
                        end=match.end(),
                    )
                )
        # Sort by position for stable downstream handling.
        matches.sort(key=lambda m: (m.start, m.end))
        return matches

    def _remove_sequence_markers(self, text: str) -> str:
        if not text:
            return ""
        matches = self._find_labeled_sequences(text)
        if not matches:
            return text

        # Remove from right to left so indices remain stable.
        cleaned = text
        for match in sorted(matches, key=lambda m: m.start, reverse=True):
            cleaned = cleaned[: match.start] + cleaned[match.end :]
        return cleaned

    def _is_numeric_only(self, text: str) -> bool:
        return bool(self._NUMERIC_ONLY_RE.match(text))

    def _is_meaningful_text(self, text: str) -> bool:
        return bool(self._MEANINGFUL_WORD_RE.search(text))

    def _clean_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        collapsed = re.sub(r"\s+", " ", str(text)).strip()
        cleaned = self.trimmer.trim(collapsed).strip()
        cleaned = re.sub(r"^[,;:]+", "", cleaned).strip()
        cleaned = re.sub(r"[,;:]+$", "", cleaned).strip()
        return cleaned
