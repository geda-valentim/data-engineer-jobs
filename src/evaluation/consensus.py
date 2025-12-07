"""
Consensus functions for computing agreement across multiple model outputs.
"""

import math
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from .models import (
    BooleanConsensusResult,
    CategoricalConsensusResult,
    ConfidenceAggregationResult,
    ListConsensusResult,
    NumericConsensusResult,
    StringConsensusResult,
)


def categorical_consensus(
    values: Dict[str, Optional[str]],
    min_agreement: float = 0.6
) -> CategoricalConsensusResult:
    """
    Compute consensus for categorical (enum) fields.

    Args:
        values: Dict mapping model_id -> extracted value
        min_agreement: Minimum agreement rate for consensus (default 60%)

    Returns:
        CategoricalConsensusResult with consensus analysis
    """
    non_null = {k: v for k, v in values.items() if v is not None}

    if not non_null:
        return CategoricalConsensusResult(
            consensus_value=None,
            agreement_rate=0.0,
            entropy=0.0,
            value_distribution={},
            outlier_models=list(values.keys()),
            has_consensus=False
        )

    counter = Counter(non_null.values())
    total = len(non_null)

    most_common_value, most_common_count = counter.most_common(1)[0]
    agreement_rate = most_common_count / total

    # Shannon entropy
    entropy = 0.0
    for count in counter.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)

    outlier_models = [
        model for model, value in values.items()
        if value != most_common_value
    ]

    has_consensus = agreement_rate >= min_agreement

    return CategoricalConsensusResult(
        consensus_value=most_common_value if has_consensus else None,
        agreement_rate=agreement_rate,
        entropy=entropy,
        value_distribution=dict(counter),
        outlier_models=outlier_models,
        has_consensus=has_consensus
    )


def numeric_consensus(
    values: Dict[str, Optional[float]],
    max_cv: float = 0.15,
    outlier_threshold: float = 2.0
) -> NumericConsensusResult:
    """
    Compute consensus for numeric fields.

    Args:
        values: Dict mapping model_id -> numeric value
        max_cv: Maximum coefficient of variation for consensus
        outlier_threshold: Z-score threshold for outlier detection
    """
    non_null = {k: v for k, v in values.items() if v is not None}
    null_count = len(values) - len(non_null)

    # All null = consensus on null
    if not non_null:
        all_null = all(v is None for v in values.values())
        return NumericConsensusResult(
            consensus_value=None,
            mean=None,
            median=None,
            std_dev=None,
            coefficient_of_variation=None,
            outlier_models=[],  # No outliers if all agree on null
            null_count=null_count,
            has_consensus=all_null and len(values) > 0
        )

    arr = np.array(list(non_null.values()))

    mean_val = float(np.mean(arr))
    median_val = float(np.median(arr))
    std_dev = float(np.std(arr)) if len(arr) > 1 else 0.0
    cv = std_dev / mean_val if mean_val != 0 else 0.0

    outlier_models = []
    if std_dev > 0:
        z_scores = (arr - mean_val) / std_dev
        for model, z_score in zip(non_null.keys(), z_scores):
            if abs(z_score) > outlier_threshold:
                outlier_models.append(model)

    outlier_models.extend([m for m in values if values[m] is None])

    has_consensus = cv <= max_cv and null_count <= 1

    return NumericConsensusResult(
        consensus_value=median_val if has_consensus else None,
        mean=mean_val,
        median=median_val,
        std_dev=std_dev,
        coefficient_of_variation=cv,
        outlier_models=outlier_models,
        null_count=null_count,
        has_consensus=has_consensus
    )


def boolean_consensus(
    values: Dict[str, Optional[bool]],
    min_agreement: float = 0.6
) -> BooleanConsensusResult:
    """
    Compute consensus for boolean fields.
    """
    non_null = {k: v for k, v in values.items() if v is not None}
    null_count = len(values) - len(non_null)

    if not non_null:
        return BooleanConsensusResult(
            consensus_value=None,
            agreement_rate=0.0,
            true_count=0,
            false_count=0,
            null_count=null_count,
            outlier_models=list(values.keys()),
            has_consensus=False
        )

    true_count = sum(1 for v in non_null.values() if v is True)
    false_count = sum(1 for v in non_null.values() if v is False)
    total = len(non_null)

    if true_count >= false_count:
        consensus_value = True
        agreement_rate = true_count / total
        outlier_models = [m for m, v in values.items() if v is not True]
    else:
        consensus_value = False
        agreement_rate = false_count / total
        outlier_models = [m for m, v in values.items() if v is not False]

    has_consensus = agreement_rate >= min_agreement

    return BooleanConsensusResult(
        consensus_value=consensus_value if has_consensus else None,
        agreement_rate=agreement_rate,
        true_count=true_count,
        false_count=false_count,
        null_count=null_count,
        outlier_models=outlier_models,
        has_consensus=has_consensus
    )


def list_consensus(
    lists: Dict[str, Optional[List[str]]],
    min_occurrence: float = 0.5,
    normalize: bool = True,
    core_agreement_threshold: float = 0.6
) -> ListConsensusResult:
    """
    Compute consensus for list/array fields using Core Agreement approach.

    Core Agreement measures what % of consensus items each model extracted.
    This avoids penalizing models that extract more detail.

    Args:
        lists: Dict mapping model_id -> list of strings
        min_occurrence: Minimum fraction of models an item must appear in
        normalize: Whether to lowercase and strip items
        core_agreement_threshold: Minimum core agreement rate to not be an outlier
    """
    normalized: Dict[str, Set[str]] = {}
    for model, items in lists.items():
        if items is None or not items:
            normalized[model] = set()
        else:
            if normalize:
                normalized[model] = {item.lower().strip() for item in items if item}
            else:
                normalized[model] = set(items)

    all_items: Counter = Counter()
    for items in normalized.values():
        for item in items:
            all_items[item] += 1

    total_models = len(lists)

    item_confidence: Dict[str, float] = {}
    consensus_list: List[str] = []

    for item, count in all_items.items():
        confidence = count / total_models
        item_confidence[item] = confidence
        if confidence >= min_occurrence:
            consensus_list.append(item)

    non_empty = [s for s in normalized.values() if s]
    if non_empty:
        union = set.union(*non_empty)
        intersection = set.intersection(*non_empty) if len(non_empty) > 1 else non_empty[0]
    else:
        union = set()
        intersection = set()

    jaccard_scores = []
    model_list = list(normalized.keys())
    for i in range(len(model_list)):
        for j in range(i + 1, len(model_list)):
            set_a = normalized[model_list[i]]
            set_b = normalized[model_list[j]]
            if set_a or set_b:
                jaccard = len(set_a & set_b) / len(set_a | set_b) if (set_a | set_b) else 0
                jaccard_scores.append(jaccard)
            else:
                # Both empty = perfect agreement
                jaccard_scores.append(1.0)

    avg_jaccard = sum(jaccard_scores) / len(jaccard_scores) if jaccard_scores else 1.0

    outlier_items: Dict[str, List[str]] = {}
    for model, items in normalized.items():
        unique = [item for item in items if all_items[item] == 1]
        if unique:
            outlier_items[model] = unique

    # Core Agreement: % of consensus items each model extracted
    consensus_set = set(consensus_list)
    model_core_agreement: Dict[str, float] = {}
    outlier_models: List[str] = []

    if consensus_list:
        for model, items in normalized.items():
            # How many consensus items did this model include?
            covered = len(items & consensus_set)
            core_rate = covered / len(consensus_set)
            model_core_agreement[model] = core_rate
            if core_rate < core_agreement_threshold:
                outlier_models.append(model)

        core_agreement_rate = sum(model_core_agreement.values()) / len(model_core_agreement)
    else:
        # No consensus items - all empty or too dispersed
        core_agreement_rate = 1.0 if all(len(s) == 0 for s in normalized.values()) else 0.0
        model_core_agreement = {m: core_agreement_rate for m in normalized.keys()}

    # All empty arrays = consensus on empty list
    all_empty = all(len(s) == 0 for s in normalized.values())
    has_consensus = all_empty or (core_agreement_rate >= 0.6 and len(consensus_list) > 0)

    return ListConsensusResult(
        consensus_list=sorted(consensus_list),
        item_confidence=item_confidence,
        avg_jaccard=avg_jaccard,
        union_size=len(union),
        intersection_size=len(intersection),
        outlier_items=outlier_items,
        has_consensus=has_consensus,
        core_agreement_rate=core_agreement_rate,
        model_core_agreement=model_core_agreement,
        outlier_models=outlier_models,
    )


def string_consensus(
    values: Dict[str, Optional[str]],
    similarity_threshold: float = 0.85
) -> StringConsensusResult:
    """
    Compute consensus for free-text string fields using fuzzy matching.
    """
    non_null = {k: v for k, v in values.items() if v is not None and v.strip()}
    null_count = len(values) - len(non_null)

    # All null/empty = consensus on null
    if not non_null:
        all_null = all(v is None or (isinstance(v, str) and not v.strip()) for v in values.values())
        return StringConsensusResult(
            has_consensus=all_null and len(values) > 0,
            unique_values=[],
            similarity_matrix={},
            avg_similarity=1.0 if all_null else 0.0,
            null_count=null_count
        )

    unique_values = list(set(non_null.values()))

    similarity_matrix: Dict[Tuple[str, str], float] = {}
    model_list = list(non_null.keys())
    similarities = []

    for i in range(len(model_list)):
        for j in range(i + 1, len(model_list)):
            m1, m2 = model_list[i], model_list[j]
            s1, s2 = non_null[m1], non_null[m2]
            ratio = SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
            similarity_matrix[(m1, m2)] = ratio
            similarities.append(ratio)

    avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

    has_consensus = len(unique_values) == 1 or avg_similarity >= similarity_threshold

    return StringConsensusResult(
        has_consensus=has_consensus,
        unique_values=unique_values,
        similarity_matrix=similarity_matrix,
        avg_similarity=avg_similarity,
        null_count=null_count
    )


def confidence_aggregation(
    inference_objects: Dict[str, Optional[Dict[str, Any]]],
    min_agreement: float = 0.6
) -> ConfidenceAggregationResult:
    """
    Aggregate inference objects with value + confidence.
    """
    valid_entries: Dict[str, Tuple[Any, float]] = {}
    for model, obj in inference_objects.items():
        if obj is not None and isinstance(obj, dict):
            value = obj.get("value")
            conf = obj.get("confidence", 0.5)
            if value is not None:
                valid_entries[model] = (value, conf)

    if not valid_entries:
        return ConfidenceAggregationResult(
            consensus_value=None,
            weighted_confidence=0.0,
            agreement_rate=0.0,
            value_distribution={},
            outlier_models=list(inference_objects.keys()),
            has_consensus=False
        )

    value_stats: Dict[str, List[Tuple[str, float]]] = {}
    for model, (value, conf) in valid_entries.items():
        key = str(value) if isinstance(value, (list, dict)) else str(value)
        if key not in value_stats:
            value_stats[key] = []
        value_stats[key].append((model, conf))

    total_models = len(valid_entries)
    best_value = None
    best_count = 0
    best_avg_conf = 0.0

    value_distribution: Dict[str, Tuple[int, float]] = {}
    for value, entries in value_stats.items():
        count = len(entries)
        avg_conf = sum(conf for _, conf in entries) / count
        value_distribution[value] = (count, avg_conf)

        if count > best_count or (count == best_count and avg_conf > best_avg_conf):
            best_value = value
            best_count = count
            best_avg_conf = avg_conf

    agreement_rate = best_count / total_models if total_models > 0 else 0.0

    outlier_models = []
    for model, (value, _) in valid_entries.items():
        key = str(value) if isinstance(value, (list, dict)) else str(value)
        if key != best_value:
            outlier_models.append(model)
    outlier_models.extend([m for m in inference_objects if m not in valid_entries])

    has_consensus = agreement_rate >= min_agreement

    consensus_value = None
    if has_consensus and best_value is not None:
        for model, (value, _) in valid_entries.items():
            key = str(value) if isinstance(value, (list, dict)) else str(value)
            if key == best_value:
                consensus_value = value
                break

    return ConfidenceAggregationResult(
        consensus_value=consensus_value,
        weighted_confidence=best_avg_conf,
        agreement_rate=agreement_rate,
        value_distribution=value_distribution,
        outlier_models=outlier_models,
        has_consensus=has_consensus
    )
