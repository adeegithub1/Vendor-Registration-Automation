# Vendor Questionnaire AI

An AI application that automatically fills vendor questionnaires (DOCX/XLSX)
using a company's own documents (profile, certificates, catalogues, etc.),
without ever recreating or reformatting the original file.

**Current status: Phase 4 — AI Question Intelligence Engine** (rule-based
question classification; Claude integration comes in Phase 5).

## Folder structure

```
Vendor-AI/
├── app.py                  # Entry point (setup check + --read-docx + --extract-knowledge + --classify-questions)
├── config.py                # Centralized, typed configuration (reads .env)
├── requirements.txt
├── .env.example              # Template for your local .env (copy this)
├── .gitignore
├── uploads/
│   ├── company_documents/    # Put a company's source documents here
│   └── questionnaire/        # Put the vendor questionnaire to fill here
├── output/                   # Completed questionnaires are saved here
├── logs/                     # Rotating application log files
├── temp/
│   ├── questions.json          # Phase 2 output: detected questionnaire questions
│   ├── question_objects.json    # Phase 4 output: questions enriched with category/type/source/priority
│   ├── knowledge_index.json     # Phase 3 output: manifest of extracted company documents
│   └── documents/                # Phase 3 output: one JSON per extracted company document
├── modules/
│   ├── __init__.py
│   ├── logger.py                 # Centralized logging setup
│   ├── docx_reader.py              # Phase 2: opens DOCX, traverses tables/rows/cells safely
│   ├── question_detector.py         # Phase 2: heuristic question/answer cell detection
│   ├── models.py                     # Shared Pydantic models (ProcessedDocument, QuestionObject, etc.)
│   ├── text_cleaner.py                # Phase 3: whitespace/formatting cleanup (no content changes)
│   ├── document_manager.py             # Phase 3: scans folder, orchestrates processing, error-tolerant
│   ├── knowledge_exporter.py            # Phase 3: writes per-document JSON + knowledge_index.json
│   ├── document_processors/
│   │   ├── __init__.py                   # PROCESSOR_REGISTRY: extension -> processor class
│   │   ├── base_processor.py              # Abstract base (Template Method pattern)
│   │   ├── pdf_processor.py                # PyMuPDF-based PDF extraction
│   │   ├── word_processor.py               # Reuses docx_reader for table-safe extraction
│   │   └── excel_processor.py              # openpyxl-based Excel extraction
│   ├── question_loader.py               # Phase 4: loads + validates temp/questions.json
│   ├── category_classifier.py            # Phase 4: rule-based category keyword scoring
│   ├── answer_type_classifier.py          # Phase 4: rule-based answer type detection
│   ├── source_predictor.py                 # Phase 4: rule-based likely-source-document prediction
│   ├── priority_classifier.py               # Phase 4: rule-based High/Medium/Low priority
│   ├── intent_extractor.py                   # Phase 4: strips boilerplate to get a concise intent
│   └── question_intelligence_engine.py        # Phase 4: orchestrates all 5 classifiers, error-tolerant
└── prompts/                  # (Phase 5+) Claude prompt templates
```

## Setup

1. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Copy the environment template and add your real Claude API key:
   ```
   cp .env.example .env
   ```
   Then open `.env` and replace `your-claude-api-key-here` with your real
   Anthropic API key from https://console.anthropic.com/

4. Run the Phase 1 setup check:
   ```
   python app.py
   ```
   You should see `Status: ALL CHECKS PASSED` along with a summary of the
   folders and configuration that were verified. A log file will also be
   created at `logs/vendor_ai.log`.

## Usage: Phase 2 — reading a questionnaire

To read a DOCX questionnaire and detect its questions:

```
python app.py --read-docx path/to/questionnaire.docx
```

This will:
1. Open the DOCX and traverse every table, row, and cell (handling merged cells correctly).
2. Detect which cells look like questions and which are their empty answer cells.
3. Save the result to `temp/questions.json`.

**Note on detection accuracy:** the question/answer detection in Phase 2 is a
rule-based heuristic (empty cell = answer, adjacent non-empty non-numeric
cell = question). It correctly skips header rows and already-answered rows,
and handles merged cells and Sr.No. columns, but it does not yet understand
questions that live outside of tables (e.g. plain paragraphs) or highly
irregular layouts. That refinement is planned for Phase 6 (Question Detection).

## Usage: Phase 3 — extracting company knowledge

Put company documents (PDF, DOCX, XLSX) into `uploads/company_documents/`,
then run:

```
python app.py --extract-knowledge
```

This will:
1. Scan the folder and automatically detect every supported file — no
   filenames are hardcoded, so adding or removing files just works.
2. Extract text (and page/sheet counts where applicable) from each one,
   using the processor registered for its extension.
3. Clean the text (remove extra whitespace, blank lines, hidden characters)
   without altering, summarizing, or rewriting any actual content.
4. Save each document to its own file: `temp/documents/<slug>.json`.
5. Save `temp/knowledge_index.json`, a manifest listing every document,
   its type, and where to find its full JSON.

If one document fails to process (corrupted file, unsupported internal
format, etc.), it's logged and recorded with `"status": "failed"` in the
index — the rest of the batch still completes.

**Known limitations, tested and documented, not hidden:** legacy `.xls`
files aren't supported (only modern `.xlsx`/`.xlsm` — an openpyxl
limitation); Excel formula cells with no cached calculated value (only
possible with workbooks never opened/saved in real Excel) extract as empty
for that cell rather than crashing.

## Usage: Phase 4 — classifying questions

After running Phase 2 (so `temp/questions.json` exists), run:

```
python app.py --classify-questions
```

This will:
1. Load and validate `temp/questions.json`.
2. For every question, determine: category, expected answer type, likely
   source document, priority, and a concise "intent" phrase — all via
   rule-based logic (no AI, no reading of company document content).
3. Save the enriched results to `temp/question_objects.json`.

**Note on classification accuracy:** this is keyword/pattern-based, not true
language understanding. In testing against a 16-question sample spanning
every category, tuning was needed to catch phrasings like "Email address"
or "GST registered" that don't contain an obvious category keyword by
default — the keyword lists in `category_classifier.py` were expanded as a
direct result. Expect similar tuning to be useful once this runs against
your real client questionnaires; the keyword lists are centralized in a
few small files specifically so that's easy.

### Module-by-module explanation: Phase 3

**`modules/models.py`** — Defines `ProcessedDocument` (the full extraction
result for one file), `KnowledgeIndexEntry` (one row of the manifest),
and — as of Phase 4 — `QuestionObject`/`Location`, as Pydantic models, so
every module that touches this data gets automatic validation instead of
passing raw, unchecked dicts around.

**`modules/text_cleaner.py`** — A single `clean_text()` function used by
every processor. Strips invisible/control characters, collapses repeated
spaces and blank lines. Deliberately does **not** touch actual content —
no summarizing, no rewriting.

**`modules/document_processors/base_processor.py`** — `BaseDocumentProcessor`
is an abstract class implementing the *Template Method* pattern: it handles
everything common to all formats (measuring file size, cleaning text,
assembling the result) in one concrete `process()` method, and delegates
only the format-specific extraction step to an abstract `_extract()` that
each subclass implements.

**`modules/document_processors/pdf_processor.py`** — `PDFProcessor` uses
**PyMuPDF** (`fitz`) to open PDFs and pull each page's text layer plus the
page count. Scanned/image-only PDFs will correctly extract as empty text
(no text layer to read) — OCR support is a planned future phase.

**`modules/document_processors/word_processor.py`** — `WordProcessor` uses
**python-docx**, reusing Phase 2's `docx_reader.py` for merged-cell-safe
table traversal. Extracts all paragraphs plus all table content (as
separate sections — see the module's docstring for why perfect document-order
interleaving is a documented simplification here, not a bug).

**`modules/document_processors/excel_processor.py`** — `ExcelProcessor` uses
**openpyxl** in `read_only=True, data_only=True` mode: read-only for lower
memory use on large sheets, data-only so formula cells return their last
*calculated* value rather than the formula text.

**`modules/document_processors/__init__.py`** — `PROCESSOR_REGISTRY`, a dict
mapping file extension → processor class. This is the single place that
would need a one-line addition to support a new format (e.g. OCR for
images) — no other code needs to change.

**`modules/document_manager.py`** — `DocumentManager` scans the folder,
looks up the right processor for each file via the registry, and is the
only place that catches per-file exceptions so one bad document never
stops the batch. Logs a summary (found/processed/failed/characters/time).

**`modules/knowledge_exporter.py`** — `KnowledgeExporter` writes each
`ProcessedDocument` to its own JSON file (filename generated via a
collision-safe "slugify" of the original filename) and builds
`knowledge_index.json`.

### Module-by-module explanation: Phase 4

**`modules/question_loader.py`** — Loads and validates `temp/questions.json`
back into Phase 2's `QuestionItem` model (reused, not redefined) so there's
exactly one schema for "a detected question" across the whole project.

**`modules/category_classifier.py`** — `CategoryClassifier` scores a question
against every category's keyword list (`CATEGORY_KEYWORDS`, one dict, single
source of truth) and picks the highest-scoring category, or "Others" if
nothing matches. See the module's docstring for exactly what "never
hardcode categories" means in a rule-based (non-AI) context.

**`modules/answer_type_classifier.py`** — `AnswerTypeClassifier` uses an
*ordered* list of regex rules (first match wins) to detect Email, Phone,
Date, Certificate Number, Address, Checkbox, List, Multi-line Text, Number,
or Yes/No — falling back to "Text". Order matters: specific content signals
are checked before generic sentence-structure patterns, so e.g. "Do you
have a valid GST registration number?" is correctly detected as needing a
number, not a yes/no answer.

**`modules/source_predictor.py`** — `SourcePredictor` checks specific
keyword rules first (e.g. "GST" → "GST Certificate"), falling back to a
per-category default document (e.g. category "Bank Details" → document
"Bank Details") if no specific keyword matches.

**`modules/priority_classifier.py`** — `PriorityClassifier` marks a question
"High" if it explicitly says "mandatory"/"required"/"must", or if its
category is one that's almost always required for vendor approval (Company
Information, Certifications, Bank Details); "Low" for unclassified
("Others") questions; "Medium" otherwise.

**`modules/intent_extractor.py`** — `IntentExtractor` strips common
boilerplate lead-ins ("Please provide your...", "Kindly describe...",
"What is the...") to produce a concise phrase, e.g. "Please provide your
Manufacturing Plant Address." → "Manufacturing Plant Address". Falls back
to the original question (with only trailing punctuation removed) if no
known lead-in pattern matches.

**`modules/question_intelligence_engine.py`** — `QuestionIntelligenceEngine`
orchestrates the five classifiers above (each injected via the
constructor, defaulting to the real implementation — the same
dependency-injection pattern used by Phase 3's `DocumentManager`) and
assembles the final `QuestionObject`. Verified directly (with a classifier
that intentionally raises an exception) that one failing question is
logged and skipped without stopping the rest of the batch.

## What's implemented so far

**Phase 1 — Project structure**
- Typed, validated configuration loaded from `.env` (`config.py`)
- Centralized rotating-file + console logging (`modules/logger.py`)
- Full folder structure, auto-created if missing
- A startup health check (`app.py`) confirming everything above works

**Phase 2 — Document Reader Engine**
- Safe DOCX loading with clear errors for missing/invalid/corrupted files (`modules/docx_reader.py`)
- Full table/row/cell traversal with correct handling of merged cells
- Heuristic question/answer cell detection (`modules/question_detector.py`)
- Structured, validated output written to `temp/questions.json`
- Original document is never modified — Phase 2 only reads

**Phase 3 — Company Knowledge Extraction Engine**
- Automatic detection of supported files in `uploads/company_documents/` — no hardcoded filenames
- PDF (PyMuPDF), Word (python-docx, reusing Phase 2's table reader), and Excel (openpyxl) extraction
- Extensible `BaseDocumentProcessor` architecture — new formats (e.g. OCR) plug in without modifying existing code
- Per-file error tolerance — one corrupted document never stops the batch
- Whitespace/formatting cleanup with zero changes to actual content
- One JSON per document (`temp/documents/`) plus a lightweight manifest (`temp/knowledge_index.json`)

**Phase 4 — AI Question Intelligence Engine**
- Rule-based classification into category, expected answer type, likely source document, priority, and intent
- Five independent, dependency-injected classifiers, each in its own file
- Per-question error tolerance, verified with an injected failure
- Structured, validated output written to `temp/question_objects.json`
- No AI, no company-document reading — purely analyzes the question text itself

## What's NOT implemented yet

Calling Claude and writing answers back into questionnaire documents are
separate phases and will be added one at a time, each requiring approval
before moving to the next.

## Development plan

Note: phase numbers below track the order features were actually requested
in, which has diverged from the original 10-item outline in two ways:
(1) the original phases 3 ("Read XLSX") and 4 ("Extract PDF text") were
combined into a single Phase 3, "Company Knowledge Extraction Engine",
covering PDF + DOCX + XLSX together; (2) this Phase 4, "AI Question
Intelligence Engine", covers question classification (category, answer
type, source prediction, priority) — conceptually an expanded version of
what the original outline called "Question Detection" (originally
numbered Phase 6), delivered earlier and in more depth than first planned.

| Phase | Scope |
|---|---|
| 1 | Project structure *(done)* |
| 2 | Read DOCX questionnaire *(done)* |
| 3 | Company knowledge extraction: PDF + DOCX + XLSX *(done)* |
| 4 | AI Question Intelligence Engine: category, answer type, source, priority *(done)* |
| 5 | Claude API integration |
| 6 | Generate answers (using Phase 4's question objects + Phase 3's extracted knowledge) |
| 7 | Write answers back into the original questionnaire |
| 8 | Output generation |
| 9 | Testing |
