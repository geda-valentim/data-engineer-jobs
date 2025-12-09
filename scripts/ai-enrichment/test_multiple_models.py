"""
Multiple models comparison tests.
Contains functions for testing and comparing results across different LLM models.
"""

import os
import traceback
from typing import Optional, List

# Import test functions
from test_pass1 import test_multiple_jobs_comparison
from test_pass2 import test_pass2_inference
from test_pass3 import test_pass3_analysis
from test_execution_helpers import AVAILABLE_MODELS
from test_enrichment_helpers import load_jobs_from_s3, save_job_original


def test_multiple_models(
    use_s3: bool = False,
    date: Optional[str] = None,
    limit: int = 5,
    save_json: bool = True,
    models: Optional[List[str]] = None,
    pass_type: str = "pass1",
    use_cache: bool = False
):
    """
    Test extraction/inference across multiple models and compare results.
    Reuses existing test functions by temporarily overriding env vars.

    Args:
        use_s3: Use jobs from S3 bucket
        date: Partition date (YYYY-MM-DD)
        limit: Number of jobs to process
        save_json: Save results to data/local/{job_id}/{pass}-{model}.json
        models: List of model keys to test (default: all available)
        pass_type: Which pass to test (pass1, pass2, pass3)
        use_cache: Enable caching of results
    """
    print("\n" + "=" * 120)
    print(f"Testing Multiple Models - {pass_type.upper()}")
    print("=" * 120)

    # Determine which models to test
    if models:
        test_models = {k: v for k, v in AVAILABLE_MODELS.items() if k in models}
        invalid = [m for m in models if m not in AVAILABLE_MODELS]
        if invalid:
            print(f"Warning: Unknown models ignored: {invalid}")
    else:
        test_models = AVAILABLE_MODELS

    if not test_models:
        print("Error: No valid models to test")
        print(f"Available models: {list(AVAILABLE_MODELS.keys())}")
        return False

    print(f"\nModels to test ({len(test_models)}):")
    for key, model in test_models.items():
        print(f"  • {key}: {model['name']} ({model['id']})")
        print(f"    Cost: ${model['input_cost_per_1m']}/1M input, ${model['output_cost_per_1m']}/1M output")

    # Pre-load jobs from S3 ONCE (optimization to avoid repeated S3 calls)
    preloaded_jobs = None
    preloaded_partition_info = None
    if use_s3:
        print(f"\n{'=' * 120}")
        print("PRE-LOADING JOBS FROM S3 (once for all models)")
        print(f"{'=' * 120}")
        if date:
            print(f"  Date filter: {date}")
        else:
            print(f"  Using most recent partition(s)")
        print(f"  Requested limit: {limit} jobs")

        preloaded_jobs, preloaded_partition_info = load_jobs_from_s3(date_str=date, limit=limit)

        # Save original job data for all pre-loaded jobs
        print(f"\nSaving original job data to bronze layer...")
        for job in preloaded_jobs:
            save_job_original(job)
        print(f"  ✓ Saved {len(preloaded_jobs)} original job files")

    # Save original env vars
    original_pass1 = os.getenv("BEDROCK_MODEL_PASS1")
    original_pass2 = os.getenv("BEDROCK_MODEL_PASS2")
    original_pass3 = os.getenv("BEDROCK_MODEL_PASS3")

    model_results = {}

    try:
        # Run test for each model
        for model_key, model_config in test_models.items():
            model_id = model_config['id']
            model_name = model_config['name']

            print(f"\n{'=' * 120}")
            print(f"MODEL: {model_name} ({model_id})")
            print(f"{'=' * 120}")

            # Override env vars for this model
            os.environ["BEDROCK_MODEL_PASS1"] = model_id
            os.environ["BEDROCK_MODEL_PASS2"] = model_id
            os.environ["BEDROCK_MODEL_PASS3"] = model_id

            # Call existing test function based on pass_type
            # Pass pre-loaded jobs to avoid repeated S3 calls
            try:
                if pass_type == "pass1":
                    success = test_multiple_jobs_comparison(
                        use_s3=use_s3,
                        date=date,
                        limit=limit,
                        use_cache=use_cache,
                        save_json=save_json,
                        preloaded_jobs=preloaded_jobs,
                        preloaded_partition_info=preloaded_partition_info
                    )
                elif pass_type == "pass2":
                    success = test_pass2_inference(
                        use_s3=use_s3,
                        date=date,
                        limit=limit,
                        use_cache=use_cache,
                        save_json=save_json,
                        preloaded_jobs=preloaded_jobs,
                        preloaded_partition_info=preloaded_partition_info
                    )
                elif pass_type == "pass3":
                    success = test_pass3_analysis(
                        use_s3=use_s3,
                        date=date,
                        limit=limit,
                        use_cache=use_cache,
                        save_json=save_json,
                        preloaded_jobs=preloaded_jobs,
                        preloaded_partition_info=preloaded_partition_info
                    )
                else:
                    print(f"Unknown pass type: {pass_type}")
                    success = False

                model_results[model_key] = {
                    "name": model_name,
                    "model_id": model_id,
                    "success": success,
                    "input_cost_per_1m": model_config['input_cost_per_1m'],
                    "output_cost_per_1m": model_config['output_cost_per_1m'],
                }

            except Exception as e:
                print(f"ERROR testing {model_name}: {e}")
                traceback.print_exc()
                model_results[model_key] = {
                    "name": model_name,
                    "model_id": model_id,
                    "success": False,
                    "error": str(e),
                }

    finally:
        # Restore original env vars
        if original_pass1:
            os.environ["BEDROCK_MODEL_PASS1"] = original_pass1
        elif "BEDROCK_MODEL_PASS1" in os.environ:
            del os.environ["BEDROCK_MODEL_PASS1"]

        if original_pass2:
            os.environ["BEDROCK_MODEL_PASS2"] = original_pass2
        elif "BEDROCK_MODEL_PASS2" in os.environ:
            del os.environ["BEDROCK_MODEL_PASS2"]

        if original_pass3:
            os.environ["BEDROCK_MODEL_PASS3"] = original_pass3
        elif "BEDROCK_MODEL_PASS3" in os.environ:
            del os.environ["BEDROCK_MODEL_PASS3"]

    # Print summary
    print(f"\n{'=' * 120}")
    print("MULTIPLE MODELS - FINAL SUMMARY")
    print(f"{'=' * 120}")

    print(f"\n{'Model':<30} | {'Status':<10} | {'Input $/1M':<12} | {'Output $/1M':<12}")
    print("-" * 70)

    for model_key, result in model_results.items():
        status = "✓ OK" if result.get('success') else "✗ FAIL"
        if 'error' in result:
            status = "✗ ERROR"
        input_cost = f"${result.get('input_cost_per_1m', 0):.2f}"
        output_cost = f"${result.get('output_cost_per_1m', 0):.2f}"
        print(f"{result['name'][:29]:<30} | {status:<10} | {input_cost:<12} | {output_cost:<12}")

    print(f"\nResults saved to: data/local/{{job_id}}/{pass_type}-{{model}}.json")
    print("Compare results by inspecting the JSON files for each model.")

    return all(r.get('success', False) for r in model_results.values())
