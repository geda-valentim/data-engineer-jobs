#!/usr/bin/env python3
"""
Analyze Pass 3 outputs to extract vocabulary patterns using TF-IDF.
Goal: Define controlled vocabulary for summary array fields.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# TF-IDF implementation without external dependencies
import math


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words, removing punctuation."""
    # Remove special chars, keep alphanumeric
    text = re.sub(r'[^\w\s-]', ' ', text.lower())
    # Split and filter short words
    words = [w.strip() for w in text.split() if len(w.strip()) > 2]
    return words


def compute_tfidf(documents: List[str]) -> Dict[str, float]:
    """
    Compute TF-IDF scores for terms across documents.
    Returns dict of term -> tfidf score (sum across docs).
    """
    if not documents:
        return {}

    # Tokenize all documents
    tokenized_docs = [tokenize(doc) for doc in documents]

    # Document frequency (how many docs contain each term)
    df = Counter()
    for tokens in tokenized_docs:
        unique_tokens = set(tokens)
        for token in unique_tokens:
            df[token] += 1

    n_docs = len(documents)

    # Compute TF-IDF for each term
    tfidf_scores = defaultdict(float)

    for tokens in tokenized_docs:
        tf = Counter(tokens)
        doc_len = len(tokens) if tokens else 1

        for term, count in tf.items():
            # TF: normalized by doc length
            tf_score = count / doc_len
            # IDF: log(N / df)
            idf_score = math.log(n_docs / df[term]) if df[term] > 0 else 0
            # Accumulate across documents
            tfidf_scores[term] += tf_score * idf_score

    return dict(tfidf_scores)


def extract_bigrams(text: str) -> List[str]:
    """Extract meaningful bigrams from text."""
    words = tokenize(text)
    bigrams = []
    for i in range(len(words) - 1):
        bigram = f"{words[i]}_{words[i+1]}"
        bigrams.append(bigram)
    return bigrams


def load_pass3_data(base_path: str = "data/local") -> Dict[str, List[str]]:
    """
    Load all Pass 3 outputs and extract summary array fields.
    Returns dict: field_name -> list of all values across all files.
    """
    base = Path(base_path)

    # Fields to analyze
    summary_arrays = [
        "strengths",
        "concerns",
        "best_fit_for",
        "red_flags_to_probe",
        "negotiation_leverage"
    ]

    # Also capture analysis inference arrays
    analysis_arrays = [
        ("company_maturity", "maturity_signals"),
        ("tech_culture_assessment", "tech_culture_signals"),
        ("tech_culture_assessment", "dev_practices_mentioned"),
        ("ai_ml_integration", "ml_tools_expected"),
    ]

    data: Dict[str, List[str]] = defaultdict(list)

    # Find all pass3 files
    for job_dir in base.iterdir():
        if not job_dir.is_dir():
            continue

        for pass3_file in job_dir.glob("pass3-*.json"):
            try:
                with open(pass3_file) as f:
                    content = json.load(f)

                result = content.get("result", {})
                summary = result.get("summary", {})
                analysis = result.get("analysis", {})

                # Extract summary arrays
                for field in summary_arrays:
                    values = summary.get(field, [])
                    if isinstance(values, list):
                        for v in values:
                            if isinstance(v, str) and v.strip():
                                data[f"summary.{field}"].append(v.strip())

                # Extract analysis arrays (from inference objects)
                for group, field in analysis_arrays:
                    group_data = analysis.get(group, {})
                    field_data = group_data.get(field, {})

                    # Handle inference object format
                    if isinstance(field_data, dict):
                        values = field_data.get("value", [])
                    else:
                        values = field_data

                    if isinstance(values, list):
                        for v in values:
                            if isinstance(v, str) and v.strip():
                                data[f"analysis.{group}.{field}"].append(v.strip())

            except Exception as e:
                print(f"Error loading {pass3_file}: {e}")

    return dict(data)


def analyze_field_vocabulary(field_name: str, values: List[str]) -> Dict:
    """
    Analyze vocabulary for a single field using TF-IDF.
    """
    # Raw frequency
    raw_freq = Counter(values)

    # TF-IDF on individual entries (each entry is a "document")
    tfidf_scores = compute_tfidf(values)

    # Also compute bigram frequencies
    all_bigrams = []
    for v in values:
        all_bigrams.extend(extract_bigrams(v))
    bigram_freq = Counter(all_bigrams)

    # Extract key concepts (high TF-IDF terms)
    top_terms = sorted(tfidf_scores.items(), key=lambda x: -x[1])[:30]

    # Extract common bigrams
    top_bigrams = bigram_freq.most_common(20)

    return {
        "total_entries": len(values),
        "unique_entries": len(set(values)),
        "top_tfidf_terms": top_terms,
        "top_bigrams": top_bigrams,
        "most_common_exact": raw_freq.most_common(10),
    }


def suggest_vocabulary(field_name: str, analysis: Dict) -> List[str]:
    """
    Suggest controlled vocabulary based on TF-IDF analysis.
    Groups similar concepts into categories.
    """
    terms = [t for t, _ in analysis["top_tfidf_terms"]]
    bigrams = [b for b, _ in analysis["top_bigrams"]]

    # Define category patterns based on observed data
    categories = {
        # Strengths/positive patterns
        "competitive_compensation": ["salary", "compensation", "pay", "bonus", "equity", "stock"],
        "modern_tech_stack": ["modern", "stack", "cloud", "aws", "gcp", "azure", "kubernetes", "docker"],
        "work_flexibility": ["remote", "hybrid", "flexible", "wfh", "work-life", "balance"],
        "career_growth": ["growth", "career", "advancement", "promotion", "learning", "development"],
        "clear_requirements": ["clear", "defined", "specific", "detailed", "requirements"],
        "benefits_package": ["benefits", "health", "insurance", "401k", "pto", "vacation"],
        "team_culture": ["team", "culture", "collaborative", "inclusive", "diverse"],
        "data_engineering_focus": ["data", "pipeline", "etl", "warehouse", "lake", "engineering"],
        "established_company": ["established", "stable", "enterprise", "fortune"],
        "startup_growth": ["startup", "growth", "fast-paced", "scaling"],

        # Concerns/negative patterns
        "unclear_requirements": ["vague", "unclear", "ambiguous", "generic", "broad"],
        "no_salary_info": ["salary", "undisclosed", "not_disclosed", "compensation_unclear"],
        "visa_restrictions": ["visa", "sponsorship", "authorization", "h1b", "citizenship"],
        "on_call_expectations": ["on-call", "oncall", "24/7", "pager", "weekend"],
        "scope_creep_risk": ["scope", "creep", "wear_many_hats", "jack_of_all"],
        "legacy_tech": ["legacy", "outdated", "old", "maintenance", "migration"],
        "high_turnover_signals": ["backfill", "immediate", "urgent", "asap"],
        "reporting_unclear": ["reporting", "manager", "structure", "hierarchy"],
        "overtime_risk": ["overtime", "long_hours", "demanding", "fast-paced"],
        "travel_requirements": ["travel", "onsite", "relocation", "commute"],

        # Best fit patterns
        "senior_engineers": ["senior", "experienced", "5+", "years", "expert"],
        "cloud_specialists": ["cloud", "aws", "gcp", "azure", "infrastructure"],
        "data_platform_builders": ["platform", "architecture", "design", "build"],
        "pipeline_developers": ["pipeline", "etl", "elt", "orchestration", "airflow"],
        "analytics_engineers": ["analytics", "dbt", "sql", "modeling", "warehouse"],

        # Red flags to probe
        "ask_about_team": ["team", "size", "structure", "composition", "growth"],
        "ask_about_tech_stack": ["stack", "tools", "technologies", "architecture"],
        "ask_about_work_hours": ["hours", "on-call", "overtime", "expectations"],
        "ask_about_career_path": ["career", "growth", "promotion", "ladder"],
        "ask_about_remote": ["remote", "hybrid", "office", "location", "flexibility"],

        # Negotiation leverage
        "rare_skills": ["specialized", "rare", "niche", "expertise", "specific"],
        "multiple_offers": ["competitive", "market", "demand", "offers"],
        "experience_match": ["experience", "background", "match", "fit", "qualifications"],
    }

    # Match terms to categories
    matched_categories = set()
    for term in terms + bigrams:
        term_lower = term.lower().replace("_", " ")
        for cat, keywords in categories.items():
            if any(kw in term_lower for kw in keywords):
                matched_categories.add(cat)

    return sorted(matched_categories)


def main():
    print("=" * 70)
    print("PASS 3 VOCABULARY ANALYSIS")
    print("=" * 70)

    # Load data
    print("\nLoading Pass 3 data...")
    data = load_pass3_data()

    print(f"\nFound {len(data)} fields to analyze")

    results = {}

    for field_name, values in sorted(data.items()):
        print(f"\n{'='*70}")
        print(f"FIELD: {field_name}")
        print(f"{'='*70}")

        analysis = analyze_field_vocabulary(field_name, values)
        results[field_name] = analysis

        print(f"Total entries: {analysis['total_entries']}")
        print(f"Unique entries: {analysis['unique_entries']}")
        print(f"Uniqueness ratio: {analysis['unique_entries']/analysis['total_entries']:.1%}")

        print(f"\nTop TF-IDF Terms:")
        for term, score in analysis["top_tfidf_terms"][:15]:
            print(f"  {score:6.3f}  {term}")

        print(f"\nTop Bigrams:")
        for bigram, count in analysis["top_bigrams"][:10]:
            print(f"  {count:4d}  {bigram}")

        print(f"\nMost Common Exact Matches:")
        for entry, count in analysis["most_common_exact"][:5]:
            truncated = entry[:60] + "..." if len(entry) > 60 else entry
            print(f"  {count:4d}  {truncated}")

        # Suggest vocabulary
        suggestions = suggest_vocabulary(field_name, analysis)
        if suggestions:
            print(f"\nSuggested Categories ({len(suggestions)}):")
            for cat in suggestions[:10]:
                print(f"  - {cat}")

    # Generate vocabulary recommendation
    print("\n" + "=" * 70)
    print("VOCABULARY RECOMMENDATIONS")
    print("=" * 70)

    generate_vocabulary_recommendations(results)


def generate_vocabulary_recommendations(results: Dict):
    """Generate final vocabulary recommendations for schema update."""

    # Define recommended enums based on analysis
    recommendations = {
        "summary.strengths": {
            "enum_name": "StrengthCategory",
            "values": [
                "competitive_compensation",
                "transparent_salary",
                "equity_offered",
                "modern_tech_stack",
                "cloud_native",
                "remote_friendly",
                "hybrid_work",
                "flexible_schedule",
                "career_growth_clear",
                "learning_opportunities",
                "clear_requirements",
                "well_defined_role",
                "strong_benefits",
                "work_life_balance",
                "collaborative_culture",
                "diverse_team",
                "data_focused_role",
                "established_company",
                "startup_energy",
                "visa_sponsorship",
            ]
        },
        "summary.concerns": {
            "enum_name": "ConcernCategory",
            "values": [
                "vague_requirements",
                "unclear_responsibilities",
                "salary_not_disclosed",
                "below_market_pay",
                "no_visa_sponsorship",
                "citizenship_required",
                "on_call_expected",
                "overtime_likely",
                "scope_creep_risk",
                "jack_of_all_trades",
                "legacy_technology",
                "tech_debt_heavy",
                "high_turnover_signals",
                "backfill_role",
                "unclear_reporting",
                "travel_required",
                "relocation_required",
                "limited_growth",
                "startup_risk",
                "contract_short_term",
            ]
        },
        "summary.best_fit_for": {
            "enum_name": "CandidateProfile",
            "values": [
                "senior_data_engineers",
                "mid_level_engineers",
                "junior_engineers",
                "cloud_specialists",
                "platform_architects",
                "pipeline_developers",
                "analytics_engineers",
                "ml_engineers",
                "data_generalists",
                "startup_enthusiasts",
                "enterprise_experienced",
                "remote_workers",
                "career_changers",
                "leadership_track",
                "technical_specialists",
            ]
        },
        "summary.red_flags_to_probe": {
            "enum_name": "ProbeQuestion",
            "values": [
                "team_size_composition",
                "reporting_structure",
                "tech_stack_details",
                "on_call_expectations",
                "work_hour_expectations",
                "remote_policy_details",
                "career_growth_path",
                "salary_range_details",
                "visa_sponsorship_details",
                "role_scope_boundaries",
                "tech_debt_situation",
                "team_turnover_history",
                "company_financials",
                "project_timeline",
                "success_metrics",
            ]
        },
        "summary.negotiation_leverage": {
            "enum_name": "NegotiationLeverage",
            "values": [
                "rare_skill_match",
                "exact_experience_match",
                "exceeds_requirements",
                "multiple_competing_offers",
                "high_market_demand",
                "domain_expertise",
                "leadership_experience",
                "quick_availability",
                "local_candidate",
                "referral_connection",
            ]
        }
    }

    for field, rec in recommendations.items():
        print(f"\n{field}:")
        print(f"  Enum: {rec['enum_name']}")
        print(f"  Values ({len(rec['values'])}):")
        for v in rec['values']:
            print(f"    - {v}")

    # Save recommendations to JSON
    output_path = Path("data/vocabulary_recommendations.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(recommendations, f, indent=2)

    print(f"\n\nRecommendations saved to: {output_path}")


if __name__ == "__main__":
    main()
