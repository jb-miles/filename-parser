#!/usr/bin/env python3
"""
Sequence extractor module for identifying sequence information in tokens.

Extracts:
- Part: pt. N, pt N, pN, p.N, part N, partN, part.N, part-N (may have # between)
- Scene: scene, sc, s (but sc + 4 digits = Sean Cody studio code, skip it)
- Episode: episode, ep, e
- Volume: vol, v (can be in parent directory OR filename)
- Title number: loose number at end (handled by title_extractor)
"""

import re
from typing import Optional, Dict
from .tokenizer import TokenizationResult


class SequenceExtractor:
    """Extractor for sequence information from tokens."""

    def extract_from_token(self, token_value: str, studio: Optional[str]) -> Optional[Dict[str, int]]:
        """
        Extract sequence information from a token.

        Returns dict like {"part": 2}, {"scene": 1}, {"episode": 3}, {"volume": 5}

        Args:
            token_value: The token value to check
            studio: Current studio (used to avoid false positives like Sean Cody codes)

        Returns:
            Dict with sequence type and number, or None if no sequence found
        """
        token_lower = token_value.lower().strip()

        # Part patterns: pt. N, pt N, pN, p.N, part N, partN, part.N, part-N
        part_pattern = r'(?:part|pt)[.\s-]?#?\s*(\d+)'
        if re.search(part_pattern, token_lower):
            match = re.search(part_pattern, token_lower)
            if match:
                return {"part": int(match.group(1))}

        # Shorthand part: pN or p.N or p-N
        part_short = r'\bp[.\s-]?#?\s*(\d+)\b'
        if re.search(part_short, token_lower):
            match = re.search(part_short, token_lower)
            if match:
                return {"part": int(match.group(1))}

        # Episode patterns: episode, ep, e
        episode_pattern = r'(?:episode|ep)[.\s-]?#?\s*(\d+)'
        if re.search(episode_pattern, token_lower):
            match = re.search(episode_pattern, token_lower)
            if match:
                return {"episode": int(match.group(1))}

        # Shorthand episode: eN or e.N or e-N (must be careful not to catch random 'e' words)
        episode_short = r'\be[.\s-]?#?\s*(\d+)\b'
        if re.search(episode_short, token_lower):
            match = re.search(episode_short, token_lower)
            if match:
                return {"episode": int(match.group(1))}

        # Volume patterns: vol, v
        volume_pattern = r'(?:volume|vol)[.\s-]?#?\s*(\d+)'
        if re.search(volume_pattern, token_lower):
            match = re.search(volume_pattern, token_lower)
            if match:
                return {"volume": int(match.group(1))}

        # Shorthand volume: vN or v.N or v-N
        volume_short = r'\bv[.\s-]?#?\s*(\d+)\b'
        if re.search(volume_short, token_lower):
            match = re.search(volume_short, token_lower)
            if match:
                return {"volume": int(match.group(1))}

        # Scene patterns: scene, sc, s
        # BUT: sc + 4 digits with optional dash = Sean Cody studio code, skip it
        if re.match(r'sc-?\d{4}$', token_lower):
            # This is a Sean Cody studio code, not a scene number
            return None

        scene_pattern = r'(?:scene|sc)[.\s-]?#?\s*(\d+)'
        if re.search(scene_pattern, token_lower):
            match = re.search(scene_pattern, token_lower)
            if match:
                return {"scene": int(match.group(1))}

        # Shorthand scene: sN or s.N or s-N (be careful with 's' alone)
        scene_short = r'\bs[.\s-]?#?\s*(\d+)\b'
        if re.search(scene_short, token_lower):
            match = re.search(scene_short, token_lower)
            if match:
                return {"scene": int(match.group(1))}

        return None

    def process(self, result: TokenizationResult) -> TokenizationResult:
        """
        Process tokens to extract sequence information.

        Marks tokens that contain sequence info and stores the sequences.

        Args:
            result: TokenizationResult from previous processing

        Returns:
            Updated TokenizationResult with sequence information
        """
        if not result.tokens:
            return result

        sequences = []
        studio = result.studio  # Use existing studio if available

        # Check filename tokens for sequences
        for token in result.tokens:
            if token.type not in ['path', 'date', 'studio', 'studio_code', 'performers']:
                seq = self.extract_from_token(token.value, studio)
                if seq:
                    sequences.append(seq)
                    # Mark token as sequence type
                    token.type = 'sequence'

        # Check path for volume information and extract group
        path_token = next((t for t in result.tokens if t.type == 'path'), None)
        if path_token:
            # Extract parent directory (group = immediate parent directory)
            path_parts = path_token.value.split('/')
            if len(path_parts) > 0:
                parent_dir = path_parts[-1] if path_parts[-1] else (path_parts[-2] if len(path_parts) > 1 else None)
                if parent_dir:
                    # Also check for volume in parent directory
                    vol_seq = self.extract_from_token(parent_dir, studio)
                    if vol_seq and 'volume' in vol_seq:
                        sequences.append(vol_seq)

        # Merge sequences into a single dict (last wins for duplicates)
        merged_sequence = {}
        for seq_dict in sequences:
            merged_sequence.update(seq_dict)

        # Store in result
        result.sequence = merged_sequence if merged_sequence else None

        return result
