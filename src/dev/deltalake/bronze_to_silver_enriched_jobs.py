from pathlib import Path

from pyspark.sql.functions import (
    input_file_name,
    regexp_extract,
    col,
    to_json,
    lit,
    get_json_object,
    when,
    coalesce,
)
from src.dev.deltalake.spark_session import get_spark


# Paths (relativos ao projeto)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # src/dev/deltalake -> raiz
BASE_DIR = PROJECT_ROOT / "data" / "local" / "ai_enrichment"
BRONZE_DIR = BASE_DIR / "bronze"
DELTA_SILVER_PATH = BASE_DIR / "silver" / "delta" / "enriched_jobs"

# Colunas comuns para o UNION
COLUMNS = [
    "job_id", "job_title", "company_name", "job_location",
    "model_name", "pass_num", "source_file",
    "tokens", "cost",
    # Pass1 - Compensation
    "salary_disclosed", "salary_min", "salary_max", "salary_currency",
    "salary_period", "salary_text_raw",
    # Pass1 - Work Authorization
    "visa_sponsorship", "security_clearance",
    # Pass1 - Work Model
    "work_model", "employment_type", "location_restriction_text",
    # Pass1 - Contract
    "contract_type",
    # Pass1 - Skills
    "must_have_skills_json", "nice_to_have_skills_json",
    # Pass1 - Experience
    "years_experience_min", "years_experience_max", "years_experience_text",
    # Pass1 - Education
    "education_level", "education_area", "education_requirement",
    # Pass1 - Geo Restrictions
    "geo_restriction_type", "allowed_countries_json", "us_state_restrictions_json",
    # Pass1 - Benefits
    "equity_mentioned", "learning_budget_mentioned", "pto_policy",
    "benefits_json",
    # Pass1 - Context
    "team_info_text", "company_description_text",
    # Pass2 - Seniority and Role
    "seniority_level", "job_family", "sub_specialty", "leadership_expectation",
    # Pass2 - Stack and Cloud
    "primary_cloud", "secondary_clouds_json", "processing_paradigm",
    "orchestrator_category", "storage_layer",
    # Pass2 - Geo and Work Model
    "remote_restriction", "timezone_focus", "relocation_required",
    # Pass2 - Visa and Authorization
    "h1b_friendly", "opt_cpt_friendly", "citizenship_required",
    # Pass2 - Contract and Compensation
    "w2_vs_1099", "benefits_level",
    # Pass2 - Career Development
    "growth_path_clarity", "mentorship_signals", "promotion_path_mentioned",
    "internal_mobility_mentioned", "career_tracks_json",
    # Pass2 - Requirements Classification
    "requirement_strictness", "scope_definition", "skill_inflation_detected",
    # Pass3 - Company Maturity
    "data_maturity_score", "data_maturity_level", "maturity_signals_json",
    # Pass3 - Red Flags and Role Quality
    "scope_creep_score", "overtime_risk_score", "overall_red_flag_score", "role_clarity",
    # Pass3 - Stakeholders and Leadership
    "reporting_structure_clarity", "manager_level_inferred", "team_growth_velocity",
    "cross_functional_embedded",
    # Pass3 - Tech Culture
    "work_life_balance_score", "growth_opportunities_score", "tech_culture_score",
    # Pass3 - Tech Culture Assessment
    "tech_culture_signals_json", "dev_practices_json", "innovation_signals", "tech_debt_awareness",
    # Pass3 - AI/ML Integration
    "ai_integration_level", "ml_tools_json",
    # Pass3 - Competition and Timing
    "hiring_urgency", "competition_level",
    # Pass3 - Company Context
    "company_stage_inferred", "hiring_velocity", "role_creation_type",
    # Pass3 - Summary
    "recommendation_score", "recommendation_confidence", "overall_assessment",
    "strength_categories_json", "concern_categories_json",
    "best_fit_categories_json", "probe_categories_json", "leverage_categories_json",
    # Raw
    "result_json"
]


def run_bronze_to_silver_enriched_jobs():
    spark = get_spark("BronzeToSilverEnrichedJobs")

    # === PASS 1: Extração ===
    pass1_pattern = str(BRONZE_DIR / "*" / "pass1-*.json")
    print(f"Lendo Pass1: {pass1_pattern}")

    df1 = spark.read.option("multiLine", True).json(pass1_pattern)
    df1 = (df1
        .withColumn("source_file", input_file_name())
        .withColumn("job_id", regexp_extract(col("source_file"), r"/bronze/([^/]+)/", 1).cast("long"))
        .withColumn("model_name", regexp_extract(col("source_file"), r"pass[0-9]+-(.*?)\.json", 1))
        .withColumn("pass_num", lit(1))
        # Metadata
        .withColumn("job_title", col("metadata.job_title"))
        .withColumn("company_name", col("metadata.company_name"))
        .withColumn("job_location", col("metadata.job_location"))
        # Tokens (pass1 usa total_tokens_used, não tem result.tokens)
        .withColumn("tokens", col("result.total_tokens_used").cast("int"))
        .withColumn("cost", col("result.enrichment_cost_usd"))
        # Pass1 - Compensation
        .withColumn("salary_disclosed", col("result.ext_salary_disclosed"))
        .withColumn("salary_min", col("result.ext_salary_min"))
        .withColumn("salary_max", col("result.ext_salary_max"))
        .withColumn("salary_currency", col("result.ext_salary_currency"))
        .withColumn("salary_period", col("result.ext_salary_period"))
        .withColumn("salary_text_raw", col("result.ext_salary_text_raw"))
        # Pass1 - Work Authorization
        .withColumn("visa_sponsorship", col("result.ext_visa_sponsorship_stated"))
        .withColumn("security_clearance", col("result.ext_security_clearance_stated"))
        # Pass1 - Work Model
        .withColumn("work_model", col("result.ext_work_model_stated"))
        .withColumn("employment_type", col("result.ext_employment_type_stated"))
        .withColumn("location_restriction_text", col("result.ext_location_restriction_text"))
        # Pass1 - Contract
        .withColumn("contract_type", col("result.ext_contract_type"))
        # Pass1 - Skills
        .withColumn("must_have_skills_json", to_json(col("result.ext_must_have_hard_skills")))
        .withColumn("nice_to_have_skills_json", to_json(col("result.ext_nice_to_have_hard_skills")))
        # Pass1 - Experience
        .withColumn("years_experience_min", col("result.ext_years_experience_min"))
        .withColumn("years_experience_max", col("result.ext_years_experience_max"))
        .withColumn("years_experience_text", col("result.ext_years_experience_text"))
        # Pass1 - Education
        .withColumn("education_level", col("result.ext_education_level"))
        .withColumn("education_area", col("result.ext_education_area"))
        .withColumn("education_requirement", col("result.ext_education_requirement"))
        # Pass1 - Geo Restrictions
        .withColumn("geo_restriction_type", col("result.ext_geo_restriction_type"))
        .withColumn("allowed_countries_json", to_json(col("result.ext_allowed_countries")))
        .withColumn("us_state_restrictions_json", to_json(col("result.ext_us_state_restrictions")))
        # Pass1 - Benefits
        .withColumn("equity_mentioned", col("result.ext_equity_mentioned"))
        .withColumn("learning_budget_mentioned", col("result.ext_learning_budget_mentioned"))
        .withColumn("pto_policy", col("result.ext_pto_policy"))
        .withColumn("benefits_json", to_json(col("result.ext_benefits_mentioned")))
        # Pass1 - Context
        .withColumn("team_info_text", col("result.ext_team_info_text"))
        .withColumn("company_description_text", col("result.ext_company_description_text"))
        # Pass2 específicos (null para pass1)
        # Seniority and Role
        .withColumn("seniority_level", lit(None).cast("string"))
        .withColumn("job_family", lit(None).cast("string"))
        .withColumn("sub_specialty", lit(None).cast("string"))
        .withColumn("leadership_expectation", lit(None).cast("string"))
        # Stack and Cloud
        .withColumn("primary_cloud", lit(None).cast("string"))
        .withColumn("secondary_clouds_json", lit(None).cast("string"))
        .withColumn("processing_paradigm", lit(None).cast("string"))
        .withColumn("orchestrator_category", lit(None).cast("string"))
        .withColumn("storage_layer", lit(None).cast("string"))
        # Geo and Work Model
        .withColumn("remote_restriction", lit(None).cast("string"))
        .withColumn("timezone_focus", lit(None).cast("string"))
        .withColumn("relocation_required", lit(None).cast("boolean"))
        # Visa and Authorization
        .withColumn("h1b_friendly", lit(None).cast("boolean"))
        .withColumn("opt_cpt_friendly", lit(None).cast("boolean"))
        .withColumn("citizenship_required", lit(None).cast("string"))
        # Contract and Compensation
        .withColumn("w2_vs_1099", lit(None).cast("string"))
        .withColumn("benefits_level", lit(None).cast("string"))
        # Career Development
        .withColumn("growth_path_clarity", lit(None).cast("string"))
        .withColumn("mentorship_signals", lit(None).cast("string"))
        .withColumn("promotion_path_mentioned", lit(None).cast("boolean"))
        .withColumn("internal_mobility_mentioned", lit(None).cast("boolean"))
        .withColumn("career_tracks_json", lit(None).cast("string"))
        # Requirements Classification
        .withColumn("requirement_strictness", lit(None).cast("string"))
        .withColumn("scope_definition", lit(None).cast("string"))
        .withColumn("skill_inflation_detected", lit(None).cast("boolean"))
        # Pass3 específicos (null para pass1)
        # Company Maturity
        .withColumn("data_maturity_score", lit(None).cast("double"))
        .withColumn("data_maturity_level", lit(None).cast("string"))
        .withColumn("maturity_signals_json", lit(None).cast("string"))
        # Red Flags and Role Quality
        .withColumn("scope_creep_score", lit(None).cast("double"))
        .withColumn("overtime_risk_score", lit(None).cast("double"))
        .withColumn("overall_red_flag_score", lit(None).cast("double"))
        .withColumn("role_clarity", lit(None).cast("string"))
        # Stakeholders and Leadership
        .withColumn("reporting_structure_clarity", lit(None).cast("string"))
        .withColumn("manager_level_inferred", lit(None).cast("string"))
        .withColumn("team_growth_velocity", lit(None).cast("string"))
        .withColumn("cross_functional_embedded", lit(None).cast("boolean"))
        # Tech Culture
        .withColumn("work_life_balance_score", lit(None).cast("double"))
        .withColumn("growth_opportunities_score", lit(None).cast("double"))
        .withColumn("tech_culture_score", lit(None).cast("double"))
        # Tech Culture Assessment
        .withColumn("tech_culture_signals_json", lit(None).cast("string"))
        .withColumn("dev_practices_json", lit(None).cast("string"))
        .withColumn("innovation_signals", lit(None).cast("string"))
        .withColumn("tech_debt_awareness", lit(None).cast("boolean"))
        # AI/ML Integration
        .withColumn("ai_integration_level", lit(None).cast("string"))
        .withColumn("ml_tools_json", lit(None).cast("string"))
        # Competition and Timing
        .withColumn("hiring_urgency", lit(None).cast("string"))
        .withColumn("competition_level", lit(None).cast("string"))
        # Company Context
        .withColumn("company_stage_inferred", lit(None).cast("string"))
        .withColumn("hiring_velocity", lit(None).cast("string"))
        .withColumn("role_creation_type", lit(None).cast("string"))
        # Summary
        .withColumn("recommendation_score", lit(None).cast("double"))
        .withColumn("recommendation_confidence", lit(None).cast("double"))
        .withColumn("overall_assessment", lit(None).cast("string"))
        .withColumn("strength_categories_json", lit(None).cast("string"))
        .withColumn("concern_categories_json", lit(None).cast("string"))
        .withColumn("best_fit_categories_json", lit(None).cast("string"))
        .withColumn("probe_categories_json", lit(None).cast("string"))
        .withColumn("leverage_categories_json", lit(None).cast("string"))
        # Raw
        .withColumn("result_json", to_json(col("result")))
    )

    # === PASS 2: Inferências ===
    pass2_pattern = str(BRONZE_DIR / "*" / "pass2-*.json")
    print(f"Lendo Pass2: {pass2_pattern}")

    df2 = spark.read.option("multiLine", True).json(pass2_pattern)
    df2 = (df2
        .withColumn("source_file", input_file_name())
        .withColumn("job_id", regexp_extract(col("source_file"), r"/bronze/([^/]+)/", 1).cast("long"))
        .withColumn("model_name", regexp_extract(col("source_file"), r"pass[0-9]+-(.*?)\.json", 1))
        .withColumn("pass_num", lit(2))
        # Metadata
        .withColumn("job_title", col("metadata.job_title"))
        .withColumn("company_name", col("metadata.company_name"))
        .withColumn("job_location", col("metadata.job_location"))
        # Tokens (pass2 usa result.tokens)
        .withColumn("tokens", col("result.tokens").cast("int"))
        .withColumn("cost", col("result.cost"))
        # Pass1 específicos (null)
        .withColumn("salary_disclosed", lit(None).cast("boolean"))
        .withColumn("salary_min", lit(None).cast("double"))
        .withColumn("salary_max", lit(None).cast("double"))
        .withColumn("salary_currency", lit(None).cast("string"))
        .withColumn("salary_period", lit(None).cast("string"))
        .withColumn("salary_text_raw", lit(None).cast("string"))
        .withColumn("visa_sponsorship", lit(None).cast("string"))
        .withColumn("security_clearance", lit(None).cast("string"))
        .withColumn("work_model", lit(None).cast("string"))
        .withColumn("employment_type", lit(None).cast("string"))
        .withColumn("location_restriction_text", lit(None).cast("string"))
        .withColumn("contract_type", lit(None).cast("string"))
        .withColumn("must_have_skills_json", lit(None).cast("string"))
        .withColumn("nice_to_have_skills_json", lit(None).cast("string"))
        .withColumn("years_experience_min", lit(None).cast("double"))
        .withColumn("years_experience_max", lit(None).cast("double"))
        .withColumn("years_experience_text", lit(None).cast("string"))
        .withColumn("education_level", lit(None).cast("string"))
        .withColumn("education_area", lit(None).cast("string"))
        .withColumn("education_requirement", lit(None).cast("string"))
        .withColumn("geo_restriction_type", lit(None).cast("string"))
        .withColumn("allowed_countries_json", lit(None).cast("string"))
        .withColumn("us_state_restrictions_json", lit(None).cast("string"))
        .withColumn("equity_mentioned", lit(None).cast("boolean"))
        .withColumn("learning_budget_mentioned", lit(None).cast("boolean"))
        .withColumn("pto_policy", lit(None).cast("string"))
        .withColumn("benefits_json", lit(None).cast("string"))
        .withColumn("team_info_text", lit(None).cast("string"))
        .withColumn("company_description_text", lit(None).cast("string"))
        # Pass2 - Seniority and Role
        .withColumn("seniority_level", col("result.inference.seniority_and_role.seniority_level.value"))
        .withColumn("job_family", col("result.inference.seniority_and_role.job_family.value"))
        .withColumn("sub_specialty", col("result.inference.seniority_and_role.sub_specialty.value"))
        .withColumn("leadership_expectation", col("result.inference.seniority_and_role.leadership_expectation.value"))
        # Pass2 - Stack and Cloud
        .withColumn("primary_cloud", col("result.inference.stack_and_cloud.primary_cloud.value"))
        .withColumn("secondary_clouds_json", to_json(col("result.inference.stack_and_cloud.secondary_clouds.value")))
        .withColumn("processing_paradigm", col("result.inference.stack_and_cloud.processing_paradigm.value"))
        .withColumn("orchestrator_category", col("result.inference.stack_and_cloud.orchestrator_category.value"))
        .withColumn("storage_layer", col("result.inference.stack_and_cloud.storage_layer.value"))
        # Pass2 - Geo and Work Model
        .withColumn("remote_restriction", col("result.inference.geo_and_work_model.remote_restriction.value"))
        .withColumn("timezone_focus", col("result.inference.geo_and_work_model.timezone_focus.value"))
        # relocation_required pode ser boolean ou string
        .withColumn("_reloc_str", col("result.inference.geo_and_work_model.relocation_required.value").cast("string"))
        .withColumn("relocation_required",
            when(col("_reloc_str") == "true", lit(True))
            .when(col("_reloc_str") == "false", lit(False))
            .otherwise(lit(None).cast("boolean"))
        )
        .drop("_reloc_str")
        # Pass2 - Visa and Authorization
        # h1b_friendly pode ser boolean (true/false) ou string ("not_mentioned", etc)
        .withColumn("_h1b_str", col("result.inference.visa_and_authorization.h1b_friendly.value").cast("string"))
        .withColumn("h1b_friendly",
            when(col("_h1b_str") == "true", lit(True))
            .when(col("_h1b_str") == "false", lit(False))
            .otherwise(lit(None).cast("boolean"))
        )
        .drop("_h1b_str")
        # opt_cpt_friendly também pode ser boolean ou string
        .withColumn("_opt_str", col("result.inference.visa_and_authorization.opt_cpt_friendly.value").cast("string"))
        .withColumn("opt_cpt_friendly",
            when(col("_opt_str") == "true", lit(True))
            .when(col("_opt_str") == "false", lit(False))
            .otherwise(lit(None).cast("boolean"))
        )
        .drop("_opt_str")
        .withColumn("citizenship_required", col("result.inference.visa_and_authorization.citizenship_required.value"))
        # Pass2 - Contract and Compensation
        .withColumn("w2_vs_1099", col("result.inference.contract_and_compensation.w2_vs_1099.value"))
        .withColumn("benefits_level", col("result.inference.contract_and_compensation.benefits_level.value"))
        # Pass2 - Career Development
        .withColumn("growth_path_clarity", col("result.inference.career_development.growth_path_clarity.value"))
        .withColumn("mentorship_signals", col("result.inference.career_development.mentorship_signals.value"))
        # promotion_path_mentioned pode ser boolean ou string
        .withColumn("_promo_str", col("result.inference.career_development.promotion_path_mentioned.value").cast("string"))
        .withColumn("promotion_path_mentioned",
            when(col("_promo_str") == "true", lit(True))
            .when(col("_promo_str") == "false", lit(False))
            .otherwise(lit(None).cast("boolean"))
        )
        .drop("_promo_str")
        # internal_mobility_mentioned pode ser boolean ou string
        .withColumn("_mob_str", col("result.inference.career_development.internal_mobility_mentioned.value").cast("string"))
        .withColumn("internal_mobility_mentioned",
            when(col("_mob_str") == "true", lit(True))
            .when(col("_mob_str") == "false", lit(False))
            .otherwise(lit(None).cast("boolean"))
        )
        .drop("_mob_str")
        # career_tracks can be array or string depending on model
        .withColumn("career_tracks_json", col("result.inference.career_development.career_tracks_available.value").cast("string"))
        # Pass2 - Requirements Classification
        .withColumn("requirement_strictness", col("result.inference.requirements_classification.requirement_strictness.value"))
        .withColumn("scope_definition", col("result.inference.requirements_classification.scope_definition.value"))
        # skill_inflation_detected pode ser boolean ou string
        .withColumn("_skill_str", col("result.inference.requirements_classification.skill_inflation_detected.value").cast("string"))
        .withColumn("skill_inflation_detected",
            when(col("_skill_str") == "true", lit(True))
            .when(col("_skill_str") == "false", lit(False))
            .otherwise(lit(None).cast("boolean"))
        )
        .drop("_skill_str")
        # Pass3 específicos (null para pass2)
        # Company Maturity
        .withColumn("data_maturity_score", lit(None).cast("double"))
        .withColumn("data_maturity_level", lit(None).cast("string"))
        .withColumn("maturity_signals_json", lit(None).cast("string"))
        # Red Flags and Role Quality
        .withColumn("scope_creep_score", lit(None).cast("double"))
        .withColumn("overtime_risk_score", lit(None).cast("double"))
        .withColumn("overall_red_flag_score", lit(None).cast("double"))
        .withColumn("role_clarity", lit(None).cast("string"))
        # Stakeholders and Leadership
        .withColumn("reporting_structure_clarity", lit(None).cast("string"))
        .withColumn("manager_level_inferred", lit(None).cast("string"))
        .withColumn("team_growth_velocity", lit(None).cast("string"))
        .withColumn("cross_functional_embedded", lit(None).cast("boolean"))
        # Tech Culture
        .withColumn("work_life_balance_score", lit(None).cast("double"))
        .withColumn("growth_opportunities_score", lit(None).cast("double"))
        .withColumn("tech_culture_score", lit(None).cast("double"))
        # Tech Culture Assessment
        .withColumn("tech_culture_signals_json", lit(None).cast("string"))
        .withColumn("dev_practices_json", lit(None).cast("string"))
        .withColumn("innovation_signals", lit(None).cast("string"))
        .withColumn("tech_debt_awareness", lit(None).cast("boolean"))
        # AI/ML Integration
        .withColumn("ai_integration_level", lit(None).cast("string"))
        .withColumn("ml_tools_json", lit(None).cast("string"))
        # Competition and Timing
        .withColumn("hiring_urgency", lit(None).cast("string"))
        .withColumn("competition_level", lit(None).cast("string"))
        # Company Context
        .withColumn("company_stage_inferred", lit(None).cast("string"))
        .withColumn("hiring_velocity", lit(None).cast("string"))
        .withColumn("role_creation_type", lit(None).cast("string"))
        # Summary
        .withColumn("recommendation_score", lit(None).cast("double"))
        .withColumn("recommendation_confidence", lit(None).cast("double"))
        .withColumn("overall_assessment", lit(None).cast("string"))
        .withColumn("strength_categories_json", lit(None).cast("string"))
        .withColumn("concern_categories_json", lit(None).cast("string"))
        .withColumn("best_fit_categories_json", lit(None).cast("string"))
        .withColumn("probe_categories_json", lit(None).cast("string"))
        .withColumn("leverage_categories_json", lit(None).cast("string"))
        # Raw
        .withColumn("result_json", to_json(col("result")))
    )

    # === PASS 3: Análise ===
    pass3_pattern = str(BRONZE_DIR / "*" / "pass3-*.json")
    print(f"Lendo Pass3: {pass3_pattern}")

    df3 = spark.read.option("multiLine", True).json(pass3_pattern)
    df3 = (df3
        .withColumn("source_file", input_file_name())
        .withColumn("job_id", regexp_extract(col("source_file"), r"/bronze/([^/]+)/", 1).cast("long"))
        .withColumn("model_name", regexp_extract(col("source_file"), r"pass[0-9]+-(.*?)\.json", 1))
        .withColumn("pass_num", lit(3))
        # Metadata
        .withColumn("job_title", col("metadata.job_title"))
        .withColumn("company_name", col("metadata.company_name"))
        .withColumn("job_location", col("metadata.job_location"))
        # Tokens
        .withColumn("tokens", col("result.tokens").cast("int"))
        .withColumn("cost", col("result.cost"))
        # Pass1 específicos (null)
        .withColumn("salary_disclosed", lit(None).cast("boolean"))
        .withColumn("salary_min", lit(None).cast("double"))
        .withColumn("salary_max", lit(None).cast("double"))
        .withColumn("salary_currency", lit(None).cast("string"))
        .withColumn("salary_period", lit(None).cast("string"))
        .withColumn("salary_text_raw", lit(None).cast("string"))
        .withColumn("visa_sponsorship", lit(None).cast("string"))
        .withColumn("security_clearance", lit(None).cast("string"))
        .withColumn("work_model", lit(None).cast("string"))
        .withColumn("employment_type", lit(None).cast("string"))
        .withColumn("location_restriction_text", lit(None).cast("string"))
        .withColumn("contract_type", lit(None).cast("string"))
        .withColumn("must_have_skills_json", lit(None).cast("string"))
        .withColumn("nice_to_have_skills_json", lit(None).cast("string"))
        .withColumn("years_experience_min", lit(None).cast("double"))
        .withColumn("years_experience_max", lit(None).cast("double"))
        .withColumn("years_experience_text", lit(None).cast("string"))
        .withColumn("education_level", lit(None).cast("string"))
        .withColumn("education_area", lit(None).cast("string"))
        .withColumn("education_requirement", lit(None).cast("string"))
        .withColumn("geo_restriction_type", lit(None).cast("string"))
        .withColumn("allowed_countries_json", lit(None).cast("string"))
        .withColumn("us_state_restrictions_json", lit(None).cast("string"))
        .withColumn("equity_mentioned", lit(None).cast("boolean"))
        .withColumn("learning_budget_mentioned", lit(None).cast("boolean"))
        .withColumn("pto_policy", lit(None).cast("string"))
        .withColumn("benefits_json", lit(None).cast("string"))
        .withColumn("team_info_text", lit(None).cast("string"))
        .withColumn("company_description_text", lit(None).cast("string"))
        # Pass2 específicos (null)
        # Seniority and Role
        .withColumn("seniority_level", lit(None).cast("string"))
        .withColumn("job_family", lit(None).cast("string"))
        .withColumn("sub_specialty", lit(None).cast("string"))
        .withColumn("leadership_expectation", lit(None).cast("string"))
        # Stack and Cloud
        .withColumn("primary_cloud", lit(None).cast("string"))
        .withColumn("secondary_clouds_json", lit(None).cast("string"))
        .withColumn("processing_paradigm", lit(None).cast("string"))
        .withColumn("orchestrator_category", lit(None).cast("string"))
        .withColumn("storage_layer", lit(None).cast("string"))
        # Geo and Work Model
        .withColumn("remote_restriction", lit(None).cast("string"))
        .withColumn("timezone_focus", lit(None).cast("string"))
        .withColumn("relocation_required", lit(None).cast("boolean"))
        # Visa and Authorization
        .withColumn("h1b_friendly", lit(None).cast("boolean"))
        .withColumn("opt_cpt_friendly", lit(None).cast("boolean"))
        .withColumn("citizenship_required", lit(None).cast("string"))
        # Contract and Compensation
        .withColumn("w2_vs_1099", lit(None).cast("string"))
        .withColumn("benefits_level", lit(None).cast("string"))
        # Career Development
        .withColumn("growth_path_clarity", lit(None).cast("string"))
        .withColumn("mentorship_signals", lit(None).cast("string"))
        .withColumn("promotion_path_mentioned", lit(None).cast("boolean"))
        .withColumn("internal_mobility_mentioned", lit(None).cast("boolean"))
        .withColumn("career_tracks_json", lit(None).cast("string"))
        # Requirements Classification
        .withColumn("requirement_strictness", lit(None).cast("string"))
        .withColumn("scope_definition", lit(None).cast("string"))
        .withColumn("skill_inflation_detected", lit(None).cast("boolean"))
        # Pass3 específicos - Extract to JSON first to handle polymorphic types
        .withColumn("result_json", to_json(col("result")))
        # === Company Maturity ===
        .withColumn("_dm_raw", get_json_object(col("result_json"), "$.analysis.company_maturity.data_maturity_score.value"))
        .withColumn("data_maturity_score",
            when(col("_dm_raw").isNotNull(), col("_dm_raw").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("data_maturity_level", get_json_object(col("result_json"), "$.analysis.company_maturity.data_maturity_level.value"))
        .withColumn("maturity_signals_json", get_json_object(col("result_json"), "$.analysis.company_maturity.maturity_signals.value"))
        # === Red Flags and Role Quality ===
        .withColumn("_sc_raw", get_json_object(col("result_json"), "$.analysis.red_flags_and_role_quality.scope_creep_score.value"))
        .withColumn("scope_creep_score",
            when(col("_sc_raw").isNotNull(), col("_sc_raw").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("_or_raw", get_json_object(col("result_json"), "$.analysis.red_flags_and_role_quality.overtime_risk_score.value"))
        .withColumn("overtime_risk_score",
            when(col("_or_raw").isNotNull(), col("_or_raw").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("_orf_raw", get_json_object(col("result_json"), "$.analysis.red_flags_and_role_quality.overall_red_flag_score.value"))
        .withColumn("overall_red_flag_score",
            when(col("_orf_raw").isNotNull(), col("_orf_raw").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("role_clarity", get_json_object(col("result_json"), "$.analysis.red_flags_and_role_quality.role_clarity.value"))
        # === Stakeholders and Leadership ===
        .withColumn("reporting_structure_clarity", get_json_object(col("result_json"), "$.analysis.stakeholders_and_leadership.reporting_structure_clarity.value"))
        .withColumn("manager_level_inferred", get_json_object(col("result_json"), "$.analysis.stakeholders_and_leadership.manager_level_inferred.value"))
        .withColumn("team_growth_velocity", get_json_object(col("result_json"), "$.analysis.stakeholders_and_leadership.team_growth_velocity.value"))
        .withColumn("_cfe_str", get_json_object(col("result_json"), "$.analysis.stakeholders_and_leadership.cross_functional_embedded.value"))
        .withColumn("cross_functional_embedded",
            when(col("_cfe_str") == "true", lit(True))
            .when(col("_cfe_str") == "false", lit(False))
            .otherwise(lit(None).cast("boolean"))
        )
        # === Tech Culture ===
        .withColumn("_wlb_raw", get_json_object(col("result_json"), "$.analysis.tech_culture.work_life_balance_score.value"))
        .withColumn("work_life_balance_score",
            when(col("_wlb_raw").isNotNull(), col("_wlb_raw").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("_go_raw", get_json_object(col("result_json"), "$.analysis.tech_culture.growth_opportunities_score.value"))
        .withColumn("growth_opportunities_score",
            when(col("_go_raw").isNotNull(), col("_go_raw").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("_tc_raw", get_json_object(col("result_json"), "$.analysis.tech_culture.tech_culture_score.value"))
        .withColumn("tech_culture_score",
            when(col("_tc_raw").isNotNull(), col("_tc_raw").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        # === Tech Culture Assessment ===
        .withColumn("tech_culture_signals_json", get_json_object(col("result_json"), "$.analysis.tech_culture_assessment.tech_culture_signals.value"))
        .withColumn("dev_practices_json", get_json_object(col("result_json"), "$.analysis.tech_culture_assessment.dev_practices_mentioned.value"))
        .withColumn("innovation_signals", get_json_object(col("result_json"), "$.analysis.tech_culture_assessment.innovation_signals.value"))
        .withColumn("_tda_str", get_json_object(col("result_json"), "$.analysis.tech_culture_assessment.tech_debt_awareness.value"))
        .withColumn("tech_debt_awareness",
            when(col("_tda_str") == "true", lit(True))
            .when(col("_tda_str") == "false", lit(False))
            .otherwise(lit(None).cast("boolean"))
        )
        # === AI/ML Integration ===
        .withColumn("ai_integration_level", get_json_object(col("result_json"), "$.analysis.ai_ml_integration.ai_integration_level.value"))
        .withColumn("ml_tools_json", get_json_object(col("result_json"), "$.analysis.ai_ml_integration.ml_tools_expected.value"))
        # === Competition and Timing ===
        .withColumn("hiring_urgency", get_json_object(col("result_json"), "$.analysis.competition_and_timing.hiring_urgency.value"))
        .withColumn("competition_level", get_json_object(col("result_json"), "$.analysis.competition_and_timing.competition_level.value"))
        # === Company Context ===
        .withColumn("company_stage_inferred", get_json_object(col("result_json"), "$.analysis.company_context.company_stage_inferred.value"))
        .withColumn("hiring_velocity", get_json_object(col("result_json"), "$.analysis.company_context.hiring_velocity.value"))
        .withColumn("role_creation_type", get_json_object(col("result_json"), "$.analysis.company_context.role_creation_type.value"))
        # === Summary ===
        .withColumn("_rec_score_raw", get_json_object(col("result_json"), "$.summary.recommendation_score"))
        .withColumn("_rec_from_obj", regexp_extract(col("_rec_score_raw"), r'"value"\s*:\s*([0-9.]+)', 1))
        .withColumn("_rec_from_num", regexp_extract(col("_rec_score_raw"), r'^([0-9.]+)$', 1))
        .withColumn("recommendation_score",
            when(col("_rec_from_obj") != "", col("_rec_from_obj").cast("double"))
            .when(col("_rec_from_num") != "", col("_rec_from_num").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("_rec_conf_raw", get_json_object(col("result_json"), "$.summary.recommendation_confidence"))
        .withColumn("recommendation_confidence",
            when(col("_rec_conf_raw").isNotNull(), col("_rec_conf_raw").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("overall_assessment", get_json_object(col("result_json"), "$.summary.overall_assessment"))
        .withColumn("strength_categories_json", get_json_object(col("result_json"), "$.summary.strength_categories"))
        .withColumn("concern_categories_json", get_json_object(col("result_json"), "$.summary.concern_categories"))
        .withColumn("best_fit_categories_json", get_json_object(col("result_json"), "$.summary.best_fit_categories"))
        .withColumn("probe_categories_json", get_json_object(col("result_json"), "$.summary.probe_categories"))
        .withColumn("leverage_categories_json", get_json_object(col("result_json"), "$.summary.leverage_categories"))
        # Drop temporary columns
        .drop("_dm_raw", "_sc_raw", "_or_raw", "_orf_raw", "_wlb_raw", "_go_raw", "_tc_raw",
              "_cfe_str", "_tda_str", "_rec_score_raw", "_rec_from_obj", "_rec_from_num", "_rec_conf_raw")
    )

    # === UNION: Seleciona apenas colunas comuns ===
    print("Fazendo UNION dos 3 passes...")
    print(f"Columns in COLUMNS list: {len(COLUMNS)}")

    df1_selected = df1.select(COLUMNS)
    df2_selected = df2.select(COLUMNS)
    df3_selected = df3.select(COLUMNS)

    print(f"df1 columns: {len(df1_selected.columns)}")
    print(f"df2 columns: {len(df2_selected.columns)}")
    print(f"df3 columns: {len(df3_selected.columns)}")

    df = df1_selected.unionByName(df2_selected).unionByName(df3_selected)

    print("Schema da Silver (pré-write):")
    df.printSchema()

    # === SALVAR ===
    delta_path = "file://" + str(DELTA_SILVER_PATH)

    (
        df.write
        .format("delta")
        .mode("overwrite")
        .partitionBy("model_name", "pass_num")
        .save(delta_path)
    )

    print(f"Silver Delta criada em: {delta_path}")

    # Registrar como tabela no catálogo Spark
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS ai_enriched_jobs
        USING DELTA
        LOCATION '{delta_path}'
        """
    )

    # Verificar dados
    print("\nAmostra dos dados:")
    spark.sql("""
        SELECT job_id, model_name, pass_num, job_title,
               salary_min, seniority_level, recommendation_score
        FROM ai_enriched_jobs
        ORDER BY job_id, model_name, pass_num
        LIMIT 15
    """).show(truncate=False)

    # Contagem por pass
    print("\nContagem por pass:")
    spark.sql("""
        SELECT pass_num, COUNT(*) as count
        FROM ai_enriched_jobs
        GROUP BY pass_num
        ORDER BY pass_num
    """).show()

    spark.stop()


if __name__ == "__main__":
    run_bronze_to_silver_enriched_jobs()
