"""
Test functions for AI Enrichment passes (Pass 1, Pass 2, Pass 3).
This module now serves as a compatibility layer, importing from specialized modules.

For new code, prefer importing directly from the specialized modules:
- test_pass1: Pass 1 extraction tests
- test_pass2: Pass 2 inference tests
- test_pass3: Pass 3 analysis tests
- test_multiple_models: Multi-model comparison framework
- test_execution_helpers: Execution and display helpers
"""

# Import and re-export all public functions for backward compatibility
from test_pass1 import test_multiple_jobs_comparison
from test_pass2 import test_pass2_inference
from test_pass3 import test_pass3_analysis
from test_multiple_models import test_multiple_models
from test_execution_helpers import (
    AVAILABLE_MODELS,
    execute_pass2,
    execute_pass3,
    display_pass2_results,
    display_pass3_results,
)

# Re-export with internal names for backward compatibility
_execute_pass2 = execute_pass2
_execute_pass3 = execute_pass3
_display_pass2_results = display_pass2_results
_display_pass3_results = display_pass3_results

__all__ = [
    'test_multiple_jobs_comparison',
    'test_pass2_inference',
    'test_pass3_analysis',
    'test_multiple_models',
    'AVAILABLE_MODELS',
]
