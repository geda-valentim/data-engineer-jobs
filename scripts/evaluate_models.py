#!/usr/bin/env python3
"""
CLI script for inter-model evaluation.

Usage:
    python scripts/evaluate_models.py 4323400548
    python scripts/evaluate_models.py 4323400548 --output reports/
    python scripts/evaluate_models.py --all --output reports/
    python scripts/evaluate_models.py 4323400548 --base-path data/local
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import evaluate_job, generate_report


def evaluate_single_job(job_id: str, base_path: str, output_dir: str = None, output_format: str = "markdown") -> dict:
    """Evaluate a single job and return summary stats."""
    job_dir = Path(base_path) / job_id
    if not job_dir.exists():
        print(f"Error: Job directory not found: {job_dir}", file=sys.stderr)
        return None

    print(f"Evaluating job {job_id}...", file=sys.stderr)
    evaluation = evaluate_job(job_id, base_path)

    # Generate report
    if output_format == "markdown":
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            output_file = output_path / f"evaluation_{job_id}.md"
            generate_report(evaluation, str(output_file))
            print(f"  Report saved to: {output_file}", file=sys.stderr)
        else:
            report = generate_report(evaluation)
            print(report)

    elif output_format == "json":
        import json
        from dataclasses import asdict

        def to_dict(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: to_dict(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [to_dict(v) for v in obj]
            return obj

        output = to_dict(evaluation)

        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            output_file = output_path / f"evaluation_{job_id}.json"
            with open(output_file, "w") as f:
                json.dump(output, f, indent=2, default=str)
            print(f"  Report saved to: {output_file}", file=sys.stderr)
        else:
            print(json.dumps(output, indent=2, default=str))

    return {
        "job_id": job_id,
        "job_title": evaluation.job_title,
        "company_name": evaluation.company_name,
        "overall_consensus": evaluation.overall_consensus_rate,
        "pass1_consensus": evaluation.pass1_consensus_rate,
        "pass2_consensus": evaluation.pass2_consensus_rate,
        "pass3_consensus": evaluation.pass3_consensus_rate,
        "fields_evaluated": len(evaluation.field_evaluations),
        "high_disagreement_count": len(evaluation.high_disagreement_fields),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate inter-model agreement for AI enrichment outputs"
    )
    parser.add_argument(
        "job_id",
        nargs="?",
        default=None,
        help="Job posting ID to evaluate (optional if --all is used)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all jobs in base-path directory"
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

    # Validate arguments
    if not args.all and not args.job_id:
        print("Error: Either provide a job_id or use --all flag", file=sys.stderr)
        sys.exit(1)

    if args.all:
        # Find all job directories
        base_path = Path(args.base_path)
        if not base_path.exists():
            print(f"Error: Base path not found: {base_path}", file=sys.stderr)
            sys.exit(1)

        job_dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name.isdigit()]
        if not job_dirs:
            print(f"Error: No job directories found in {base_path}", file=sys.stderr)
            sys.exit(1)

        print(f"\n{'='*80}", file=sys.stderr)
        print(f"Evaluating {len(job_dirs)} jobs from {base_path}", file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)

        results = []
        for job_dir in sorted(job_dirs):
            result = evaluate_single_job(
                job_dir.name,
                args.base_path,
                args.output,
                args.format
            )
            if result:
                results.append(result)

        # Print summary table
        print(f"\n{'='*80}", file=sys.stderr)
        print("SUMMARY - All Jobs", file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)

        print(f"{'Job ID':<15} {'Company':<20} {'Overall':<10} {'Pass1':<10} {'Pass2':<10} {'Pass3':<10}", file=sys.stderr)
        print("-" * 75, file=sys.stderr)

        total_overall = 0
        total_pass1 = 0
        total_pass2 = 0
        total_pass3 = 0

        for r in results:
            print(
                f"{r['job_id']:<15} "
                f"{r['company_name'][:18]:<20} "
                f"{r['overall_consensus']*100:>6.1f}%   "
                f"{r['pass1_consensus']*100:>6.1f}%   "
                f"{r['pass2_consensus']*100:>6.1f}%   "
                f"{r['pass3_consensus']*100:>6.1f}%",
                file=sys.stderr
            )
            total_overall += r['overall_consensus']
            total_pass1 += r['pass1_consensus']
            total_pass2 += r['pass2_consensus']
            total_pass3 += r['pass3_consensus']

        n = len(results)
        if n > 0:
            print("-" * 75, file=sys.stderr)
            print(
                f"{'AVERAGE':<15} "
                f"{'':<20} "
                f"{total_overall/n*100:>6.1f}%   "
                f"{total_pass1/n*100:>6.1f}%   "
                f"{total_pass2/n*100:>6.1f}%   "
                f"{total_pass3/n*100:>6.1f}%",
                file=sys.stderr
            )

        # Generate summary report if output specified
        if args.output and args.format == "markdown":
            summary_file = Path(args.output) / "SUMMARY_ALL_JOBS.md"
            with open(summary_file, "w") as f:
                f.write("# Inter-Model Evaluation Summary\n\n")
                f.write(f"> Generated: {datetime.now().isoformat()}\n\n")
                f.write(f"## Overview\n\n")
                f.write(f"- **Jobs Evaluated**: {len(results)}\n")
                f.write(f"- **Average Overall Consensus**: {total_overall/n*100:.1f}%\n")
                f.write(f"- **Average Pass 1 Consensus**: {total_pass1/n*100:.1f}%\n")
                f.write(f"- **Average Pass 2 Consensus**: {total_pass2/n*100:.1f}%\n")
                f.write(f"- **Average Pass 3 Consensus**: {total_pass3/n*100:.1f}%\n\n")
                f.write("## Per-Job Results\n\n")
                f.write("| Job ID | Company | Overall | Pass 1 | Pass 2 | Pass 3 |\n")
                f.write("|--------|---------|---------|--------|--------|--------|\n")
                for r in results:
                    f.write(
                        f"| {r['job_id']} | {r['company_name'][:20]} | "
                        f"{r['overall_consensus']*100:.1f}% | "
                        f"{r['pass1_consensus']*100:.1f}% | "
                        f"{r['pass2_consensus']*100:.1f}% | "
                        f"{r['pass3_consensus']*100:.1f}% |\n"
                    )
            print(f"\nSummary saved to: {summary_file}", file=sys.stderr)

    else:
        # Single job evaluation
        result = evaluate_single_job(
            args.job_id,
            args.base_path,
            args.output,
            args.format
        )

        if result:
            # Print summary to stderr
            print(f"\n--- Summary ---", file=sys.stderr)
            print(f"Job: {result['job_title']} @ {result['company_name']}", file=sys.stderr)
            print(f"Fields evaluated: {result['fields_evaluated']}", file=sys.stderr)
            print(f"Overall consensus: {result['overall_consensus']*100:.1f}%", file=sys.stderr)
            print(f"  Pass 1: {result['pass1_consensus']*100:.1f}%", file=sys.stderr)
            print(f"  Pass 2: {result['pass2_consensus']*100:.1f}%", file=sys.stderr)
            print(f"  Pass 3: {result['pass3_consensus']*100:.1f}%", file=sys.stderr)

            if result['high_disagreement_count'] > 0:
                print(f"\nHigh disagreement fields: {result['high_disagreement_count']}", file=sys.stderr)


if __name__ == "__main__":
    main()
