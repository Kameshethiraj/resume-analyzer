
from app.pii_handler import (
    redact_pii,
    setup_safe_logger,
    log_safe_text,
)


def test_email_redaction():
    result = redact_pii("Email: arun@example.com")
    assert "arun@example.com" not in result
    assert "[EMAIL_REDACTED]" in result


def test_phone_redaction():
    result = redact_pii("Phone: +91 9876543210")
    assert "9876543210" not in result
    assert "[PHONE_REDACTED]" in result


def test_pan_redaction():
    result = redact_pii("PAN: ABCDE1234F")
    assert "ABCDE1234F" not in result
    assert "[PAN_REDACTED]" in result


def test_id_number_redaction():
    result = redact_pii("ID: 1234 5678 9012")
    assert "1234 5678 9012" not in result
    assert "[ID_NUMBER_REDACTED]" in result


def test_url_redaction():
    result = redact_pii(
        "Portfolio: https://example.com/profile?id=123"
    )
    assert "https://example.com/profile?id=123" not in result
    assert "[URL_REDACTED]" in result


def test_non_string_input():
    try:
        redact_pii(12345)
    except TypeError:
        pass
    else:
        raise AssertionError("Expected TypeError")


def demonstrate_safe_logging():
    logger = setup_safe_logger()

    candidate_answer = (
        "My email is arun@example.com and "
        "my phone is +91 9876543210."
    )

    log_safe_text(
        logger,
        event="interview_answer_received",
        text=candidate_answer,
    )

    print("Safe logging demonstration complete.")
    print("Check logs/application.log")


if __name__ == "__main__":
    demonstrate_safe_logging()
    print("Run tests using: python -m pytest Experiments/test_pii_handler.py")
