"""
Answer Type Classifier.

WHY RULE ORDER MATTERS
-------------------------
Answer type detection uses an ORDERED list of (pattern, answer_type)
rules — the first rule that matches wins. This matters because some
question phrasings are ambiguous under a naive "check everything, use
any match" approach:

    "Do you have a valid GST registration number?"

This sentence starts like a yes/no question ("Do you have...") but is
really asking for a number. To handle this correctly, SPECIFIC content
signals (email, phone, date, certificate/registration number, address)
are checked BEFORE the generic yes/no sentence-structure check — so a
question that mentions a concrete data type wins over a generic phrasing
pattern, even if both technically match.

THIS IS STILL A HEURISTIC
----------------------------
No rule-based system will get every phrasing right. Genuinely ambiguous
or unusually worded questions may be misclassified; the fallback is
always "Text", which is always a safe (if imprecise) default since free
text can hold any answer.
"""

import re
from typing import List, Pattern, Tuple

# Each rule is (compiled regex, answer_type). Evaluated in order; first match wins.
_ANSWER_TYPE_RULES: List[Tuple[Pattern, str]] = [
    (re.compile(r"\bemail\b", re.IGNORECASE), "Email"),
    (re.compile(r"\b(phone|mobile|contact number|fax)\b", re.IGNORECASE), "Phone"),
    (re.compile(r"\b(date|when|valid until|expiry|expiration|year of)\b", re.IGNORECASE), "Date"),
    (
        re.compile(
            r"\b(certificate number|certification number|license number|licence number|"
            r"registration number|gst number|pan number|iso number)\b",
            re.IGNORECASE,
        ),
        "Certificate Number",
    ),
    (re.compile(r"\b(address|located at|location of|situated)\b", re.IGNORECASE), "Address"),
    (re.compile(r"\b(tick|check the box|select all that apply|checkbox)\b", re.IGNORECASE), "Checkbox"),
    (re.compile(r"\b(list of|list all|enumerate|provide a list)\b", re.IGNORECASE), "List"),
    (
        re.compile(r"\b(describe|explain|elaborate|provide details of|give details of)\b", re.IGNORECASE),
        "Multi-line Text",
    ),
    (
        re.compile(
            r"\b(how many|number of|quantity|capacity|percentage|turnover|revenue|"
            r"headcount|strength)\b|%",
            re.IGNORECASE,
        ),
        "Number",
    ),
    (
        re.compile(
            r"^\s*(do you|does the company|does your|is the|is your|are you|"
            r"have you|can you|will you)\b",
            re.IGNORECASE,
        ),
        "Yes / No",
    ),
]

_DEFAULT_ANSWER_TYPE = "Text"


class AnswerTypeClassifier:
    """Determines the expected answer type (Text, Number, Date, etc.) for a question."""

    def __init__(self, rules: List[Tuple[Pattern, str]] = _ANSWER_TYPE_RULES):
        self.rules = rules

    def classify(self, question_text: str) -> str:
        """
        Args:
            question_text: The original question text.

        Returns:
            The first matching answer type from the ordered rule list,
            or "Text" if nothing matches.
        """
        for pattern, answer_type in self.rules:
            if pattern.search(question_text):
                return answer_type
        return _DEFAULT_ANSWER_TYPE
