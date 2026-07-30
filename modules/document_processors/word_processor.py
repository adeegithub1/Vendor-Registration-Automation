"""
Word Processor.

LIBRARY USED: python-docx
---------------------------
Same library used in Phase 2. Rather than writing new DOCX-opening code,
this processor REUSES modules/docx_reader.py — specifically load_document()
(safe file opening with clear errors) and get_tables() / get_row_grid_cells()
(merged-cell-safe table traversal). This avoids duplicating the merged-cell
handling logic we already built and tested in Phase 2, and means any future
bugfix to that traversal logic benefits both Phase 2's question detection
and Phase 3's knowledge extraction automatically.

WHAT GETS EXTRACTED
---------------------
- All top-level paragraph text (document.paragraphs), in document order.
- All table content, per table, with each row's cells joined by " | ".
Paragraphs and tables are extracted as two separate sections rather than
perfectly interleaved in original document order — python-docx does not
expose a simple ordered stream of "paragraph or table, in original
sequence" without deeper XML traversal. For knowledge extraction (as
opposed to visual reproduction), having all the information present
matters more than preserving exact interleaving, so this is an accepted,
documented simplification for this phase.

NOTE ON PAGE COUNT
--------------------
Unlike PDFs, DOCX files don't reliably store a true page count without
the document being rendered/paginated by Word itself. Rather than fake a
number, num_pages is left as None for Word documents.
"""

from pathlib import Path

from modules.document_processors.base_processor import BaseDocumentProcessor, RawExtraction
from modules.docx_reader import DocxReadError, get_row_grid_cells, get_tables, load_document


class WordProcessor(BaseDocumentProcessor):
    """Extracts text (paragraphs + tables) from .docx files."""

    document_type = "WORD"

    def _extract(self, file_path: Path) -> RawExtraction:
        try:
            document = load_document(file_path)
        except DocxReadError as exc:
            # Normalize to a plain RuntimeError so DocumentManager only needs
            # to handle generic exceptions, not know about docx_reader internals.
            raise RuntimeError(str(exc)) from exc

        paragraph_texts = [p.text for p in document.paragraphs if p.text.strip()]

        table_sections = []
        for table_index, table in enumerate(get_tables(document), start=1):
            row_lines = []
            for row in table.rows:
                grid_cells = get_row_grid_cells(row)
                row_text = " | ".join(gc.text for gc in grid_cells if gc.text)
                if row_text:
                    row_lines.append(row_text)
            if row_lines:
                table_sections.append(f"[Table {table_index}]\n" + "\n".join(row_lines))

        full_text = "\n\n".join(paragraph_texts + table_sections)
        return RawExtraction(text=full_text, num_pages=None, num_sheets=None)
