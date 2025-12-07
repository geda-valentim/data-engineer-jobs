#!/usr/bin/env python3
"""
CLI script for inter-model evaluation.

Usage:
    python scripts/evaluate_models.py 4323400548
    python scripts/evaluate_models.py 4323400548 --output reports/
    python scripts/evaluate_models.py 4323400548 --base-path data/local
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import evaluate_job, generate_report


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate inter-model agreement for AI enrichment outputs"
    )
    parser.add_argument(
        "job_id",
        help="Job posting ID to evaluate"
    )
    parser.add_argument(
        "--base-path",
        default="data/local",
        help="Base path for data files (default: data/local)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory for report (default: prints to stdout)"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )

    args = parser.parse_args()

    # Check if job directory exists
    job_dir = Path(args.base_path) / args.job_id
    if not job_dir.exists():
        print(f"Error: Job directory not found: {job_dir}", file=sys.stderr)
        sys.exit(1)

    # Run evaluation
    print(f"Evaluating job {args.job_id}...", file=sys.stderr)
    evaluation = evaluate_job(args.job_id, args.base_path)

    # Generate report
    if args.format == "markdown":
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"evaluation_{args.job_id}.md"
            report = generate_report(evaluation, str(output_file))
            print(f"Report saved to: {output_file}", file=sys.stderr)
        else:
            report = generate_report(evaluation)
            print(report)

    elif args.format == "json":
        import json
        from dataclasses import asdict

        # Convert to dict for JSON serialization
        def to_dict(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: to_dict(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [to_dict(v) for v in obj]
            return obj

        output = to_dict(evaluation)

        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"evaluation_{args.job_id}.json"
            with open(output_file, "w") as f:
                json.dump(output, f, indent=2, default=str)
            print(f"Report saved to: {output_file}", file=sys.stderr)
        else:
            print(json.dumps(output, indent=2, default=str))

    # Print summary to stderr
    print(f"\n--- Summary ---", file=sys.stderr)
    print(f"Job: {evaluation.job_title} @ {evaluation.company_name}", file=sys.stderr)
    print(f"Models: {len(evaluation.models)}", file=sys.stderr)
    print(f"Fields evaluated: {len(evaluation.field_evaluations)}", file=sys.stderr)
    print(f"Overall consensus: {evaluation.overall_consensus_rate*100:.1f}%", file=sys.stderr)
    print(f"  Pass 1: {evaluation.pass1_consensus_rate*100:.1f}%", file=sys.stderr)
    print(f"  Pass 2: {evaluation.pass2_consensus_rate*100:.1f}%", file=sys.stderr)
    print(f"  Pass 3: {evaluation.pass3_consensus_rate*100:.1f}%", file=sys.stderr)

    if evaluation.high_disagreement_fields:
        print(f"\nHigh disagreement fields ({len(evaluation.high_disagreement_fields)}):", file=sys.stderr)
        for field in evaluation.high_disagreement_fields[:5]:
            print(f"  - {field}", file=sys.stderr)


if __name__ == "__main__":
    main()
