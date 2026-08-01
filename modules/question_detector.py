"""
Question Detector.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Given a loaded DOCX document, this module decides which table cells are
"questions" and which are their matching (currently empty) "answer"
cells, and produces a structured, validated list of QuestionItem objects.

This is a HEURISTIC, not a final solution. It intentionally does not use
any AI — it uses simple, explainable rules based on cell position and
content. Your development plan has a dedicated Phase 6 ("Question
Detection") to make this smarter (e.g. handling questions that aren't in
tables, multi-row questions, or ambiguous layouts). For now, this covers
the common vendor-questionnaire pattern: a table row containing one cell
with question text and one empty cell where the answer belongs.

DETECTION RULES (in order)
-----------------------------
For each row in each table:
  1. Build the row's logical cells (merged cells already de-duplicated
     by docx_reader.get_row_grid_cells).
  2. A cell is an ANSWER CANDIDATE if it is empty after stripping whitespace.
  3. A cell is a QUESTION CANDIDATE if it has text, and that text is not
     just a serial number / row label (e.g. "1", "(2)", "Sr", "Q3").
  4. If the row has NO answer candidates (nothing empty to fill) OR NO
     question candidates, the row is skipped — this naturally skips
     header rows (all cells filled with labels like "Question"/"Answer")
     and rows that are already fully answered.
  5. If there are multiple question candidates, the one with the longest
     text is chosen (most likely to be the actual question rather than a
     short label).
  6. If there are multiple answer candidates, the empty cell closest to
     the right of the chosen question column is chosen; if none exist to
     the right, the closest one on the left is used instead.

WHY A SERIAL-NUMBER FILTER IS NEEDED
----------------------------------------
Many vendor questionnaires have a "Sr. No." column: ["1", "Vendor Name", ""].
Without filtering, "1" would incorrectly be picked as if it could be a
question. The filter (`_is_serial_or_label`) rejects short, purely
numeric-looking cells.

DATA MODEL
-----------
QuestionItem is a Pydantic model, not a plain dict. This guarantees every
question written to JSON has the correct types and required fields —
if a bug ever produced a malformed entry, this raises immediately
during construction, not silently later.
"""

import json
import re
from pathlib import Path
from typing import List, Optional

from docx.document import Document as DocumentObject
from pydantic import BaseModel, Field

from modules.docx_reader import GridCell, get_row_grid_cells, get_tables
from modules.logger import get_logger

logger = get_logger(__name__)

# Matches cells that are just serial numbers / row labels, e.g.:
# "1", "1.", "(1)", "01", "Q1", "Sr" — these should never be treated
# as the question text itself.
_SERIAL_PATTERN = re.compile(r"^[\(\[]?\s*(no\.?|sr\.?|s\.?no\.?|q)?\s*\d+\s*[\)\].]?$", re.IGNORECASE)

# A question candidate must have at least this many characters, to avoid
# treating short stray labels (e.g. "Y/N", "NA") as questions.
_MIN_QUESTION_TEXT_LENGTH = 3


class QuestionItem(BaseModel):
    """A single detected question and where its answer should be written."""

    question_id: int = Field(..., description="Sequential ID, unique across the whole document.")
    question: str = Field(..., description="The extracted question text.")
    table: int = Field(..., description="1-based index of the table within the document.")
    row: int = Field(..., description="1-based index of the row within that table.")
    question_column: int = Field(..., description="0-based logical column index of the question cell.")
    answer_column: int = Field(..., description="0-based logical column index of the answer cell.")
    answer: str = Field(default="", description="Left empty in Phase 2 — filled in a later phase.")


def _is_serial_or_label(text: str) -> bool:
    """Return True if text looks like a serial number / row label, not a real question."""
    return bool(_SERIAL_PATTERN.match(text.strip()))


def _select_question_cell(candidates: List[GridCell]) -> GridCell:
    """From multiple question candidates in a row, pick the one most likely to be the real question."""
    return max(candidates, key=lambda gc: len(gc.text))


def _select_answer_cell(candidates: List[GridCell], question_column: int) -> GridCell:
    """
    From multiple empty candidates in a row, pick the one that best matches
    the chosen question column: prefer the nearest empty cell to the right,
    falling back to the nearest one on the left.
    """
    to_the_right = [gc for gc in candidates if gc.column_index > question_column]
    if to_the_right:
        return min(to_the_right, key=lambda gc: gc.column_index - question_column)

    to_the_left = [gc for gc in candidates if gc.column_index < question_column]
    if to_the_left:
        return min(to_the_left, key=lambda gc: question_column - gc.column_index)

    # Shouldn't happen (an answer candidate can't share the question's own
    # column, since that column is non-empty by definition), but guard anyway.
    return candidates[0]


def _detect_row_question(grid_cells: List[GridCell]) -> Optional[dict]:
    """
    Apply the detection rules to a single row's grid cells.

    Returns:
        A dict with question_column/question_text/answer_column, or None
        if this row doesn't look like a fillable question row.
    """
    answer_candidates = [gc for gc in grid_cells if gc.text == ""]
    question_candidates = [
        gc
        for gc in grid_cells
        if gc.text != ""
        and len(gc.text) >= _MIN_QUESTION_TEXT_LENGTH
        and not _is_serial_or_label(gc.text)
    ]

    if not answer_candidates or not question_candidates:
        return None

    question_cell = _select_question_cell(question_candidates)
    answer_cell = _select_answer_cell(answer_candidates, question_cell.column_index)

    return {
        "question_text": question_cell.text,
        "question_column": question_cell.column_index,
        "answer_column": answer_cell.column_index,
    }


def detect_questions(document: DocumentObject) -> List[QuestionItem]:
    """
    Scan every table in the document and extract all detected questions.

    Args:
        document: A python-docx Document object (from docx_reader.load_document).

    Returns:
        List of QuestionItem, in document order, with sequential question_id
        values starting at 1.
    """
    questions: List[QuestionItem] = []
    next_question_id = 1

    tables = get_tables(document)

    for table_index, table in enumerate(tables, start=1):
        for row_index, row in enumerate(table.rows, start=1):
            grid_cells = get_row_grid_cells(row)
            detected = _detect_row_question(grid_cells)

            if detected is None:
                continue

            question_item = QuestionItem(
                question_id=next_question_id,
                question=detected["question_text"],
                table=table_index,
                row=row_index,
                question_column=detected["question_column"],
                answer_column=detected["answer_column"],
                answer="",
            )
            questions.append(question_item)
            next_question_id += 1

    logger.info(f"Detected {len(questions)} question(s) across {len(tables)} table(s).")
    return questions


def save_questions_json(questions: List[QuestionItem], output_path: Path) -> None:
    """
    Save detected questions to a JSON file.

    Args:
        questions: List of QuestionItem to save.
        output_path: Full path to the JSON file to write (parent folder
            is created automatically if missing).

    Raises:
        OSError: If the file cannot be written (e.g. permissions issue,
            disk full). Logged and re-raised so the caller can decide
            how to handle it.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        payload = [q.model_dump() for q in questions]
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error(f"Failed to write questions JSON to {output_path}: {exc}")
        raise

    logger.info(f"Saved {len(questions)} question(s) to {output_path}")
