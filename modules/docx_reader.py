"""
DOCX Reader Engine.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
This module knows how to:
  1. Safely open a .docx file and hand back a python-docx Document object.
  2. Walk every table in that document.
  3. Turn each table row into a clean, de-duplicated list of cell text,
     correctly handling MERGED CELLS (see explanation below).

This module does NOT know what a "question" or "answer" is — that logic
lives in question_detector.py. Keeping this module "dumb" (pure document
traversal only) means we can reuse it later for other DOCX tasks (Phase 8:
writing answers back) without dragging question-detection logic along
with it.

WHY MERGED CELLS NEED SPECIAL HANDLING
-----------------------------------------
python-docx represents a horizontally merged cell (e.g. one cell visually
spanning 3 columns) by returning the SAME underlying cell object at every
column position it spans, when you access `row.cells`. If we naively
treated each position in row.cells as a distinct column, a single merged
header cell like "VENDOR DETAILS" spanning 3 columns would be miscounted
as three separate cells with identical text — which would corrupt column
indexes for every module downstream.

We detect this by comparing the identity of each cell's underlying XML
element (`cell._tc`). If two consecutive positions point to the exact
same XML element, the second position is a merge continuation, not a
real distinct cell, and we skip it.

LIBRARY USED
-------------
python-docx: reads/writes .docx files. A "Document" contains "tables"
and "paragraphs". A "Table" contains "rows", each "row" contains "cells".
We only touch the parts of its API needed for reading here — writing
answers back (Phase 8) will reuse the Document object this module returns,
which is why load_document() returns the live object rather than a copy.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List

from docx import Document
from docx.document import Document as DocumentObject
from docx.table import Table, _Cell

from modules.logger import get_logger

logger = get_logger(__name__)


class DocxReadError(Exception):
    """Raised when a DOCX file cannot be opened or is not a valid file."""


@dataclass
class GridCell:
    """
    A single logical (de-duplicated) cell within a table row.

    Attributes:
        column_index: 0-based column position within the row, after
            merged-cell de-duplication.
        text: The cell's visible text, whitespace-stripped.
        cell: The original python-docx _Cell object (kept so later phases,
            like Phase 8's answer writer, can write directly into it
            without re-locating it).
    """

    column_index: int
    text: str
    cell: _Cell


def load_document(file_path: Path) -> DocumentObject:
    """
    Open a .docx file and return the python-docx Document object.

    Args:
        file_path: Path to the .docx file.

    Returns:
        A python-docx Document object.

    Raises:
        DocxReadError: If the file doesn't exist, isn't a .docx file,
            or python-docx fails to parse it (e.g. corrupted file).
    """
    if not file_path.exists():
        message = f"DOCX file not found: {file_path}"
        logger.error(message)
        raise DocxReadError(message)

    if file_path.suffix.lower() != ".docx":
        message = f"Expected a .docx file, got: {file_path.suffix} ({file_path})"
        logger.error(message)
        raise DocxReadError(message)

    try:
        document = Document(str(file_path))
    except Exception as exc:
        # python-docx can raise several different underlying exception
        # types (from the zipfile/XML layers) for a corrupted or
        # non-Word file. We normalize all of them into DocxReadError so
        # callers only need to catch one exception type.
        message = f"Failed to open DOCX file (it may be corrupted or not a valid Word file): {file_path}"
        logger.error(f"{message} | underlying error: {exc}")
        raise DocxReadError(message) from exc

    logger.info(f"Successfully loaded DOCX file: {file_path}")
    return document


def get_tables(document: DocumentObject) -> List[Table]:
    """
    Return all top-level tables in the document, in document order.

    Note: This does not recurse into tables nested inside table cells
    (a "table within a cell"). That is an edge case some vendor
    questionnaires use and is called out as a known limitation for a
    future phase, since it requires recursive traversal and careful
    handling to avoid double-counting.

    Args:
        document: A python-docx Document object from load_document().

    Returns:
        List of Table objects.
    """
    tables = document.tables
    logger.info(f"Found {len(tables)} table(s) in document.")
    return tables


def get_row_grid_cells(row) -> List[GridCell]:
    """
    Convert a table row into a de-duplicated list of GridCell objects,
    correctly collapsing horizontally merged cells into a single entry.

    Args:
        row: A python-docx _Row object (from table.rows).

    Returns:
        List of GridCell, one per LOGICAL (not raw) column in the row.
    """
    grid_cells: List[GridCell] = []
    last_seen_tc = None
    logical_column_index = 0

    for raw_cell in row.cells:
        # Compare underlying XML element identity to detect merge continuations.
        if raw_cell._tc is last_seen_tc:
            # This position is just a continuation of the previous merged
            # cell, not a new logical cell — skip it.
            continue

        grid_cells.append(
            GridCell(
                column_index=logical_column_index,
                text=raw_cell.text.strip(),
                cell=raw_cell,
            )
        )
        last_seen_tc = raw_cell._tc
        logical_column_index += 1

    return grid_cells
