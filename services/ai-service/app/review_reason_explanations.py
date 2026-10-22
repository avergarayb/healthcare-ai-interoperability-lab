"""Server-owned explanations for supported operational review reasons.

The Human Review page and the AI model projection share this mapping.
Do not keep a second copy of these sentences.
"""

REASON_EXPLANATIONS = {
    "post_consultation_result_requires_review": (
        "A post-consultation result was selected for operational review."
    ),
    "missed_follow_up_without_confirmed_replacement": (
        "Follow-up appointment was not completed. "
        "No confirmed future follow-up was recorded at the time the case was created."
    ),
}
