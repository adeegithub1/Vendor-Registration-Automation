"""
Priority Classifier.

RULES (in order)
------------------
1. If the question text explicitly signals it's mandatory (contains
   "mandatory", "required", or "must"), it's always "High" regardless
   of category — an explicit signal in the question itself overrides
   any category-based default.
2. Otherwise, priority is looked up from the question's CATEGORY:
   categories that are almost always required for vendor approval
   (Company Information, Certifications, Bank Details) default to
   "High"; unclassified questions ("Others") default to "Low"; every
   other category defaults to "Medium".

This is a simple, explainable heuristic — it does not attempt to judge
true business importance, only to give a reasonable starting priority
that a human reviewer can adjust.
"""

import re
from typing import Dict

_MANDATORY_SIGNAL_PATTERN = re.compile(r"\b(mandatory|required|must)\b", re.IGNORECASE)

_HIGH_PRIORITY_CATEGORIES = {"Company Information", "Certifications", "Bank Details"}
_LOW_PRIORITY_CATEGORIES = {"Others"}

_HIGH = "High"
_MEDIUM = "Medium"
_LOW = "Low"


class PriorityClassifier:
    """Assigns a High/Medium/Low priority to a question based on explicit signals and category."""

    def classify(self, question_text: str, category: str) -> str:
        """
        Args:
            question_text: The original question text.
            category: The category already assigned by CategoryClassifier.

        Returns:
            "High", "Medium", or "Low".
        """
        if _MANDATORY_SIGNAL_PATTERN.search(question_text):
            return _HIGH

        if category in _HIGH_PRIORITY_CATEGORIES:
            return _HIGH
        if category in _LOW_PRIORITY_CATEGORIES:
            return _LOW
        return _MEDIUM
