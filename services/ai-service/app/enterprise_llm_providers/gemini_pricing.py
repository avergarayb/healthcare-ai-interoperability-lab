"""Paid Standard rates for gemini-3.5-flash-lite, in micro-USD per million tokens.

The pricing page lists input at $0.30 and output, including thinking tokens, at $2.50.
Batch, Flex and Priority are different products and are not selected here.
"""
from .errors import ProviderError


STANDARD_INPUT = 300_000
STANDARD_OUTPUT = 2_500_000
CALL_CEILING_MICROUSD = 1_000


def estimate_microusd(input_tokens, output_tokens):
    if (type(input_tokens) is not int or type(output_tokens) is not int
            or input_tokens < 0 or output_tokens < 0):
        raise ProviderError("not_configured")
    return (input_tokens * STANDARD_INPUT + output_tokens * STANDARD_OUTPUT + 999_999) // 1_000_000
