"""
Intent Extractor.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Produces a short, concise paraphrase of what a question is actually
asking for, by stripping common boilerplate lead-in phrases
("Please provide your...", "Kindly specify...", "What is the...") and
trailing punctuation.

Example:
    "Please provide your Manufacturing Plant Address."
    -> "Manufacturing Plant Address"

HOW IT WORKS
-------------
An ORDERED list of lead-in regex patterns is tried against the start of
the question. The first one that matches is stripped. If none match, the
original question is used as-is (minus trailing punctuation) — this is a
safe fallback, since an unrecognized phrasing simply means we show the
full original question as the "intent" rather than guessing.
"""

import re
from typing import List, Pattern

# Ordered list of lead-in phrases to strip from the START of a question.
# Longer/more specific patterns are listed first to avoid a shorter
# pattern accidentally matching only part of a longer boilerplate phrase.
_LEAD_IN_PATTERNS: List[Pattern] = [
    re.compile(r"^please\s+(provide|share|mention|specify|state|confirm|furnish|describe|explain|elaborate\s+on|elaborate)\s+(us\s+with\s+)?(your|the)?\s*", re.IGNORECASE),
    re.compile(r"^kindly\s+(provide|share|mention|specify|state|confirm|furnish|describe|explain|elaborate\s+on|elaborate)\s+(your|the)?\s*", re.IGNORECASE),
    re.compile(r"^what\s+is\s+(your|the)\s+", re.IGNORECASE),
    re.compile(r"^what\s+are\s+(your|the)\s+", re.IGNORECASE),
    re.compile(r"^do\s+you\s+have\s+(a|an|any)?\s*", re.IGNORECASE),
    re.compile(r"^does\s+the\s+company\s+have\s+(a|an|any)?\s*", re.IGNORECASE),
    re.compile(r"^mention\s+(your|the)\s+", re.IGNORECASE),
    re.compile(r"^state\s+(your|the)\s+", re.IGNORECASE),
    re.compile(r"^provide\s+(your|the)\s+", re.IGNORECASE),
    re.compile(r"^describe\s+(your|the)\s+", re.IGNORECASE),
    re.compile(r"^explain\s+(your|the)\s+", re.IGNORECASE),
]

_TRAILING_PUNCTUATION_PATTERN = re.compile(r"[\s\.\?]+$")


class IntentExtractor:
    """Strips common boilerplate lead-in phrasing to produce a concise question intent."""

    def __init__(self, lead_in_patterns: List[Pattern] = _LEAD_IN_PATTERNS):
        self.lead_in_patterns = lead_in_patterns

    def extract(self, question_text: str) -> str:
        """
        Args:
            question_text: The original question text.

        Returns:
            A concise intent phrase, with boilerplate lead-ins and
            trailing punctuation removed, first letter capitalized.
        """
        text = question_text.strip()

        for pattern in self.lead_in_patterns:
            stripped = pattern.sub("", text)
            if stripped != text:
                text = stripped
                break

        text = _TRAILING_PUNCTUATION_PATTERN.sub("", text).strip()

        if not text:
            # Stripping left nothing meaningful (e.g. an unusual/very short
            # question) -- fall back to the original text rather than
            # returning an empty intent.
            text = question_text.strip().rstrip(".?").strip()

        return text[0].upper() + text[1:] if text else text
