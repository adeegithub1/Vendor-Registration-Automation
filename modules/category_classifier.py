"""
Category Classifier.

HOW THIS WORKS (AND ITS HONEST LIMITS)
------------------------------------------
Since this phase explicitly excludes AI, category detection is done by
KEYWORD SCORING: each category has an associated list of keywords/phrases.
A question is checked against every category's keyword list, and the
category with the most matching keywords wins. If no category has any
match at all, the question falls into "Others".

WHAT "NEVER HARDCODE CATEGORIES" MEANS HERE
------------------------------------------------
No logic anywhere is tied to a *specific question or filename* (there is
no "if question == 'Vendor Name': category = ...'" anywhere in this
codebase). The category taxonomy — the list of category names and their
associated keywords — is necessarily defined somewhere (that's simply
what a rule-based classifier is), but it lives in exactly ONE place
(CATEGORY_KEYWORDS below), is fully data-driven, and applies uniformly
to any question text, known in advance or not. Adding a new category, or
tuning an existing one, is a one-line dict change — no code logic changes.

THIS IS A HEURISTIC, NOT TRUE UNDERSTANDING
------------------------------------------------
Keyword scoring will occasionally misclassify genuinely ambiguous
questions (e.g. a question mentioning both "employees" and "safety
training" could plausibly be HR or Safety). This is an inherent
limitation of rule-based classification without AI, not a bug. If this
becomes a real accuracy problem in practice, an AI-assisted classifier
(explicitly out of scope for this phase) would be the natural upgrade.
"""

from typing import Dict, List

# Each category maps to a list of lowercase keywords/phrases. A question is
# scored per category by counting how many of that category's keywords
# appear in it (substring match, case-insensitive). Order of the dict
# does NOT affect scoring, but does act as the tie-breaker when two
# categories score equally (earlier entry wins) — keeping "Others" as a
# fallback, not a dict entry, guarantees it's never picked except when no
# category has any match at all.
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Company Information": [
        "company name", "vendor name", "registered address", "registered office",
        "year of establishment", "incorporation", "constitution of firm",
        "ownership", "ceo", "managing director", "board of directors",
        "number of employees", "company profile", "website", "pan number",
        "legal status", "years in business", "annual turnover", "group company",
        "subsidiary", "parent company", "email", "phone", "contact number",
        "mobile number", "fax", "gst",
    ],
    "Manufacturing": [
        "manufactur", "plant", "factory", "production capacity", "machinery",
        "production process", "assembly line", "shop floor", "tooling",
        "in-house production", "installed capacity",
    ],
    "Quality": [
        "quality control", "quality assurance", "quality manual", "inspection",
        "defect", "aql", "control plan", "quality policy", "testing procedure",
        "calibration", "non-conformance",
    ],
    "Certifications": [
        "iso", "certificate", "certification", "accreditation", "ce mark",
        "ohsas", "compliance standard", "audit report",
    ],
    "Bank Details": [
        "bank name", "account number", "ifsc", "swift code", "bank branch",
        "beneficiary", "bank account", "cancelled cheque",
    ],
    "Technical": [
        "technical specification", "drawing", "cad file", "tolerance",
        "material grade", "engineering", "design capability", "prototype",
    ],
    "Commercial": [
        "price", "pricing", "payment terms", "delivery lead time",
        "minimum order quantity", "moq", "invoice", "credit period",
        "discount", "quotation", "purchase order", "freight terms", "incoterms",
    ],
    "Safety": [
        "safety policy", "ppe", "hazard", "workplace accident", "fire safety",
        "emergency procedure", "occupational safety", "safety training",
    ],
    "Environment": [
        "environment policy", "pollution control", "waste management",
        "emission", "sustainability", "carbon footprint", "recycl",
        "effluent treatment",
    ],
    "HR": [
        "human resource", "workforce strength", "employee training",
        "labor law", "staff strength", "attendance policy", "employee welfare",
        "recruitment policy", "workforce",
    ],
}

OTHERS_CATEGORY = "Others"


class CategoryClassifier:
    """Classifies a question's text into one of the categories in CATEGORY_KEYWORDS, or 'Others'."""

    def __init__(self, category_keywords: Dict[str, List[str]] = CATEGORY_KEYWORDS):
        self.category_keywords = category_keywords

    def classify(self, question_text: str) -> str:
        """
        Args:
            question_text: The original question text.

        Returns:
            The best-matching category name, or "Others" if no keyword
            from any category appears in the question.
        """
        text_lower = question_text.lower()

        best_category = OTHERS_CATEGORY
        best_score = 0

        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > best_score:
                best_score = score
                best_category = category

        return best_category
