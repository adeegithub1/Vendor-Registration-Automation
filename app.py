"""
Vendor Questionnaire AI - entry point.

PHASE 1 SCOPE
--------------
There is no UI yet (Streamlit comes in a later phase). What this file
DOES do, right now, is real and working: it proves the foundation of
the project is correctly wired together before we build anything on
top of it. Specifically, running this file will:

  1. Load configuration from .env (via config.py) and confirm the
     Claude API key was found.
  2. Create the full folder structure if any folder is missing.
  3. Initialize logging and write a test log line to both the console
     and the rotating log file.
  4. Print a clear summary so you can visually confirm Phase 1 works.

Run it with:
    python app.py
"""

import argparse
import sys
from pathlib import Path

from config import PROJECT_ROOT, settings
from modules.docx_reader import DocxReadError, load_document
from modules.document_manager import DocumentManager
from modules.knowledge_exporter import KnowledgeExporter
from modules.logger import get_logger
from modules.question_detector import detect_questions, save_questions_json
from modules.question_intelligence_engine import QuestionIntelligenceEngine, save_question_objects
from modules.question_loader import QuestionLoadError, load_questions

logger = get_logger(__name__)


def verify_setup() -> bool:
    """
    Run all Phase 1 startup checks. Returns True if everything is fine,
    False if something needs fixing (e.g. missing API key).
    """
    logger.info("Starting Vendor Questionnaire AI - Phase 1 setup check")

    # 1. Confirm folder structure exists (creates any missing folders).
    settings.ensure_directories_exist()
    logger.info("Folder structure verified/created successfully.")

    required_dirs = [
        settings.company_documents_dir,
        settings.questionnaire_dir,
        settings.output_dir,
        settings.logs_dir,
        settings.prompts_dir,
    ]
    for directory in required_dirs:
        if not directory.is_dir():
            logger.error(f"Required directory is missing: {directory}")
            return False

    # 2. Confirm the Claude API key was loaded (we never log the key itself).
    if not settings.anthropic_api_key or settings.anthropic_api_key == "your-claude-api-key-here":
        logger.error(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your real key."
        )
        return False
    logger.info("Claude API key loaded successfully.")

    logger.info(f"Configured Claude model: {settings.claude_model}")
    logger.info("Phase 1 setup check completed successfully.")
    return True


def run_docx_question_detection(docx_path: Path) -> None:
    """
    Phase 2 pipeline: load a DOCX questionnaire, detect its questions,
    and save them to temp/questions.json.

    Args:
        docx_path: Path to the vendor questionnaire .docx file.
    """
    settings.ensure_directories_exist()

    try:
        document = load_document(docx_path)
    except DocxReadError as exc:
        logger.error(f"Could not read questionnaire: {exc}")
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    questions = detect_questions(document)
    output_path = settings.questions_json_path
    save_questions_json(questions, output_path)

    print("\n" + "=" * 60)
    print("PHASE 2: DOCUMENT READER ENGINE")
    print("=" * 60)
    print(f"Source file        : {docx_path}")
    print(f"Questions detected  : {len(questions)}")
    print(f"Saved to            : {output_path}")
    print("=" * 60 + "\n")


def run_knowledge_extraction() -> None:
    """
    Phase 3 pipeline: scan uploads/company_documents/, extract every
    supported document's content, and save the results to
    temp/documents/*.json plus temp/knowledge_index.json.
    """
    settings.ensure_directories_exist()

    manager = DocumentManager(settings.company_documents_dir)

    try:
        documents = manager.process_documents()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    exporter = KnowledgeExporter(
        documents_dir=settings.documents_temp_dir,
        index_path=settings.knowledge_index_path,
        project_root=PROJECT_ROOT,
    )
    exporter.export_all(documents)

    processed = [d for d in documents if d.status == "success"]
    failed = [d for d in documents if d.status == "failed"]
    total_characters = sum(d.total_characters for d in processed)

    print("\n" + "=" * 60)
    print("PHASE 3: COMPANY KNOWLEDGE EXTRACTION ENGINE")
    print("=" * 60)
    print(f"Source folder        : {settings.company_documents_dir}")
    print(f"Documents found       : {len(documents)}")
    print(f"Processed successfully : {len(processed)}")
    print(f"Failed                : {len(failed)}")
    print(f"Total characters       : {total_characters}")
    print(f"Document JSON folder   : {settings.documents_temp_dir}")
    print(f"Knowledge index        : {settings.knowledge_index_path}")
    if failed:
        print("\nFailed documents:")
        for doc in failed:
            print(f"  - {doc.filename}: {doc.error_message}")
    print("=" * 60 + "\n")


def run_question_classification() -> None:
    """
    Phase 4 pipeline: load temp/questions.json, classify every question
    (category, answer type, likely source document, priority, intent),
    and save the results to temp/question_objects.json.
    """
    settings.ensure_directories_exist()

    try:
        question_items = load_questions(settings.questions_json_path)
    except QuestionLoadError as exc:
        logger.error(str(exc))
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    engine = QuestionIntelligenceEngine()
    question_objects = engine.process_questions(question_items)
    save_question_objects(question_objects, settings.question_objects_json_path)

    categories_found = sorted({q.category for q in question_objects})
    others_count = sum(1 for q in question_objects if q.category == "Others")
    failed_count = len(question_items) - len(question_objects)

    print("\n" + "=" * 60)
    print("PHASE 4: AI QUESTION INTELLIGENCE ENGINE")
    print("=" * 60)
    print(f"Questions loaded      : {len(question_items)}")
    print(f"Questions classified   : {len(question_objects)}")
    print(f"Categories found        : {', '.join(categories_found) if categories_found else '(none)'}")
    print(f"Unknown (Others)         : {others_count}")
    print(f"Failed                    : {failed_count}")
    print(f"Saved to                  : {settings.question_objects_json_path}")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Vendor Questionnaire AI")
    parser.add_argument(
        "--read-docx",
        type=Path,
        metavar="PATH",
        help="Run Phase 2: read a DOCX questionnaire and detect its questions.",
    )
    parser.add_argument(
        "--extract-knowledge",
        action="store_true",
        help="Run Phase 3: extract knowledge from uploads/company_documents/.",
    )
    parser.add_argument(
        "--classify-questions",
        action="store_true",
        help="Run Phase 4: classify questions from temp/questions.json into structured question objects.",
    )
    args = parser.parse_args()

    if args.read_docx is not None:
        run_docx_question_detection(args.read_docx)
        return

    if args.extract_knowledge:
        run_knowledge_extraction()
        return

    if args.classify_questions:
        run_question_classification()
        return

    success = verify_setup()

    print("\n" + "=" * 60)
    print("VENDOR QUESTIONNAIRE AI - PHASE 1: PROJECT STRUCTURE")
    print("=" * 60)
    if success:
        print("Status: ALL CHECKS PASSED")
        print(f"Company documents folder : {settings.company_documents_dir}")
        print(f"Questionnaire folder     : {settings.questionnaire_dir}")
        print(f"Output folder            : {settings.output_dir}")
        print(f"Logs folder              : {settings.logs_dir}")
        print(f"Log file                 : {settings.logs_dir / 'vendor_ai.log'}")
        print(f"Claude model configured  : {settings.claude_model}")
    else:
        print("Status: SETUP INCOMPLETE - see error above")
        sys.exit(1)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
