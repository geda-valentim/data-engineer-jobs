"""
Main evaluation logic for inter-model comparison.
"""

from datetime import datetime
from typing import Any, Dict, List

from .consensus import (
    boolean_consensus,
    categorical_consensus,
    confidence_aggregation,
    list_consensus,
    numeric_consensus,
    string_consensus,
)
from .field_registry import (
    PASS1_FIELDS,
    PASS2_FIELDS,
    PASS3_FIELDS,
    PASS3_SUMMARY_FIELDS,
    ARRAY,
    BOOLEAN,
    ENUM,
    INFERENCE,
    NUMERIC,
    STRING,
)
from .loader import (
    MODEL_NAMES,
    extract_pass1_field,
    extract_pass2_field,
    extract_pass3_field,
    extract_pass3_summary_field,
    get_job_metadata,
    load_all_passes,
)
from .models import FieldEvaluation, JobEvaluation, ModelPerformance
from .normalizers import normalize_model_values


def evaluate_pass1_field(
    field_name: str,
    field_type: str,
    outputs: Dict[str, Dict[str, Any]]
) -> FieldEvaluation:
    """Evaluate a single Pass 1 field across all models."""
    values = extract_pass1_field(outputs, field_name)
    normalized = normalize_model_values(values, field_type)

    if field_type == BOOLEAN:
        result = boolean_consensus(normalized)
        return FieldEvaluation(
            field_name=field_name,
            field_type=field_type,
            pass_number=1,
            has_consensus=result.has_consensus,
            consensus_value=result.consensus_value,
            agreement_rate=result.agreement_rate,
            model_values=values,
            outlier_models=result.outlier_models,
        )

    elif field_type == ENUM:
        result = categorical_consensus(normalized)
        return FieldEvaluation(
            field_name=field_name,
            field_type=field_type,
            pass_number=1,
            has_consensus=result.has_consensus,
            consensus_value=result.consensus_value,
            agreement_rate=result.agreement_rate,
            model_values=values,
            outlier_models=result.outlier_models,
            entropy=result.entropy,
        )

    elif field_type == NUMERIC:
        result = numeric_consensus(normalized)
        # All null = 100% agreement on null
        all_null = all(v is None for v in normalized.values())
        return FieldEvaluation(
            field_name=field_name,
            field_type=field_type,
            pass_number=1,
            has_consensus=result.has_consensus,
            consensus_value=result.consensus_value,
            agreement_rate=1.0 if (result.has_consensus or all_null) else 0.0,
            model_values=values,
            outlier_models=result.outlier_models,
            coefficient_of_variation=result.coefficient_of_variation,
        )

    elif field_type == ARRAY:
        result = list_consensus(normalized)
        return FieldEvaluation(
            field_name=field_name,
            field_type=field_type,
            pass_number=1,
            has_consensus=result.has_consensus,
            consensus_value=result.consensus_list,
            agreement_rate=result.core_agreement_rate,  # Use Core Agreement instead of Jaccard
            model_values=values,
            outlier_models=result.outlier_models,  # Use models with low core agreement
            jaccard_index=result.avg_jaccard,  # Keep Jaccard for reference
        )

    else:  # STRING
        result = string_consensus(normalized)
        # All null/empty = 100% agreement
        all_null = all(v is None or (isinstance(v, str) and not v.strip()) for v in normalized.values())
        return FieldEvaluation(
            field_name=field_name,
            field_type=field_type,
            pass_number=1,
            has_consensus=result.has_consensus,
            consensus_value=result.unique_values[0] if result.unique_values else None,
            agreement_rate=1.0 if all_null else result.avg_similarity,
            model_values=values,
            outlier_models=[],
            avg_similarity=result.avg_similarity,
        )


def evaluate_pass2_field(
    field_path: str,
    group: str,
    field: str,
    outputs: Dict[str, Dict[str, Any]]
) -> FieldEvaluation:
    """Evaluate a single Pass 2 inference field."""
    inference_objects = extract_pass2_field(outputs, group, field)
    result = confidence_aggregation(inference_objects)

    return FieldEvaluation(
        field_name=field_path,
        field_type=INFERENCE,
        pass_number=2,
        has_consensus=result.has_consensus,
        consensus_value=result.consensus_value,
        agreement_rate=result.agreement_rate,
        model_values={m: o.get("value") if o else None for m, o in inference_objects.items()},
        outlier_models=result.outlier_models,
        weighted_confidence=result.weighted_confidence,
    )


def evaluate_pass3_field(
    field_path: str,
    group: str,
    field: str,
    outputs: Dict[str, Dict[str, Any]]
) -> FieldEvaluation:
    """Evaluate a single Pass 3 analysis field."""
    inference_objects = extract_pass3_field(outputs, group, field)
    result = confidence_aggregation(inference_objects)

    return FieldEvaluation(
        field_name=field_path,
        field_type=INFERENCE,
        pass_number=3,
        has_consensus=result.has_consensus,
        consensus_value=result.consensus_value,
        agreement_rate=result.agreement_rate,
        model_values={m: o.get("value") if o else None for m, o in inference_objects.items()},
        outlier_models=result.outlier_models,
        weighted_confidence=result.weighted_confidence,
    )


def evaluate_pass3_summary_field(
    field_path: str,
    field_type: str,
    outputs: Dict[str, Dict[str, Any]]
) -> FieldEvaluation:
    """Evaluate a Pass 3 summary field (not inference object)."""
    field = field_path.split(".")[1]
    values = extract_pass3_summary_field(outputs, field)
    normalized = normalize_model_values(values, field_type)

    if field_type == ARRAY:
        result = list_consensus(normalized)
        return FieldEvaluation(
            field_name=field_path,
            field_type=field_type,
            pass_number=3,
            has_consensus=result.has_consensus,
            consensus_value=result.consensus_list,
            agreement_rate=result.core_agreement_rate,  # Use Core Agreement instead of Jaccard
            model_values=values,
            outlier_models=result.outlier_models,  # Use models with low core agreement
            jaccard_index=result.avg_jaccard,  # Keep Jaccard for reference
        )

    elif field_type == NUMERIC:
        result = numeric_consensus(normalized)
        all_null = all(v is None for v in normalized.values())
        return FieldEvaluation(
            field_name=field_path,
            field_type=field_type,
            pass_number=3,
            has_consensus=result.has_consensus,
            consensus_value=result.consensus_value,
            agreement_rate=1.0 if (result.has_consensus or all_null) else 0.0,
            model_values=values,
            outlier_models=result.outlier_models,
            coefficient_of_variation=result.coefficient_of_variation,
        )

    else:  # STRING
        result = string_consensus(normalized)
        all_null = all(v is None or (isinstance(v, str) and not v.strip()) for v in normalized.values())
        return FieldEvaluation(
            field_name=field_path,
            field_type=field_type,
            pass_number=3,
            has_consensus=result.has_consensus,
            consensus_value=result.unique_values[0] if result.unique_values else None,
            agreement_rate=1.0 if all_null else result.avg_similarity,
            model_values=values,
            outlier_models=[],
            avg_similarity=result.avg_similarity,
        )


def calculate_model_performance(
    evaluations: List[FieldEvaluation],
    models: List[str]
) -> Dict[str, ModelPerformance]:
    """Calculate performance metrics for each model."""
    performance = {}

    for model in models:
        total = 0
        matching = 0
        outlier_count = 0
        pass1_total, pass1_match = 0, 0
        pass2_total, pass2_match = 0, 0
        pass3_total, pass3_match = 0, 0

        for eval in evaluations:
            if model not in eval.model_values:
                continue

            total += 1
            is_outlier = model in eval.outlier_models

            if not is_outlier and eval.has_consensus:
                matching += 1
            if is_outlier:
                outlier_count += 1

            if eval.pass_number == 1:
                pass1_total += 1
                if not is_outlier and eval.has_consensus:
                    pass1_match += 1
            elif eval.pass_number == 2:
                pass2_total += 1
                if not is_outlier and eval.has_consensus:
                    pass2_match += 1
            else:
                pass3_total += 1
                if not is_outlier and eval.has_consensus:
                    pass3_match += 1

        performance[model] = ModelPerformance(
            model_id=model,
            model_name=MODEL_NAMES.get(model, model),
            total_fields=total,
            fields_matching_consensus=matching,
            agreement_rate=matching / total if total > 0 else 0,
            pass1_agreement=pass1_match / pass1_total if pass1_total > 0 else 0,
            pass2_agreement=pass2_match / pass2_total if pass2_total > 0 else 0,
            pass3_agreement=pass3_match / pass3_total if pass3_total > 0 else 0,
            outlier_count=outlier_count,
            outlier_rate=outlier_count / total if total > 0 else 0,
        )

    return performance


def evaluate_job(job_id: str, base_path: str = "data/local") -> JobEvaluation:
    """
    Generate complete evaluation report for a job.

    Args:
        job_id: Job posting ID
        base_path: Base path for data files

    Returns:
        JobEvaluation with all field evaluations and metrics
    """
    all_passes = load_all_passes(job_id, base_path)
    pass1_outputs = all_passes[1]
    pass2_outputs = all_passes[2]
    pass3_outputs = all_passes[3]

    metadata = get_job_metadata(pass1_outputs)
    models = list(pass1_outputs.keys())

    evaluations: List[FieldEvaluation] = []

    # Evaluate Pass 1 fields
    for field_name, field_type in PASS1_FIELDS.items():
        if pass1_outputs:
            eval_result = evaluate_pass1_field(field_name, field_type, pass1_outputs)
            evaluations.append(eval_result)

    # Evaluate Pass 2 fields
    for field_path, (group, field) in PASS2_FIELDS.items():
        if pass2_outputs:
            eval_result = evaluate_pass2_field(field_path, group, field, pass2_outputs)
            evaluations.append(eval_result)

    # Evaluate Pass 3 inference fields
    for field_path, (group, field) in PASS3_FIELDS.items():
        if pass3_outputs:
            eval_result = evaluate_pass3_field(field_path, group, field, pass3_outputs)
            evaluations.append(eval_result)

    # Evaluate Pass 3 summary fields
    for field_path, field_type in PASS3_SUMMARY_FIELDS.items():
        if pass3_outputs:
            eval_result = evaluate_pass3_summary_field(field_path, field_type, pass3_outputs)
            evaluations.append(eval_result)

    # Calculate metrics
    pass1_evals = [e for e in evaluations if e.pass_number == 1]
    pass2_evals = [e for e in evaluations if e.pass_number == 2]
    pass3_evals = [e for e in evaluations if e.pass_number == 3]

    pass1_rate = sum(1 for e in pass1_evals if e.has_consensus) / len(pass1_evals) if pass1_evals else 0
    pass2_rate = sum(1 for e in pass2_evals if e.has_consensus) / len(pass2_evals) if pass2_evals else 0
    pass3_rate = sum(1 for e in pass3_evals if e.has_consensus) / len(pass3_evals) if pass3_evals else 0
    overall_rate = sum(1 for e in evaluations if e.has_consensus) / len(evaluations) if evaluations else 0

    # Find high disagreement fields
    high_disagreement = [e.field_name for e in evaluations if e.agreement_rate < 0.5]

    # Calculate model performance
    model_performance = calculate_model_performance(evaluations, models)

    # Build consensus output
    consensus_output = {}
    for e in evaluations:
        if e.has_consensus and e.consensus_value is not None:
            consensus_output[e.field_name] = e.consensus_value

    return JobEvaluation(
        job_id=job_id,
        job_title=metadata.get("job_title", ""),
        company_name=metadata.get("company_name", ""),
        evaluated_at=datetime.now().isoformat(),
        models=models,
        overall_consensus_rate=overall_rate,
        pass1_consensus_rate=pass1_rate,
        pass2_consensus_rate=pass2_rate,
        pass3_consensus_rate=pass3_rate,
        field_evaluations=evaluations,
        model_performance=model_performance,
        consensus_output=consensus_output,
        high_disagreement_fields=high_disagreement,
    )
