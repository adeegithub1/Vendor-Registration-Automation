# Vendor Questionnaire AI

An AI application that automatically fills vendor questionnaires (DOCX/XLSX)
using a company's own documents (profile, certificates, catalogues, etc.),
without ever recreating or reformatting the original file.

**Current status: Phase 6 — Word Questionnaire Fill Engine** (writes AI
answers back into the original DOCX, preserving all formatting).

> **Architecture note (Phase 5):** the original plan used the Anthropic Claude
> API exclusively. Phase 5 was scoped by request as a **provider-agnostic AI
> Service Layer** instead — Gemini is Version 1's actual working backend;
> Claude and OpenAI are registered but intentionally unimplemented stubs (see
> `modules/ai_providers/`). This also required relaxing `config.py`'s
> previously-mandatory `ANTHROPIC_API_KEY` to optional, since the app should
> no longer refuse to start over a key it doesn't currently use — see
> "Setup" below for what `.env` now needs.

## Folder structure

```
Vendor-AI/
├── app.py                  # Entry point (setup check + --read-docx + --extract-knowledge + --classify-questions + --generate-answers + --fill-questionnaire)
├── config.py                # Centralized, typed configuration (reads .env)
├── requirements.txt
├── .env.example              # Template for your local .env (copy this)
├── .gitignore
├── uploads/
│   ├── company_documents/    # Put a company's source documents here
│   └── questionnaire/        # Put the vendor questionnaire to fill here
├── output/
│   └── Filled_Questionnaire.docx   # Phase 6 output: the completed questionnaire
├── logs/                     # Rotating application log files
├── temp/
│   ├── questions.json          # Phase 2 output: detected questionnaire questions
│   ├── question_objects.json    # Phase 4 output: questions enriched with category/type/source/priority
│   ├── generated_answers.json    # Phase 5 output: AI-generated answers
│   ├── knowledge_index.json     # Phase 3 output: manifest of extracted company documents
│   └── documents/                # Phase 3 output: one JSON per extracted company document
├── prompts/
│   ├── system_prompt.txt         # Phase 5: AI behavior rules (JSON-only, never hallucinate, etc.)
│   └── user_prompt.txt            # Phase 5: per-question prompt template with {{PLACEHOLDER}} tokens
├── tests/
│   ├── __init__.py
│   └── test_word_writer.py         # Phase 6: unit tests (run: python -m unittest tests.test_word_writer -v)
├── modules/
│   ├── __init__.py
│   ├── logger.py                 # Centralized logging setup
│   ├── docx_reader.py              # Phase 2: opens DOCX, traverses tables/rows/cells safely
│   ├── question_detector.py         # Phase 2: heuristic question/answer cell detection
│   ├── models.py                     # Shared Pydantic models (ProcessedDocument, QuestionObject, AnswerObject, FillResult, etc.)
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
│   ├── question_intelligence_engine.py        # Phase 4: orchestrates all 5 classifiers, error-tolerant
│   ├── question_object_loader.py               # Phase 5: loads + validates temp/question_objects.json
│   ├── prompt_builder.py                         # Phase 5: loads prompts/, fills {{PLACEHOLDER}} tokens
│   ├── knowledge_matcher.py                       # Phase 5: finds + loads the ONE best-matching company document
│   ├── ai_service.py                               # Phase 5: retry logic + JSON parsing (the only AI entry point)
│   ├── answer_generation_engine.py                  # Phase 5: orchestrates matching, prompting, AI calls
│   ├── answer_loader.py                              # Phase 6: loads + validates temp/generated_answers.json
│   ├── word_writer.py                                 # Phase 6: fills answers into the original DOCX, preserving formatting
│   └── ai_providers/
│       ├── __init__.py                               # PROVIDER_REGISTRY + create_provider() factory
│       ├── base_provider.py                           # Abstract BaseAIProvider interface
│       ├── gemini_provider.py                          # Working implementation (google-genai SDK)
│       ├── claude_provider.py                          # Stub — raises NotImplementedError
│       └── openai_provider.py                          # Stub — raises NotImplementedError
└── (see prompts/ above)
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

3. Copy the environment template and add your real API key:
   ```
   cp .env.example .env
   ```
   Then open `.env` and set `GEMINI_API_KEY` to your real Gemini API key
   from https://aistudio.google.com/apikey (Version 1 uses Gemini by
   default — see `AI_PROVIDER` in `.env`). The `ANTHROPIC_API_KEY` and
   `OPENAI_API_KEY` entries are reserved for when `ClaudeProvider`/
   `OpenAIProvider` are implemented in a future phase — you don't need to
   fill them in to use Version 1.

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

## Usage: Phase 5 — generating answers

After running Phases 3 and 4 (so `knowledge_index.json` and
`question_objects.json` both exist), run:

```
python app.py --generate-answers
```

This will, for every question:
1. Find the single best-matching company document via `KnowledgeMatcher`
   (never sends every document — only the one predicted-relevant one, or
   none at all if nothing matches, in which case the AI is never called).
2. Build a prompt from `prompts/system_prompt.txt` + `prompts/user_prompt.txt`.
3. Ask the configured AI provider (Gemini by default) for a JSON-only answer.
4. Retry up to `AI_MAX_RETRIES` times (default 3) on failure; if every
   attempt fails, record `"answer": "NOT FOUND", "confidence": 0` for that
   question and move on — one question's failure never stops the batch.
5. Save every answer (found or not) to `temp/generated_answers.json`.

**Switching AI providers:** set `AI_PROVIDER=gemini` / `claude` / `openai` in
`.env`. Only `gemini` has a working implementation right now — selecting
`claude` or `openai` will raise a clear `NotImplementedError` the moment an
answer is actually requested (not at startup), since those providers are
intentionally empty stubs in Version 1 (see the architecture note near the
top of this file).

**What was actually verified, and how** (this phase involves live network
calls to Gemini's API, which this development environment cannot reach):
- The **real failure/retry path** was tested against the actual (blocked)
  Gemini endpoint: confirmed the correct number of retry attempts, the
  correct backoff delay, correct error wrapping, and — critically — that
  the whole 16-question batch still completed and wrote a `NOT FOUND` entry
  for every question rather than crashing.
- The **success path** (matching → prompt building → JSON parsing →
  correct answer) was verified using a fake provider standing in for
  Gemini's `generate()` call — this is the same dependency-injection point
  a real Gemini call goes through, so everything except the actual network
  round-trip is proven correct.
- Two real bugs were found and fixed this way: (1) the "API Calls" log
  count wasn't including failed attempts, only successful ones; (2) the
  stored `question_id` was trusting the AI's echoed value instead of the
  question we already knew we asked about — a model returning a wrong ID
  could have silently corrupted which question an answer was attributed to.
  Both are fixed and covered by the tests described above.
- **Not tested here, by necessity:** an actual authenticated call to
  Gemini's API succeeding end-to-end. The code is written against Google's
  current documented SDK usage, but you should run one real
  `--generate-answers` call against your own Gemini key before relying on
  this in production.

### Module-by-module explanation: Phase 5

**`modules/ai_providers/base_provider.py`** — `BaseAIProvider`, the abstract
interface (`generate(system_instruction, user_prompt) -> str`) every
provider implements. Nothing outside `modules/ai_providers/` and
`modules/ai_service.py` ever imports a concrete provider directly.

**`modules/ai_providers/gemini_provider.py`** — `GeminiProvider`, the only
working implementation in Version 1. Uses Google's current `google-genai`
SDK, sets `response_mime_type="application/json"` (an API-level constraint,
not just a prompt request) and `temperature=0` for literal, deterministic
extraction rather than creative generation.

**`modules/ai_providers/claude_provider.py`** / **`openai_provider.py`** —
Genuine stubs: implement the interface, but `generate()` raises
`NotImplementedError` with instructions for what implementing them for
real would involve. Not partial/fake implementations.

**`modules/ai_providers/__init__.py`** — `PROVIDER_REGISTRY` (provider name
→ class) and `create_provider()`, a factory that builds a configured
provider from settings. Adding a future local LLM provider is a two-line
addition here — no other file changes.

**`modules/ai_service.py`** — `AIService`, the *only* place in the
application that calls a provider, parses its JSON response (defensively
stripping markdown fences in case a model doesn't perfectly honor the
no-markdown instruction), and owns retry logic. `AIServiceError` carries an
`attempts` count so callers can accurately log how many API calls were
actually made, even on total failure.

**`modules/prompt_builder.py`** — `PromptBuilder` loads
`prompts/system_prompt.txt` and `prompts/user_prompt.txt` from disk and
fills `{{TOKEN}}` placeholders via plain string replacement (not
`str.format()`, which could break if document text happens to contain `{`
or `}` characters). Also enforces `max_document_chars` as a safety cap on
prompt size.

**`modules/knowledge_matcher.py`** — `KnowledgeMatcher` finds the single
best-matching company document for a question's predicted document name,
via the same keyword-token-overlap technique used elsewhere in this
project, and caches loaded document text in memory (many questions
typically share the same matched document).

**`modules/answer_generation_engine.py`** — `AnswerGenerationEngine`
orchestrates matching → prompting → AI call → validated `AnswerObject` for
every question, tolerating per-question failures (logs and records `NOT
FOUND` rather than aborting the batch) and logging the summary stats this
phase requires (questions processed, API calls, processing time, failed
questions, average response time).



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

## Usage: Phase 6 — filling the questionnaire

After running Phases 2, 4, and 5 (so `question_objects.json` and
`generated_answers.json` both exist for this questionnaire), run:

```
python app.py --fill-questionnaire path/to/original_questionnaire.docx
```

**Important: pass the same original file used in Phase 2.** The saved
`Location` (table/row/cell) for each question only lines up correctly
against the exact document it was detected from.

This will:
1. Load the original questionnaire (never modifying that file — a new
   file is written, the original is only read).
2. For every question, go directly to its recorded table/row/cell and
   write the answer, mutating only that cell's existing text run so all
   other formatting is untouched.
3. If a question's answer is missing or blank, write `NOT FOUND`.
4. If a question's location can't be resolved, log a warning and
   continue — one question's failure never stops the batch.
5. Save the result to `output/Filled_Questionnaire.docx`.

**Verification performed on this phase, including a real bug that was
found and fixed:** while testing multiline answers, `cell.text` showed the
right words, but inspecting the *raw saved XML* revealed the `<w:br/>` line
break elements were silently missing — `python-docx`'s `Run.text` setter
rebuilds a run's children from scratch, which was quietly deleting a break
added moments earlier. Fixed by using `run.add_text()` (which appends)
instead of `run.text = ...` (which replaces) after a break. This is called
out because `cell.text`/`paragraph.text` never render breaks as `\n` either
way, so a superficial test would not have caught it — the fix was only
confirmed by inspecting the document's actual XML, and the corresponding
test (`TestLongAnswer`) now asserts on the XML directly rather than on text
alone. Also verified end-to-end: original source file's checksum is
unchanged after running (it's only ever read), and every question cell in
the output matches the original character-for-character.

**Run the unit tests directly:**
```
python -m unittest tests.test_word_writer -v
```

### Module-by-module explanation: Phase 6

**`modules/word_writer.py`** — `WordQuestionnaireFiller` orchestrates two
injectable `AnswerInsertionStrategy` implementations, tried in order:
`TableCellInsertionStrategy` (primary — goes directly to the question's
recorded table/row/cell, reusing Phase 2's merge-safe `get_row_grid_cells`
so coordinates line up exactly) and `ParagraphColonInsertionStrategy`
(fallback — colon-based and blank-line-below paragraph styles, matched by
question text). Formatting is preserved by mutating existing `Run.text`
rather than recreating paragraphs; multiline answers use soft line breaks
within the same paragraph rather than new paragraphs, keeping cell/row
layout unchanged.

**`modules/answer_loader.py`** — Loads and validates
`temp/generated_answers.json` into `AnswerObject`, mirroring
`question_loader.py` and `question_object_loader.py`'s established pattern.

**Scope boundary, stated plainly:** Phase 2's detector (which this phase
was explicitly told not to modify) only ever produces table-based
`Location`s today — it doesn't detect colon-based, blank-line, or other
paragraph-style questions in the first place. So in the current end-to-end
CLI pipeline, every question resolves via `TableCellInsertionStrategy`.
`ParagraphColonInsertionStrategy` is fully implemented and independently
unit-tested (both directly and via `WordQuestionnaireFiller`'s automatic
fallback when a table location doesn't resolve), ready for when non-table
question detection exists, but it isn't reachable through today's
`--read-docx` → `--fill-questionnaire` flow on its own.



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

**Phase 5 — AI Knowledge Matching & Answer Generation Engine**
- Provider-agnostic AI Service Layer (`Application → AIService → BaseAIProvider → Gemini/Claude/OpenAI`)
- Gemini implemented for real (Google's `google-genai` SDK); Claude/OpenAI genuine stubs
- Sends only the single best-matching company document per question — never the whole knowledge base
- Retry logic (configurable attempts/delay) verified against a real (blocked) network failure
- Prompts live in `prompts/*.txt`, never hardcoded in Python
- Per-question error tolerance — every question gets an answer entry, `NOT FOUND` on failure
- Structured, validated output written to `temp/generated_answers.json`

**Phase 6 — Word Questionnaire Fill Engine**
- Writes answers directly into the original questionnaire DOCX, preserving all formatting
- Two-strategy insertion (table-cell primary, paragraph/colon/blank-line fallback), reusing Phase 2's merge-safe table reader
- Duplicate/identical-looking questions filled correctly via recorded per-question coordinates, not text search
- Multiline answers via real soft line breaks, verified at the XML level (not just visible text)
- Per-question error tolerance — one unresolvable question never stops the batch
- 12 unit tests covering every required scenario (table, paragraph, mixed, empty/missing answer, duplicates, long answer, corrupted document)
- Original questionnaire file is never modified — only read

## What's NOT implemented yet

Final output generation (e.g. XLSX questionnaire support, batch processing
across multiple questionnaires) and broader end-to-end testing are the
remaining phases. Also not yet done: an actual successful live call to
Gemini's API (see the Phase 5 usage section above for exactly what was and
wasn't verified here), and paragraph-style question DETECTION (Phase 2 —
the fallback WRITING strategy for such questions is implemented and
tested, but nothing currently produces that kind of QuestionObject).

## Development plan

Note: phase numbers below track the order features were actually requested
in, which has diverged from the original 10-item outline in three ways:
(1) the original phases 3 ("Read XLSX") and 4 ("Extract PDF text") were
combined into a single Phase 3, "Company Knowledge Extraction Engine",
covering PDF + DOCX + XLSX together; (2) Phase 4, "AI Question Intelligence
Engine", covers question classification — an expanded version of what the
original outline called "Question Detection" (originally numbered Phase
6), delivered earlier and in more depth than first planned; (3) Phase 5
was scoped as a provider-agnostic AI Service Layer rather than
Claude-specific integration — see the architecture note near the top of
this file.

| Phase | Scope |
|---|---|
| 1 | Project structure *(done)* |
| 2 | Read DOCX questionnaire *(done)* |
| 3 | Company knowledge extraction: PDF + DOCX + XLSX *(done)* |
| 4 | AI Question Intelligence Engine: category, answer type, source, priority *(done)* |
| 5 | Provider-agnostic AI Service Layer + answer generation (Gemini implemented) *(done)* |
| 6 | Word Questionnaire Fill Engine: write answers back, preserving formatting *(done)* |
| 7 | Output generation (broader format support / batch processing) |
| 8 | Testing |
