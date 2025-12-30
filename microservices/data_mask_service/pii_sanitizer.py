"""
PII Redaction Utility
Uses Microsoft Presidio to mask sensitive data.
"""
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Initialize engines once (they are heavy to load)
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def redact_pii(text: str) -> str:
    if not text:
        return ""

    # 1. Analyze: Find the PII entities
    results = analyzer.analyze(
        text=text,
        entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", "DATE_TIME"],
        language='en'
    )

    # 2. Anonymize: Replace them with placeholders
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={
            "PERSON": OperatorConfig("replace", {"new_value": "<PERSON>"}),
            "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE>"}),
            "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
            "CREDIT_CARD": OperatorConfig("replace", {"new_value": "<CARD>"}),
        }
    )

    return anonymized_result.text