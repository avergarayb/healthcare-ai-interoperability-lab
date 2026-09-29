"""System-behavior evaluation for the productive follow-up workflow.

This package calls FollowUpWorkflow. The workflow does not import it.
"""

from evaluation.cases import SYSTEM_SCENARIOS
from evaluation.report import format_report
from evaluation.runner import run_suite

__all__ = ["SYSTEM_SCENARIOS", "format_report", "run_suite"]
