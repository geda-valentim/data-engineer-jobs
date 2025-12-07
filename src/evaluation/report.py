"""
Markdown report generation for inter-model evaluation.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import FieldEvaluation, JobEvaluation


def format_value(value, truncate: bool = False) -> str:
    """Format a value for display."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return f"{value:.4f}" if value < 1 else f"{value:,.2f}"
    if isinstance(value, list):
        if truncate and len(value) > 5:
            return f"[{', '.join(str(v) for v in value[:5])}... +{len(value)-5}]"
        return f"[{', '.join(str(v) for v in value)}]"
    return str(value)


def format_agreement(rate: float) -> str:
    """Format agreement rate with visual indicator."""
    pct = rate * 100
    if rate >= 0.8:
        return f"{pct:.0f}%"
    elif rate >= 0.6:
        return f"{pct:.0f}%"
    else:
        return f"{pct:.0f}%"


def generate_summary_section(evaluation: JobEvaluation) -> str:
    """Generate the summary section."""
    lines = [
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Job ID | {evaluation.job_id} |",
        f"| Job Title | {evaluation.job_title} |",
        f"| Company | {evaluation.company_name} |",
        f"| Models Compared | {len(evaluation.models)} |",
        f"| Total Fields | {len(evaluation.field_evaluations)} |",
        f"| Overall Consensus Rate | {format_agreement(evaluation.overall_consensus_rate)} |",
        f"| Pass 1 Consensus Rate | {format_agreement(evaluation.pass1_consensus_rate)} |",
        f"| Pass 2 Consensus Rate | {format_agreement(evaluation.pass2_consensus_rate)} |",
        f"| Pass 3 Consensus Rate | {format_agreement(evaluation.pass3_consensus_rate)} |",
        "",
    ]
    return "\n".join(lines)


def calculate_intermodel_score(perf) -> float:
    """
    Calculate intermodel fit score (0-100).
    Higher = better fit with consensus.

    Formula: (agreement * 0.6) + ((1 - outlier_rate) * 0.4)
    """
    agreement_component = perf.agreement_rate * 0.6
    consistency_component = (1 - perf.outlier_rate) * 0.4
    return (agreement_component + consistency_component) * 100


def generate_model_performance_section(evaluation: JobEvaluation) -> str:
    """Generate the model performance section with intermodel scores."""
    # Calculate scores for all models
    model_scores = []
    for model, perf in evaluation.model_performance.items():
        score = calculate_intermodel_score(perf)
        model_scores.append((model, perf, score))

    # Sort by score descending
    model_scores.sort(key=lambda x: x[2], reverse=True)

    lines = [
        "## Model Performance",
        "",
        "| Model | Agreement | Pass1 | Pass2 | Pass3 | Outlier Rate | **Intermodel Score** |",
        "|-------|-----------|-------|-------|-------|--------------|----------------------|",
    ]

    for model, perf, score in model_scores:
        lines.append(
            f"| {perf.model_name} | {format_agreement(perf.agreement_rate)} | "
            f"{format_agreement(perf.pass1_agreement)} | "
            f"{format_agreement(perf.pass2_agreement)} | "
            f"{format_agreement(perf.pass3_agreement)} | "
            f"{format_agreement(perf.outlier_rate)} | **{score:.1f}** |"
        )

    lines.append("")

    # Best and Worst model summary
    best_model, best_perf, best_score = model_scores[0]
    worst_model, worst_perf, worst_score = model_scores[-1]

    lines.append("### Best & Worst Intermodel Fit")
    lines.append("")
    lines.append(f"| Metric | 🏆 Best | ⚠️ Worst |")
    lines.append(f"|--------|---------|----------|")
    lines.append(f"| **Model** | {best_perf.model_name} | {worst_perf.model_name} |")
    lines.append(f"| **Intermodel Score** | {best_score:.1f} | {worst_score:.1f} |")
    lines.append(f"| **Agreement Rate** | {format_agreement(best_perf.agreement_rate)} | {format_agreement(worst_perf.agreement_rate)} |")
    lines.append(f"| **Outlier Rate** | {format_agreement(best_perf.outlier_rate)} | {format_agreement(worst_perf.outlier_rate)} |")
    lines.append(f"| **Pass 1 (Extraction)** | {format_agreement(best_perf.pass1_agreement)} | {format_agreement(worst_perf.pass1_agreement)} |")
    lines.append(f"| **Pass 2 (Inference)** | {format_agreement(best_perf.pass2_agreement)} | {format_agreement(worst_perf.pass2_agreement)} |")
    lines.append(f"| **Pass 3 (Analysis)** | {format_agreement(best_perf.pass3_agreement)} | {format_agreement(worst_perf.pass3_agreement)} |")
    lines.append("")

    # Score interpretation
    lines.append("> **Intermodel Score**: Composite metric (0-100) combining agreement rate (60%) and consistency (40%). Higher = better fit with consensus.")
    lines.append("")

    return "\n".join(lines)


def generate_consensus_by_field_type_section(
    evaluation: JobEvaluation
) -> str:
    """Generate consensus breakdown by field type - shows where gaps are."""
    # Group fields by type
    type_groups = {
        "boolean": [],
        "enum": [],
        "numeric": [],
        "string": [],
        "array": [],
        "inference": [],
    }

    for fe in evaluation.field_evaluations:
        ftype = fe.field_type
        if ftype in type_groups:
            type_groups[ftype].append(fe)
        else:
            type_groups["inference"].append(fe)

    lines = [
        "## Consensus by Field Type",
        "",
        "> Shows average inter-model agreement per field type. Lower = more disagreement = gaps to address.",
        "",
        "| Field Type | Fields | With Consensus | Avg Agreement | Gap Level |",
        "|------------|--------|----------------|---------------|-----------|",
    ]

    type_stats = []
    for ftype in ["boolean", "enum", "numeric", "string", "array", "inference"]:
        fields = type_groups[ftype]
        if not fields:
            continue

        count = len(fields)
        with_consensus = sum(1 for f in fields if f.has_consensus)
        avg_agreement = sum(f.agreement_rate for f in fields) / count

        # Gap level indicator
        if avg_agreement >= 0.9:
            gap = "✅ Low"
        elif avg_agreement >= 0.7:
            gap = "⚠️ Medium"
        else:
            gap = "🔴 High"

        type_stats.append((ftype, count, with_consensus, avg_agreement, gap))
        lines.append(
            f"| **{ftype.capitalize()}** | {count} | {with_consensus} ({with_consensus*100//count}%) | "
            f"{format_agreement(avg_agreement)} | {gap} |"
        )

    lines.append("")

    # Identify biggest gaps
    sorted_by_agreement = sorted(type_stats, key=lambda x: x[3])
    if sorted_by_agreement:
        worst = sorted_by_agreement[0]
        lines.append(f"**Biggest Gap**: {worst[0].capitalize()} fields ({format_agreement(worst[3])} avg agreement)")
        lines.append("")

    return "\n".join(lines)


def generate_model_by_field_type_section(
    evaluation: JobEvaluation
) -> str:
    """Generate model performance breakdown by field type."""
    # Group fields by type
    type_groups = {
        "boolean": [],
        "enum": [],
        "numeric": [],
        "string": [],
        "array": [],
        "inference": [],
    }

    for fe in evaluation.field_evaluations:
        ftype = fe.field_type
        if ftype in type_groups:
            type_groups[ftype].append(fe)
        else:
            type_groups["inference"].append(fe)

    # Calculate per-model, per-type agreement
    models = evaluation.models
    model_type_scores = {m: {} for m in models}

    for ftype, fields in type_groups.items():
        if not fields:
            continue
        for model in models:
            matches = 0
            total = 0
            for fe in fields:
                if fe.has_consensus and fe.consensus_value is not None:
                    total += 1
                    if model not in fe.outlier_models:
                        matches += 1
            if total > 0:
                model_type_scores[model][ftype] = matches / total
            else:
                model_type_scores[model][ftype] = None

    # Short names
    short_names = {
        "gpt-oss": "GPT-OSS",
        "mistral": "Mistral",
        "gemma": "Gemma",
        "minimax": "MiniMax",
        "qwen": "Qwen",
    }

    lines = [
        "### Model Fit by Field Type",
        "",
        "> Shows how often each model agrees with the consensus, per field type.",
        "",
        "| Model | Boolean | Enum | Numeric | String | Array | Inference |",
        "|-------|---------|------|---------|--------|-------|-----------|",
    ]

    for model in models:
        scores = model_type_scores[model]
        row = f"| {short_names.get(model, model)} |"
        for ftype in ["boolean", "enum", "numeric", "string", "array", "inference"]:
            score = scores.get(ftype)
            if score is not None:
                row += f" {format_agreement(score)} |"
            else:
                row += " - |"
        lines.append(row)

    lines.append("")

    # Find best model per type
    lines.append("**Best Model per Field Type:**")
    lines.append("")
    for ftype in ["boolean", "enum", "numeric", "string", "array", "inference"]:
        best_model = None
        best_score = -1
        for model in models:
            score = model_type_scores[model].get(ftype)
            if score is not None and score > best_score:
                best_score = score
                best_model = model
        if best_model:
            lines.append(f"- **{ftype.capitalize()}**: {short_names.get(best_model, best_model)} ({format_agreement(best_score)})")

    lines.append("")
    return "\n".join(lines)


def generate_high_agreement_section(
    evaluations: List[FieldEvaluation],
) -> str:
    """Generate section for fields with high agreement."""
    high_agreement = [e for e in evaluations if e.agreement_rate >= 0.8 and e.has_consensus]
    high_agreement.sort(key=lambda x: (-x.agreement_rate, x.field_name))

    lines = [
        "## High Agreement Fields (>= 80%)",
        "",
        f"| Field | Type | Pass | Agreement | Consensus Value |",
        f"|-------|------|------|-----------|-----------------|",
    ]

    for e in high_agreement:
        lines.append(
            f"| `{e.field_name}` | {e.field_type} | {e.pass_number} | "
            f"{format_agreement(e.agreement_rate)} | {format_value(e.consensus_value, truncate=True)} |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_low_agreement_section(
    evaluations: List[FieldEvaluation],
) -> str:
    """Generate section for fields with low agreement."""
    low_agreement = [e for e in evaluations if e.agreement_rate < 0.6]
    low_agreement.sort(key=lambda x: (x.agreement_rate, x.field_name))

    if not low_agreement:
        return "## Low Agreement Fields (< 60%)\n\nNo fields with low agreement.\n"

    lines = [
        "## Low Agreement Fields (< 60%)",
        "",
        f"| Field | Type | Pass | Agreement | Outliers |",
        f"|-------|------|------|-----------|----------|",
    ]

    for e in low_agreement:
        outliers = ", ".join(e.outlier_models) if e.outlier_models else "none"
        lines.append(
            f"| `{e.field_name}` | {e.field_type} | {e.pass_number} | "
            f"{format_agreement(e.agreement_rate)} | {outliers} |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_field_table(
    e: FieldEvaluation,
    models: List[str],
    short_names: dict
) -> List[str]:
    """Generate table for a single field showing all model values."""
    lines = []
    lines.append(f"### `{e.field_name}`")
    lines.append("")
    lines.append(f"**Type**: {e.field_type} | **Pass**: {e.pass_number} | "
                f"**Agreement**: {format_agreement(e.agreement_rate)} | "
                f"**Consensus**: {e.has_consensus}")
    lines.append("")

    # Model values table
    lines.append("| Model | Value |")
    lines.append("|-------|-------|")
    for model in models:
        value = e.model_values.get(model)
        marker = " ⚠️" if model in e.outlier_models else ""
        model_display = short_names.get(model, model)
        lines.append(f"| {model_display} | {format_value(value)}{marker} |")

    lines.append("")
    if e.consensus_value is not None:
        lines.append(f"**Consensus Value**: `{format_value(e.consensus_value)}`")
        lines.append("")

    return lines


def generate_all_fields_section(
    evaluations: List[FieldEvaluation],
    models: List[str],
    pass_num: int
) -> str:
    """Generate detailed comparison for all fields in a pass."""
    pass_evals = [e for e in evaluations if e.pass_number == pass_num]
    pass_evals.sort(key=lambda x: (-x.agreement_rate, x.field_name))

    if not pass_evals:
        return ""

    # Short model names for readability
    short_names = {
        "gpt-oss": "GPT-OSS",
        "mistral": "Mistral",
        "gemma": "Gemma",
        "minimax": "MiniMax",
        "qwen": "Qwen",
    }

    lines = [
        f"## Pass {pass_num} - All Fields Detail",
        "",
    ]

    for e in pass_evals:
        lines.extend(generate_field_table(e, models, short_names))
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_detailed_comparison_section(
    evaluations: List[FieldEvaluation],
    models: List[str],
    field_filter: Optional[List[str]] = None
) -> str:
    """Generate detailed per-field comparison (key fields summary)."""
    lines = [
        "## Key Fields Comparison",
        "",
    ]

    # Key fields to highlight
    key_fields = field_filter or [
        "ext_salary_min",
        "ext_salary_max",
        "ext_work_model_stated",
        "ext_employment_type_stated",
        "ext_must_have_hard_skills",
        "seniority_and_role.seniority_level",
        "stack_and_cloud.primary_cloud",
        "company_maturity.data_maturity_score",
        "red_flags_and_role_quality.overall_red_flag_score",
        "summary.recommendation_score",
    ]

    short_names = {
        "gpt-oss": "GPT-OSS",
        "mistral": "Mistral",
        "gemma": "Gemma",
        "minimax": "MiniMax",
        "qwen": "Qwen",
    }

    for e in evaluations:
        if e.field_name not in key_fields:
            continue
        lines.extend(generate_field_table(e, models, short_names))

    return "\n".join(lines)


def generate_pass_breakdown_section(
    evaluations: List[FieldEvaluation],
    pass_num: int
) -> str:
    """Generate breakdown for a specific pass."""
    pass_evals = [e for e in evaluations if e.pass_number == pass_num]

    if not pass_evals:
        return f"## Pass {pass_num} Breakdown\n\nNo data for this pass.\n"

    consensus_count = sum(1 for e in pass_evals if e.has_consensus)
    avg_agreement = sum(e.agreement_rate for e in pass_evals) / len(pass_evals)

    lines = [
        f"## Pass {pass_num} Breakdown",
        "",
        f"- **Total Fields**: {len(pass_evals)}",
        f"- **Fields with Consensus**: {consensus_count} ({consensus_count/len(pass_evals)*100:.0f}%)",
        f"- **Average Agreement**: {avg_agreement*100:.1f}%",
        "",
    ]

    # Group by field type
    by_type = {}
    for e in pass_evals:
        if e.field_type not in by_type:
            by_type[e.field_type] = []
        by_type[e.field_type].append(e)

    lines.append("### By Field Type")
    lines.append("")
    lines.append("| Type | Count | Consensus | Avg Agreement |")
    lines.append("|------|-------|-----------|---------------|")

    for ftype, evals in sorted(by_type.items()):
        count = len(evals)
        cons = sum(1 for e in evals if e.has_consensus)
        avg = sum(e.agreement_rate for e in evals) / len(evals)
        lines.append(f"| {ftype} | {count} | {cons} | {avg*100:.1f}% |")

    lines.append("")
    return "\n".join(lines)


def generate_report(evaluation: JobEvaluation, output_path: Optional[str] = None) -> str:
    """
    Generate a complete markdown evaluation report.

    Args:
        evaluation: JobEvaluation result
        output_path: Optional path to save the report

    Returns:
        Markdown content as string
    """
    sections = [
        f"# Inter-Model Evaluation Report",
        "",
        f"> Generated: {evaluation.evaluated_at}",
        "",
        generate_summary_section(evaluation),
        generate_consensus_by_field_type_section(evaluation),
        generate_model_performance_section(evaluation),
        generate_model_by_field_type_section(evaluation),
        generate_high_agreement_section(evaluation.field_evaluations),
        generate_low_agreement_section(evaluation.field_evaluations),
        generate_detailed_comparison_section(
            evaluation.field_evaluations,
            evaluation.models
        ),
        generate_pass_breakdown_section(evaluation.field_evaluations, 1),
        generate_all_fields_section(evaluation.field_evaluations, evaluation.models, 1),
        generate_pass_breakdown_section(evaluation.field_evaluations, 2),
        generate_all_fields_section(evaluation.field_evaluations, evaluation.models, 2),
        generate_pass_breakdown_section(evaluation.field_evaluations, 3),
        generate_all_fields_section(evaluation.field_evaluations, evaluation.models, 3),
    ]

    content = "\n".join(sections)

    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")

    return content
