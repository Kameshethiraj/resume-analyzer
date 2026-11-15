
import re
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


# --------------------------------------------------
# PII REDACTION
# --------------------------------------------------

PATTERNS = [
    # Email addresses
    (
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        ),
        "[EMAIL_REDACTED]",
    ),

    # Indian phone numbers: optional +91, spaces or hyphens
    (
        re.compile(
            r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"
        ),
        "[PHONE_REDACTED]",
    ),

    # Indian PAN
    (
        re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
        "[PAN_REDACTED]",
    ),

    # Aadhaar-like 12-digit number.
    # This pattern does not validate whether it is a real Aadhaar number.
    (
        re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)"),
        "[ID_NUMBER_REDACTED]",
    ),

    # URLs: may contain personal information in paths or query parameters
    (
        re.compile(r"\bhttps?://[^\s<>]+", re.IGNORECASE),
        "[URL_REDACTED]",
    ),
]


def redact_pii(text: str) -> str:
    """
    Redact common PII from text.

    Note:
        Regex-based detection is approximate. It cannot reliably detect
        every person's name, address, or sensitive identifier.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)

    return text


# --------------------------------------------------
# SAFE LOGGING
# --------------------------------------------------

def setup_safe_logger(
    name: str = "resume_analyzer",
    log_dir: str = "logs",
) -> logging.Logger:
    """
    Create a rotating file logger.

    Log only redacted text. Avoid logging raw resumes, credentials,
    tokens, or unredacted model prompts and responses.
    """
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Avoid adding duplicate handlers if setup is called more than once.
    if not logger.handlers:
        handler = RotatingFileHandler(
            directory / "application.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )

        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            )
        )

        logger.addHandler(handler)

    return logger


def log_safe_text(
    logger: logging.Logger,
    event: str,
    text: str,
) -> None:
    """Redact text before writing it to the application log."""
    safe_text = redact_pii(text)
    safe_event = redact_pii(event)

    logger.info("%s | %s", safe_event, safe_text)
