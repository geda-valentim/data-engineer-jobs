"""
Inter-Model Evaluation Module for AI Enrichment.

This module provides tools for comparing outputs from multiple LLMs
and computing consensus values across models.

Usage:
    from src.evaluation import evaluate_job, generate_report

    # Evaluate a job
    result = evaluate_job("4323400548")

    # Generate markdown report
    report = generate_report(result, output_path="report.md")
"""

from .evaluator import evaluate_job
from .models import (
    BooleanConsensusResult,
    CategoricalConsensusResult,
    ConfidenceAggregationResult,
    FieldEvaluation,
    JobEvaluation,
    ListConsensusResult,
    ModelPerformance,
    NumericConsensusResult,
    StringConsensusResult,
)
from .report import generate_report

__all__ = [
    # Main functions
    "evaluate_job",
    "generate_report",
    # Result models
    "JobEvaluation",
    "FieldEvaluation",
    "ModelPerformance",
    "CategoricalConsensusResult",
    "NumericConsensusResult",
    "BooleanConsensusResult",
    "ListConsensusResult",
    "StringConsensusResult",
    "ConfidenceAggregationResult",
]
