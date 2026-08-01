"""
Shared data models for the Company Knowledge Extraction Engine.

WHY A SEPARATE MODELS FILE
-----------------------------
ProcessedDocument is used by document_processors/, document_manager.py,
AND knowledge_exporter.py. If we defined it inside one of those modules,
the others would have to import it from a place that isn't really its
"home", which tends to create circular imports as a project grows
(processors importing from the manager, the manager importing from
processors, etc). Putting shared models in their own file with no
dependencies on the rest of the app avoids that entirely.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ProcessedDocument(BaseModel):
    """
    The structured result of extracting one company document.
    This is exactly what gets saved to temp/documents/<slug>.json.
    """

    filename: str = Field(..., description="Original filename, e.g. 'Company Profile.pdf'.")
    extension: str = Field(..., description="Lowercase file extension including the dot, e.g. '.pdf'.")
    document_type: str = Field(..., description="Human-readable type: 'PDF', 'WORD', or 'EXCEL'.")
    file_size_bytes: int = Field(..., description="Size of the original file on disk, in bytes.")
    num_pages: Optional[int] = Field(default=None, description="Page count, if applicable (PDF only).")
    num_sheets: Optional[int] = Field(default=None, description="Sheet count, if applicable (Excel only).")
    total_characters: int = Field(..., description="Length of the cleaned extracted_text.")
    extracted_text: str = Field(..., description="Cleaned, unmodified text content of the document.")
    status: str = Field(..., description="'success' or 'failed'.")
    error_message: Optional[str] = Field(default=None, description="Populated only when status is 'failed'.")


class KnowledgeIndexEntry(BaseModel):
    """One row of temp/knowledge_index.json, pointing at a ProcessedDocument's JSON file."""

    id: int = Field(..., description="Sequential ID, unique across the index.")
    filename: str = Field(..., description="Original filename of the source document.")
    type: str = Field(..., description="Document type: 'PDF', 'WORD', or 'EXCEL'.")
    path: str = Field(..., description="Project-root-relative path to the document's JSON file.")
    status: str = Field(..., description="'success' or 'failed', mirrors ProcessedDocument.status.")


class Location(BaseModel):
    """
    Where in the original questionnaire this question's answer belongs.

    NOTE ON FIELD NAMING: Phase 2's QuestionItem uses `answer_column` (a
    0-based column index) to describe this same position. Phase 4's spec
    calls the equivalent field `cell` — they are the same value, just
    named differently to match each phase's own vocabulary. We map
    answer_column -> cell when building this object (see
    modules/question_intelligence_engine.py).
    """

    table: int = Field(..., description="1-based index of the table within the questionnaire document.")
    row: int = Field(..., description="1-based index of the row within that table.")
    cell: int = Field(..., description="0-based column index of the cell where the answer should be written.")


class QuestionObject(BaseModel):
    """
    A questionnaire question enriched with a structured understanding of
    what it's asking, ready to be handed to Claude in a later phase.
    This is exactly what gets saved to temp/question_objects.json.
    """

    id: int = Field(..., description="Matches the question_id from Phase 2's questions.json.")
    original_question: str = Field(..., description="The exact question text as extracted in Phase 2.")
    intent: str = Field(..., description="A cleaned-up, concise paraphrase of what's being asked.")
    expected_answer_type: str = Field(..., description="e.g. 'Text', 'Number', 'Date', 'Yes / No', 'Email', etc.")
    possible_document: str = Field(..., description="Rule-based prediction of which company document likely has the answer.")
    category: str = Field(..., description="e.g. 'Company Information', 'Manufacturing', 'Certifications', etc.")
    priority: str = Field(..., description="'High', 'Medium', or 'Low'.")
    location: Location = Field(..., description="Where this question's answer belongs in the original questionnaire.")


class AnswerObject(BaseModel):
    """
    An AI-generated answer to one questionnaire question.
    This is exactly what gets saved to temp/generated_answers.json.
    """

    question_id: int = Field(..., description="Matches the id from a QuestionObject.")
    answer: str = Field(..., description="The generated answer text, or 'NOT FOUND' if it couldn't be determined.")
    confidence: int = Field(..., ge=0, le=100, description="0-100. Always 0 when answer is 'NOT FOUND'.")
    source_document: str = Field(default="", description="Filename of the company document the answer came from, if any.")


class FillResult(BaseModel):
    """
    The outcome of attempting to write one question's answer into the
    original questionnaire document. Not persisted to disk (Phase 6 has
    no JSON output requirement) -- used for the console summary and to
    drive the required per-question log line (Question ID, Question Text,
    Inserted Answer, Word Position, Success/Failed).
    """

    question_id: int = Field(..., description="Matches the id from a QuestionObject.")
    question_text: str = Field(..., description="The original question text, for log readability.")
    inserted_answer: str = Field(..., description="The answer text that was written (or attempted).")
    word_position: str = Field(default="", description="Human-readable location, e.g. 'Table 1, Row 3, Cell 1'.")
    status: str = Field(..., description="'success' or 'failed'.")
    error_message: Optional[str] = Field(default=None, description="Populated only when status is 'failed'.")
