"""
Data models for inter-model evaluation results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CategoricalConsensusResult:
    """Result of categorical field consensus analysis."""
    consensus_value: Optional[str]
    agreement_rate: float
    entropy: float
    value_distribution: Dict[str, int]
    outlier_models: List[str]
    has_consensus: bool


@dataclass
class NumericConsensusResult:
    """Result of numeric field consensus analysis."""
    consensus_value: Optional[float]
    mean: Optional[float]
    median: Optional[float]
    std_dev: Optional[float]
    coefficient_of_variation: Optional[float]
    outlier_models: List[str]
    null_count: int
    has_consensus: bool


@dataclass
class BooleanConsensusResult:
    """Result of boolean field consensus analysis."""
    consensus_value: Optional[bool]
    agreement_rate: float
    true_count: int
    false_count: int
    null_count: int
    outlier_models: List[str]
    has_consensus: bool


@dataclass
class ListConsensusResult:
    """Result of list/array field consensus analysis."""
    consensus_list: List[str]
    item_confidence: Dict[str, float]
    avg_jaccard: float
    union_size: int
    intersection_size: int
    outlier_items: Dict[str, List[str]]
    has_consensus: bool
    # Core Agreement metrics
    core_agreement_rate: float = 0.0  # % of consensus items covered by models (avg)
    model_core_agreement: Dict[str, float] = field(default_factory=dict)  # Per-model coverage
    outlier_models: List[str] = field(default_factory=list)  # Models with low core agreement


@dataclass
class StringConsensusResult:
    """Result of free-text string field consensus analysis."""
    has_consensus: bool
    unique_values: List[str]
    similarity_matrix: Dict[Tuple[str, str], float]
    avg_similarity: float
    null_count: int


@dataclass
class ConfidenceAggregationResult:
    """Result of inference object consensus (value + confidence)."""
    consensus_value: Optional[Any]
    weighted_confidence: float
    agreement_rate: float
    value_distribution: Dict[str, Tuple[int, float]]
    outlier_models: List[str]
    has_consensus: bool


@dataclass
class FieldEvaluation:
    """Evaluation result for a single field."""
    field_name: str
    field_type: str
    pass_number: int
    has_consensus: bool
    consensus_value: Optional[Any]
    agreement_rate: float
    model_values: Dict[str, Any]
    outlier_models: List[str]
    entropy: Optional[float] = None
    coefficient_of_variation: Optional[float] = None
    jaccard_index: Optional[float] = None
    avg_similarity: Optional[float] = None
    weighted_confidence: Optional[float] = None


@dataclass
class ModelPerformance:
    """Performance metrics for a single model."""
    model_id: str
    model_name: str
    total_fields: int
    fields_matching_consensus: int
    agreement_rate: float
    pass1_agreement: float
    pass2_agreement: float
    pass3_agreement: float
    outlier_count: int
    outlier_rate: float
    avg_confidence_when_correct: float = 0.0
    avg_confidence_when_wrong: float = 0.0


@dataclass
class JobEvaluation:
    """Complete evaluation for a single job posting."""
    job_id: str
    job_title: str
    company_name: str
    evaluated_at: str
    models: List[str]
    overall_consensus_rate: float
    pass1_consensus_rate: float
    pass2_consensus_rate: float
    pass3_consensus_rate: float
    field_evaluations: List[FieldEvaluation]
    model_performance: Dict[str, ModelPerformance]
    consensus_output: Dict[str, Any]
    high_disagreement_fields: List[str] = field(default_factory=list)
