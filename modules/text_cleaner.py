"""
Text Cleaner.

WHY THIS EXISTS
----------------
Text extracted from PDFs/DOCX/XLSX is frequently messy: repeated spaces
from column alignment, runs of blank lines from page breaks, and invisible
control characters (like a stray BOM \\ufeff character) that don't show up
visually but can confuse downstream processing (e.g. Claude API calls in
Phase 5). This module does ONLY cosmetic cleanup — it never changes,
removes, or summarizes actual information, per the project requirements.

WHAT IT DOES
-------------
1. Strips invisible/control characters (keeping normal newlines and tabs).
2. Normalizes line endings (\\r\\n and \\r both become \\n).
3. Collapses runs of spaces/tabs into a single space.
4. Trims trailing/leading whitespace on every line.
5. Collapses 3+ consecutive blank lines down to a single blank line.

WHAT IT DELIBERATELY DOES NOT DO
------------------------------------
- Does not remove any words, numbers, or sentences.
- Does not reorder or rewrite content.
- Does not summarize.
This keeps the extracted knowledge a faithful, complete copy of the
source document — only whitespace/formatting noise is removed.
"""

import re

# Control characters (excluding \n and \t, which we want to keep) plus the
# UTF-8 byte-order-mark character, which sometimes appears at the start of
# text extracted from Word/Excel files.
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufeff]")

# 2 or more spaces/tabs in a row -> single space
_REPEATED_WHITESPACE_PATTERN = re.compile(r"[ \t]+")

# 3 or more consecutive newlines -> exactly 2 (i.e. at most one blank line)
_EXCESS_BLANK_LINES_PATTERN = re.compile(r"\n{3,}")


def clean_text(raw_text: str) -> str:
    """
    Clean extracted document text of formatting noise, without altering
    any actual information.

    Args:
        raw_text: The unmodified text as extracted from a document.

    Returns:
        Cleaned text. Returns an empty string if raw_text is empty or None.
    """
    if not raw_text:
        return ""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS_PATTERN.sub("", text)
    text = _REPEATED_WHITESPACE_PATTERN.sub(" ", text)

    # Strip leading/trailing whitespace from every individual line.
    text = "\n".join(line.strip() for line in text.split("\n"))

    text = _EXCESS_BLANK_LINES_PATTERN.sub("\n\n", text)

    return text.strip()
