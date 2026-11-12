"""Published gpt-6-luna text rates, in micro-USD per million tokens.

Standard input is $0.10, cache writes are $0.125, and output is $0.50.
A prompt above 272_000 input tokens is billed at twice the input rate and
1.5 times the output rate for the whole request. Cached-input discounts are
not assumed: the laboratory ceiling uses the cache-write rate.
"""
from .errors import ProviderError


STANDARD_INPUT = 100_000
CACHE_WRITE_INPUT = 125_000
STANDARD_OUTPUT = 500_000
LONG_CONTEXT_INPUT_TOKENS = 272_000


def estimate_microusd(input_tokens, output_tokens, *, ceiling=False):
    if (type(input_tokens) is not int or type(output_tokens) is not int
            or input_tokens < 0 or output_tokens < 0):
        raise ProviderError("not_configured")
    long_context = input_tokens > LONG_CONTEXT_INPUT_TOKENS
    input_rate = CACHE_WRITE_INPUT if ceiling else STANDARD_INPUT
    output_rate = STANDARD_OUTPUT
    if long_context:
        input_rate *= 2
        output_rate = output_rate * 3 // 2
    return (input_tokens * input_rate + output_tokens * output_rate + 999_999) // 1_000_000
