"""
Source Predictor.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Predicts which company document is most likely to contain the answer to
a given question, using rule-based logic only (no AI, no searching
actual document content — that's explicitly out of scope for this
phase; this only predicts a document TYPE/NAME based on the question's
wording and category).

TWO-TIER PRECEDENCE
----------------------
1. SPECIFIC keyword rules are checked first (e.g. a question mentioning
   "GST" predicts "GST Certificate" regardless of what category it was
   classified into).
2. If no specific keyword matches, the question's already-determined
   CATEGORY is used to look up a sensible default document
   (e.g. "Bank Details" category -> "Bank Details" document).

This mirrors the same "specific signal beats generic fallback" precedence
principle used in answer_type_classifier.py.
"""

import re
from typing import Dict, List, Pattern, Tuple

# (compiled regex, predicted document). Evaluated in order; first match wins.
_SOURCE_KEYWORD_RULES: List[Tuple[Pattern, str]] = [
    (re.compile(r"\biso\b|\bcertificat", re.IGNORECASE), "ISO Certificate"),
    (re.compile(r"\bgst\b", re.IGNORECASE), "GST Certificate"),
    (re.compile(r"\bpan\b", re.IGNORECASE), "PAN Card"),
    (re.compile(r"\b(bank|ifsc|account number|swift code)\b", re.IGNORECASE), "Bank Details"),
    (re.compile(r"\borgani[sz]ation chart\b|\borg chart\b|\bhierarchy\b", re.IGNORECASE), "Organization Chart"),
    (re.compile(r"\bquality manual\b|\bquality polic|\binspection process\b", re.IGNORECASE), "Quality Manual"),
    (re.compile(r"\bcatalogue\b|\bcatalog\b|\bproduct range\b|\bproduct list\b", re.IGNORECASE), "Product Catalogue"),
    (re.compile(r"\bmanufactur|\bplant\b|\bfactory\b|\bproduction capacity\b", re.IGNORECASE), "Manufacturing Details"),
    (re.compile(r"\btechnical specification\b|\bdrawing\b|\bcad\b", re.IGNORECASE), "Technical Documents"),
]

# Fallback when no specific keyword rule matches: derived from the question's category.
_CATEGORY_DEFAULT_SOURCE: Dict[str, str] = {
    "Company Information": "Company Profile",
    "Manufacturing": "Manufacturing Details",
    "Quality": "Quality Manual",
    "Certifications": "ISO Certificate",
    "Bank Details": "Bank Details",
    "Technical": "Technical Documents",
    "Commercial": "Company Profile",
    "Safety": "Quality Manual",
    "Environment": "Quality Manual",
    "HR": "Organization Chart",
    "Others": "Company Profile",
}

_DEFAULT_SOURCE = "Company Profile"


class SourcePredictor:
    """Predicts the likely source document for a question, using keyword rules with a category-based fallback."""

    def __init__(
        self,
        keyword_rules: List[Tuple[Pattern, str]] = _SOURCE_KEYWORD_RULES,
        category_defaults: Dict[str, str] = _CATEGORY_DEFAULT_SOURCE,
    ):
        self.keyword_rules = keyword_rules
        self.category_defaults = category_defaults

    def predict(self, question_text: str, category: str) -> str:
        """
        Args:
            question_text: The original question text.
            category: The category already assigned by CategoryClassifier.

        Returns:
            The predicted document name/type.
        """
        for pattern, predicted_source in self.keyword_rules:
            if pattern.search(question_text):
                return predicted_source

        return self.category_defaults.get(category, _DEFAULT_SOURCE)
