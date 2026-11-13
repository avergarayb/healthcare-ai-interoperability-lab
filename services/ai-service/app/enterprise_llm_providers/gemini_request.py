"""Closed generateContent request for the one synthetic fixture."""
import json

from .errors import ProviderError
from .gemini_configuration import ALLOWED_MODEL, MAX_OUTPUT_TOKENS, TIMEOUT_MILLISECONDS
from .request import INSTRUCTIONS
from .schema import QUESTION_ID, RESPONSE_SCHEMA
from .smoke import FIXED_DOCUMENT


def build_generation(document_text, settings):
    if (type(document_text) is not str or document_text != FIXED_DOCUMENT
            or settings.model_id != ALLOWED_MODEL or settings.max_output_tokens != MAX_OUTPUT_TOKENS):
        raise ProviderError("invalid_input")
    generation = {
        "model": ALLOWED_MODEL,
        "system_instruction": INSTRUCTIONS,
        "contents": "question_id=" + QUESTION_ID + "\n<source>\n" + document_text + "\n</source>",
        "response_mime_type": "application/json",
        "response_json_schema": RESPONSE_SCHEMA,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "thinking_level": "MINIMAL",
        "automatic_function_calling": False,
        "timeout_milliseconds": TIMEOUT_MILLISECONDS,
        "attempts": 1,
    }
    require_closed_generation(generation, document_text)
    return generation


def require_closed_generation(generation, document_text):
    schema = generation.get("response_json_schema")
    if (type(generation) is not dict or generation.get("model") != ALLOWED_MODEL
            or generation.get("system_instruction") != INSTRUCTIONS
            or generation.get("response_mime_type") != "application/json"
            or schema != RESPONSE_SCHEMA or schema.get("additionalProperties") is not False
            or generation.get("max_output_tokens") != MAX_OUTPUT_TOKENS
            or generation.get("thinking_level") != "MINIMAL"
            or generation.get("automatic_function_calling") is not False
            or generation.get("timeout_milliseconds") != TIMEOUT_MILLISECONDS
            or generation.get("attempts") != 1
            or "tools" in generation or "cached_content" in generation or "base_url" in generation):
        raise ProviderError("invalid_input")
    content = generation.get("contents")
    if (type(content) is not str or content.count(document_text) != 1
            or document_text in generation["system_instruction"] or document_text != FIXED_DOCUMENT):
        raise ProviderError("invalid_input")
    if settings_marker(generation):
        raise ProviderError("invalid_input")


def request_bytes(generation):
    return len(json.dumps({
        "system_instruction": generation["system_instruction"],
        "contents": generation["contents"],
        "response_json_schema": generation["response_json_schema"],
    }, ensure_ascii=False).encode("utf-8"))


def settings_marker(generation):
    rendered = json.dumps(generation, ensure_ascii=True, default=str)
    return "AIza" in rendered or "GEMINI_API_KEY" in rendered
