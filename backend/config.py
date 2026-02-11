from pathlib import Path
import os


class Settings:
    """
    Global application configuration
    """

    # Project root
    BASE_DIR = Path(__file__).resolve().parent.parent

    # Data root
    DATA_ROOT = BASE_DIR / "data" / "projects"

    # Allowed report types
    ALLOWED_REPORT_TYPES = {
        "custom-report",
        "project-report",
        "document-report"
    }

    # Excel settings
    EXCEL_EXTENSIONS = {".xlsx", ".xls"}
    EXCEL_ENGINE = "openpyxl"

    # Safety limits
    MAX_ROWS_PREVIEW = 5000
    MAX_COLUMNS = 200

    # Environment
    ENV = os.getenv("ENV", "development")
    DEBUG = ENV != "production"


settings = Settings()
