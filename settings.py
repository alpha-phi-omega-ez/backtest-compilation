from os import getenv

from dotenv import load_dotenv


def get_settings() -> dict:
    load_dotenv()
    return {
        "FOLDER_ID": getenv("FOLDER_ID"),
        "DELEGATE_EMAIL": getenv("DELEGATE_EMAIL"),
        "SHEET_URL": getenv("SHEET_URL"),
        "MONGO_URI": getenv("MONGO_URI", "mongodb://localhost:27017"),
        "LOG_LEVEL": getenv("LOG_LEVEL", "INFO"),
        "SENTRY_DSN": getenv("SENTRY_DSN", ""),
        "SENTRY_TRACE_RATE": getenv("SENTRY_TRACE_RATE", 1.0),
    }
