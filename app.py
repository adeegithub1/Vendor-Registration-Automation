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
from modules.ai_providers import create_provider
from modules.ai_providers.base_provider import AIProviderError
from modules.ai_service import AIService
from modules.answer_generation_engine import AnswerGenerationEngine, save_answers
from modules.answer_loader import AnswerLoadError, load_answers
from modules.docx_reader import DocxReadError, load_document
from modules.document_manager import DocumentManager
from modules.knowledge_exporter import KnowledgeExporter
from modules.knowledge_matcher import KnowledgeMatcher
from modules.logger import get_logger
from modules.prompt_builder import PromptBuilder
from modules.question_detector import detect_questions, save_questions_json
from modules.question_intelligence_engine import QuestionIntelligenceEngine, save_question_objects
from modules.question_loader import QuestionLoadError, load_questions
from modules.question_object_loader import QuestionObjectLoadError, load_question_objects
from modules.word_writer import WordQuestionnaireFiller

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

    # 2. Confirm the ACTIVE AI provider's key was loaded (settings.ai_provider
    #    decides which key matters -- we never require every provider's key,
    #    only the one actually configured for use; see config.py's
    #    get_active_provider_api_key() docstring for why).
    active_key = settings.get_active_provider_api_key()
    placeholder_values = {"your-gemini-api-key-here", "your-claude-api-key-here", "your-openai-api-key-here"}
    if not active_key or active_key in placeholder_values:
        logger.error(
            f"No API key set for the active AI provider ('{settings.ai_provider}'). "
            "Copy .env.example to .env and add your real key (see AI_PROVIDER and the matching *_API_KEY)."
        )
        return False
    logger.info(f"API key loaded successfully for active AI provider: {settings.ai_provider}")

    logger.info(f"Configured AI provider: {settings.ai_provider}")
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


def run_answer_generation() -> None:
    """
    Phase 5 pipeline: load temp/question_objects.json, match each question
    to its most relevant company document, ask the configured AI provider
    for a grounded answer, and save the results to temp/generated_answers.json.
    """
    settings.ensure_directories_exist()

    try:
        question_objects = load_question_objects(settings.question_objects_json_path)
    except QuestionObjectLoadError as exc:
        logger.error(str(exc))
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    active_key = settings.get_active_provider_api_key()
    active_model = {
        "gemini": settings.gemini_model,
        "claude": settings.claude_model,
        "openai": settings.openai_model,
    }.get(settings.ai_provider, "")

    try:
        provider = create_provider(settings.ai_provider, api_key=active_key, model=active_model)
    except AIProviderError as exc:
        logger.error(str(exc))
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    try:
        prompt_builder = PromptBuilder(settings.prompts_dir, max_document_chars=settings.max_document_chars)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    ai_service = AIService(
        provider=provider,
        system_instruction=prompt_builder.system_instruction,
        max_retries=settings.ai_max_retries,
        retry_delay_seconds=settings.ai_retry_delay_seconds,
    )
    knowledge_matcher = KnowledgeMatcher(settings.knowledge_index_path, PROJECT_ROOT)

    engine = AnswerGenerationEngine(ai_service, knowledge_matcher, prompt_builder)
    answers = engine.generate_answers(question_objects)
    save_answers(answers, settings.generated_answers_json_path)

    found_count = sum(1 for a in answers if a.answer != "NOT FOUND")
    not_found_count = len(answers) - found_count

    print("\n" + "=" * 60)
    print("PHASE 5: AI KNOWLEDGE MATCHING & ANSWER GENERATION ENGINE")
    print("=" * 60)
    print(f"AI provider          : {settings.ai_provider}")
    print(f"Questions processed    : {len(answers)}")
    print(f"Answers found           : {found_count}")
    print(f"NOT FOUND                : {not_found_count}")
    print(f"Saved to                  : {settings.generated_answers_json_path}")
    print("=" * 60 + "\n")


def run_fill_questionnaire(original_questionnaire_path: Path) -> None:
    """
    Phase 6 pipeline: load the original questionnaire, temp/question_objects.json,
    and temp/generated_answers.json, fill every answer into the document
    (preserving all formatting), and save to output/Filled_Questionnaire.docx.
    """
    settings.ensure_directories_exist()

    try:
        question_objects = load_question_objects(settings.question_objects_json_path)
    except QuestionObjectLoadError as exc:
        logger.error(str(exc))
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    try:
        answers = load_answers(settings.generated_answers_json_path)
    except AnswerLoadError as exc:
        logger.error(str(exc))
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    filler = WordQuestionnaireFiller()

    try:
        results = filler.fill_and_save(
            original_questionnaire_path,
            question_objects,
            answers,
            settings.filled_questionnaire_path,
        )
    except DocxReadError as exc:
        logger.error(str(exc))
        print(f"\nERROR: {exc}\n")
        sys.exit(1)

    success_count = sum(1 for r in results if r.status == "success")
    failed_count = len(results) - success_count

    print("\n" + "=" * 60)
    print("PHASE 6: WORD QUESTIONNAIRE FILL ENGINE")
    print("=" * 60)
    print(f"Original questionnaire  : {original_questionnaire_path}")
    print(f"Questions processed      : {len(results)}")
    print(f"Answers written           : {success_count}")
    print(f"Failed                     : {failed_count}")
    print(f"Saved to                    : {settings.filled_questionnaire_path}")
    if failed_count:
        print("\nFailed questions:")
        for r in results:
            if r.status == "failed":
                print(f"  - id={r.question_id}: {r.question_text[:60]} | {r.error_message}")
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
    parser.add_argument(
        "--generate-answers",
        action="store_true",
        help="Run Phase 5: generate AI answers from temp/question_objects.json using the configured AI provider.",
    )
    parser.add_argument(
        "--fill-questionnaire",
        type=Path,
        metavar="PATH",
        help="Run Phase 6: fill the ORIGINAL questionnaire DOCX with generated answers, preserving formatting.",
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

    if args.generate_answers:
        run_answer_generation()
        return

    if args.fill_questionnaire is not None:
        run_fill_questionnaire(args.fill_questionnaire)
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
        print(f"Active AI provider        : {settings.ai_provider}")
    else:
        print("Status: SETUP INCOMPLETE - see error above")
        sys.exit(1)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
