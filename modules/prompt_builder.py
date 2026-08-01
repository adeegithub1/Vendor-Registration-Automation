"""
Prompt Builder.

WHY PROMPTS LIVE IN prompts/, NOT IN PYTHON STRINGS
---------------------------------------------------------
Per this phase's explicit requirement, prompt wording must never be
hardcoded inside Python files. This module's only job is to load
prompts/system_prompt.txt and prompts/user_prompt.txt from disk and fill
in the user prompt's placeholders — it contains no prompt WORDING of its
own. Editing how the AI is instructed (tone, rules, examples) means
editing a .txt file; no Python code changes, and no redeployment of
application logic.

WHY TOKEN REPLACEMENT INSTEAD OF str.format()
---------------------------------------------------
The user prompt template is filled with real company document text,
which could plausibly (if rarely) contain literal "{" or "}" characters
(e.g. from a document mentioning JSON, code, or curly-brace notation).
Python's str.format() would raise a KeyError or produce garbled output
if the substituted text itself contains braces that look like format
fields. Using distinctive "{{TOKEN}}" markers and plain str.replace()
avoids this entirely — document text is inserted byte-for-byte, however
many braces it happens to contain.
"""

from pathlib import Path

from modules.models import QuestionObject


class PromptBuilder:
    """Loads prompt templates from prompts/ and fills in per-question values."""

    def __init__(self, prompts_dir: Path, max_document_chars: int = 12000):
        """
        Args:
            prompts_dir: Folder containing system_prompt.txt and user_prompt.txt.
            max_document_chars: Safety cap on how much document text is
                inserted into a single prompt (controls prompt size/cost).
        """
        self.system_instruction = self._load_prompt_file(prompts_dir / "system_prompt.txt")
        self._user_prompt_template = self._load_prompt_file(prompts_dir / "user_prompt.txt")
        self.max_document_chars = max_document_chars

    @staticmethod
    def _load_prompt_file(path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {path}. Prompts must exist under prompts/ — see README."
            )
        return path.read_text(encoding="utf-8").strip()

    def _truncate_document_text(self, document_text: str) -> str:
        if len(document_text) <= self.max_document_chars:
            return document_text
        return document_text[: self.max_document_chars] + "\n[... TRUNCATED ...]"

    def build_user_prompt(self, question_object: QuestionObject, document_text: str, source_document: str) -> str:
        """
        Fill the user prompt template for one question.

        Args:
            question_object: The question being answered.
            document_text: Extracted text of the matched company document.
            source_document: Filename of the matched company document
                (shown to the AI so it can echo it back in "source_document").

        Returns:
            The fully-filled user prompt string, ready to send to an AI provider.
        """
        truncated_text = self._truncate_document_text(document_text)

        prompt = self._user_prompt_template
        prompt = prompt.replace("{{QUESTION_ID}}", str(question_object.id))
        prompt = prompt.replace("{{QUESTION}}", question_object.original_question)
        prompt = prompt.replace("{{CATEGORY}}", question_object.category)
        prompt = prompt.replace("{{EXPECTED_ANSWER_TYPE}}", question_object.expected_answer_type)
        prompt = prompt.replace("{{SOURCE_DOCUMENT}}", source_document)
        prompt = prompt.replace("{{DOCUMENT_TEXT}}", truncated_text)
        return prompt
