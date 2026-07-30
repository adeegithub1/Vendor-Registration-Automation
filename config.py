"""
Central configuration for Vendor Questionnaire AI.

WHY THIS EXISTS
----------------
The instructions for this project explicitly forbid hardcoded values.
Instead of every module defining its own paths or reading os.environ
directly, there is exactly ONE place (this file) that:

  1. Loads secrets/settings from a ".env" file (never from source code).
  2. Defines every folder path the application uses, as pathlib.Path
     objects, resolved relative to the project root — so the software
     works no matter which directory it's launched from.
  3. Validates that required settings (like the Claude API key) are
     actually present, and fails fast with a clear error if not,
     rather than crashing confusingly deep inside some other module.

Every other module does:
    from config import settings
    settings.company_documents_dir   # etc.

LIBRARIES USED HERE
--------------------
- pydantic-settings: A library that defines configuration as a typed
  class (like a form with validation). It automatically reads matching
  environment variables (and a .env file) and raises a clear error if
  a required field is missing or the wrong type. This is safer than
  plain os.environ.get() calls scattered across the codebase, because
  typos in variable names or missing values are caught immediately at
  startup instead of causing confusing bugs later.
- python-dotenv (used internally by pydantic-settings): Reads key=value
  pairs from a ".env" file and makes them available as environment
  variables.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The root of the project (the folder this file lives in).
# Using .resolve() turns this into an absolute path, so it works
# correctly regardless of the current working directory the app
# is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """
    Typed application settings, populated from environment variables
    and/or a ".env" file in the project root.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unrelated env vars instead of erroring
    )

    # --- Claude API ---
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Optional until Phase 5. Required only when AI answer generation is used.",
    )
    claude_model: str = Field(
        default="claude-sonnet-4-6",
        description="Which Claude model to use for answering questionnaire questions.",
    )

    # --- Logging ---
    log_level: str = Field(
        default="INFO",
        description="Logging verbosity: DEBUG, INFO, WARNING, or ERROR.",
    )

    # --- Folder paths (all relative to PROJECT_ROOT, all pathlib.Path) ---
    uploads_dir: Path = PROJECT_ROOT / "uploads"
    company_documents_dir: Path = PROJECT_ROOT / "uploads" / "company_documents"
    questionnaire_dir: Path = PROJECT_ROOT / "uploads" / "questionnaire"
    output_dir: Path = PROJECT_ROOT / "output"
    logs_dir: Path = PROJECT_ROOT / "logs"
    prompts_dir: Path = PROJECT_ROOT / "prompts"
    temp_dir: Path = PROJECT_ROOT / "temp"
    documents_temp_dir: Path = PROJECT_ROOT / "temp" / "documents"
    knowledge_index_path: Path = PROJECT_ROOT / "temp" / "knowledge_index.json"
    questions_json_path: Path = PROJECT_ROOT / "temp" / "questions.json"
    question_objects_json_path: Path = PROJECT_ROOT / "temp" / "question_objects.json"

    def ensure_directories_exist(self) -> None:
        """
        Create every required folder if it doesn't already exist.
        Called once at application startup so the rest of the code
        can safely assume these folders are present.
        """
        for directory in (
            self.uploads_dir,
            self.company_documents_dir,
            self.questionnaire_dir,
            self.output_dir,
            self.logs_dir,
            self.prompts_dir,
            self.temp_dir,
            self.documents_temp_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


# A single shared instance, imported by every other module in the project.
# Creating it here (rather than each module making its own) guarantees
# every part of the app sees identical, already-validated settings.
settings = Settings()
