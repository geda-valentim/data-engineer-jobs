"""
GraphQL Server para consultar Delta Lake local.
Uso: PYTHONPATH=. poetry run python src/dev/graphql/server.py
"""
import strawberry
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional
from pathlib import Path
import json
from collections import Counter

from pyspark.sql.functions import countDistinct, explode, col, from_json, count, lower, trim
from pyspark.sql.types import ArrayType, StringType

from src.dev.deltalake.spark_session import get_spark


# Paths (relativos ao projeto)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # src/dev/graphql -> raiz
BASE_DIR = PROJECT_ROOT / "data" / "local" / "ai_enrichment"
DELTA_SILVER_PATH = f"file://{BASE_DIR}/silver/delta/enriched_jobs"

# Spark Session (singleton)
_spark = None


def get_spark_session():
    global _spark
    if _spark is None:
        _spark = get_spark("GraphQLServer")
    return _spark


# =============================================================================
# GraphQL Types - Nested Results for Each Pass
# =============================================================================

@strawberry.type
class Pass1Compensation:
    """Compensation data extracted from job posting."""
    salary_disclosed: Optional[bool] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    salary_text_raw: Optional[str] = None


@strawberry.type
class Pass1WorkAuthorization:
    """Work authorization requirements."""
    visa_sponsorship: Optional[str] = None
    security_clearance: Optional[str] = None


@strawberry.type
class Pass1WorkModel:
    """Work model and employment details."""
    work_model: Optional[str] = None
    employment_type: Optional[str] = None
    location_restriction_text: Optional[str] = None
    contract_type: Optional[str] = None


@strawberry.type
class Pass1Skills:
    """Skills requirements."""
    must_have_skills_json: Optional[str] = None
    nice_to_have_skills_json: Optional[str] = None


@strawberry.type
class Pass1Experience:
    """Experience requirements."""
    years_experience_min: Optional[float] = None
    years_experience_max: Optional[float] = None
    years_experience_text: Optional[str] = None


@strawberry.type
class Pass1Education:
    """Education requirements."""
    education_level: Optional[str] = None
    education_area: Optional[str] = None
    education_requirement: Optional[str] = None


@strawberry.type
class Pass1GeoRestrictions:
    """Geographic restrictions."""
    geo_restriction_type: Optional[str] = None
    allowed_countries_json: Optional[str] = None
    us_state_restrictions_json: Optional[str] = None


@strawberry.type
class Pass1Benefits:
    """Benefits information."""
    equity_mentioned: Optional[bool] = None
    learning_budget_mentioned: Optional[bool] = None
    pto_policy: Optional[str] = None
    benefits_json: Optional[str] = None


@strawberry.type
class Pass1Context:
    """Team and company context."""
    team_info_text: Optional[str] = None
    company_description_text: Optional[str] = None


@strawberry.type
class Pass1ExtractionResult:
    """Pass1 - Extraction of structured data from job posting."""
    compensation: Optional[Pass1Compensation] = None
    work_authorization: Optional[Pass1WorkAuthorization] = None
    work_model: Optional[Pass1WorkModel] = None
    skills: Optional[Pass1Skills] = None
    experience: Optional[Pass1Experience] = None
    education: Optional[Pass1Education] = None
    geo_restrictions: Optional[Pass1GeoRestrictions] = None
    benefits: Optional[Pass1Benefits] = None
    context: Optional[Pass1Context] = None


@strawberry.type
class Pass2SeniorityAndRole:
    """Seniority and role inference."""
    seniority_level: Optional[str] = None
    job_family: Optional[str] = None
    sub_specialty: Optional[str] = None
    leadership_expectation: Optional[str] = None


@strawberry.type
class Pass2StackAndCloud:
    """Tech stack and cloud inference."""
    primary_cloud: Optional[str] = None
    secondary_clouds_json: Optional[str] = None
    processing_paradigm: Optional[str] = None
    orchestrator_category: Optional[str] = None
    storage_layer: Optional[str] = None


@strawberry.type
class Pass2GeoAndWorkModel:
    """Geographic and work model inference."""
    remote_restriction: Optional[str] = None
    timezone_focus: Optional[str] = None
    relocation_required: Optional[bool] = None


@strawberry.type
class Pass2VisaAndAuthorization:
    """Visa and work authorization inference."""
    h1b_friendly: Optional[bool] = None
    opt_cpt_friendly: Optional[bool] = None
    citizenship_required: Optional[str] = None


@strawberry.type
class Pass2ContractAndCompensation:
    """Contract and compensation inference."""
    w2_vs_1099: Optional[str] = None
    benefits_level: Optional[str] = None


@strawberry.type
class Pass2CareerDevelopment:
    """Career development inference."""
    growth_path_clarity: Optional[str] = None
    mentorship_signals: Optional[str] = None
    promotion_path_mentioned: Optional[bool] = None
    internal_mobility_mentioned: Optional[bool] = None
    career_tracks_json: Optional[str] = None


@strawberry.type
class Pass2RequirementsClassification:
    """Requirements classification inference."""
    requirement_strictness: Optional[str] = None
    scope_definition: Optional[str] = None
    skill_inflation_detected: Optional[bool] = None


@strawberry.type
class Pass2InferenceResult:
    """Pass2 - Inferences derived from extracted data."""
    seniority_and_role: Optional[Pass2SeniorityAndRole] = None
    stack_and_cloud: Optional[Pass2StackAndCloud] = None
    geo_and_work_model: Optional[Pass2GeoAndWorkModel] = None
    visa_and_authorization: Optional[Pass2VisaAndAuthorization] = None
    contract_and_compensation: Optional[Pass2ContractAndCompensation] = None
    career_development: Optional[Pass2CareerDevelopment] = None
    requirements_classification: Optional[Pass2RequirementsClassification] = None


@strawberry.type
class Pass3Scores:
    """Analysis scores."""
    data_maturity_score: Optional[float] = None
    scope_creep_score: Optional[float] = None
    overtime_risk_score: Optional[float] = None
    overall_red_flag_score: Optional[float] = None
    work_life_balance_score: Optional[float] = None
    growth_opportunities_score: Optional[float] = None
    tech_culture_score: Optional[float] = None
    recommendation_score: Optional[float] = None
    recommendation_confidence: Optional[float] = None


@strawberry.type
class Pass3CompanyMaturity:
    """Company data maturity analysis."""
    data_maturity_level: Optional[str] = None
    maturity_signals_json: Optional[str] = None


@strawberry.type
class Pass3RedFlags:
    """Red flags and role quality assessment."""
    role_clarity: Optional[str] = None


@strawberry.type
class Pass3Stakeholders:
    """Stakeholders and leadership analysis."""
    reporting_structure_clarity: Optional[str] = None
    manager_level_inferred: Optional[str] = None
    team_growth_velocity: Optional[str] = None
    cross_functional_embedded: Optional[bool] = None


@strawberry.type
class Pass3TechCultureAssessment:
    """Tech culture assessment details."""
    tech_culture_signals_json: Optional[str] = None
    dev_practices_json: Optional[str] = None
    innovation_signals: Optional[str] = None
    tech_debt_awareness: Optional[bool] = None


@strawberry.type
class Pass3AIMLIntegration:
    """AI/ML integration analysis."""
    ai_integration_level: Optional[str] = None
    ml_tools_json: Optional[str] = None


@strawberry.type
class Pass3CompetitionTiming:
    """Competition and timing analysis."""
    hiring_urgency: Optional[str] = None
    competition_level: Optional[str] = None


@strawberry.type
class Pass3CompanyContext:
    """Company context analysis."""
    company_stage_inferred: Optional[str] = None
    hiring_velocity: Optional[str] = None
    role_creation_type: Optional[str] = None


@strawberry.type
class Pass3Summary:
    """Analysis summary and categories."""
    overall_assessment: Optional[str] = None
    strength_categories_json: Optional[str] = None
    concern_categories_json: Optional[str] = None
    best_fit_categories_json: Optional[str] = None
    probe_categories_json: Optional[str] = None
    leverage_categories_json: Optional[str] = None


@strawberry.type
class Pass3AnalysisResult:
    """Pass3 - Analysis and scoring of the job posting."""
    scores: Optional[Pass3Scores] = None
    company_maturity: Optional[Pass3CompanyMaturity] = None
    red_flags: Optional[Pass3RedFlags] = None
    stakeholders: Optional[Pass3Stakeholders] = None
    tech_culture_assessment: Optional[Pass3TechCultureAssessment] = None
    ai_ml_integration: Optional[Pass3AIMLIntegration] = None
    competition_timing: Optional[Pass3CompetitionTiming] = None
    company_context: Optional[Pass3CompanyContext] = None
    summary: Optional[Pass3Summary] = None


@strawberry.type
class PassResult:
    """Resultado de um pass específico de um modelo."""
    pass_num: int
    source_file: Optional[str] = None
    # Métricas (todos os passes)
    tokens: Optional[int] = None
    cost: Optional[float] = None
    # Nested results by pass type
    extraction: Optional[Pass1ExtractionResult] = None  # pass_num=1
    inference: Optional[Pass2InferenceResult] = None    # pass_num=2
    analysis: Optional[Pass3AnalysisResult] = None      # pass_num=3
    # Raw (debug)
    result_json: Optional[str] = None


@strawberry.type
class ModelResult:
    """Resultados de um modelo específico para um job."""
    model_name: str
    passes: List[PassResult]


@strawberry.type
class Job:
    """Job completo com todos os modelos e passes."""
    job_id: strawberry.ID  # ID como string para suportar valores long
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    job_location: Optional[str] = None
    models: List[ModelResult]


@strawberry.type
class JobSummary:
    """Resumo de um job para listagem."""
    job_id: strawberry.ID  # ID como string para suportar valores long
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    job_location: Optional[str] = None
    models_count: int


@strawberry.type
class JobStats:
    """Estatísticas gerais do dataset."""
    total_records: int
    unique_jobs: int
    models: List[str]
    passes: List[int]


@strawberry.type
class SkillCount:
    """Skill with occurrence count."""
    skill: str
    count: int


@strawberry.type
class SkillsResult:
    """Result containing list of skills with counts."""
    skills: List[SkillCount]
    total_unique: int
    total_occurrences: int


# =============================================================================
# Helper Functions
# =============================================================================

def _build_pass1_extraction(row) -> Optional[Pass1ExtractionResult]:
    """Build Pass1 extraction result from row."""
    return Pass1ExtractionResult(
        compensation=Pass1Compensation(
            salary_disclosed=getattr(row, "salary_disclosed", None),
            salary_min=getattr(row, "salary_min", None),
            salary_max=getattr(row, "salary_max", None),
            salary_currency=getattr(row, "salary_currency", None),
            salary_period=getattr(row, "salary_period", None),
            salary_text_raw=getattr(row, "salary_text_raw", None),
        ),
        work_authorization=Pass1WorkAuthorization(
            visa_sponsorship=getattr(row, "visa_sponsorship", None),
            security_clearance=getattr(row, "security_clearance", None),
        ),
        work_model=Pass1WorkModel(
            work_model=getattr(row, "work_model", None),
            employment_type=getattr(row, "employment_type", None),
            location_restriction_text=getattr(row, "location_restriction_text", None),
            contract_type=getattr(row, "contract_type", None),
        ),
        skills=Pass1Skills(
            must_have_skills_json=getattr(row, "must_have_skills_json", None),
            nice_to_have_skills_json=getattr(row, "nice_to_have_skills_json", None),
        ),
        experience=Pass1Experience(
            years_experience_min=getattr(row, "years_experience_min", None),
            years_experience_max=getattr(row, "years_experience_max", None),
            years_experience_text=getattr(row, "years_experience_text", None),
        ),
        education=Pass1Education(
            education_level=getattr(row, "education_level", None),
            education_area=getattr(row, "education_area", None),
            education_requirement=getattr(row, "education_requirement", None),
        ),
        geo_restrictions=Pass1GeoRestrictions(
            geo_restriction_type=getattr(row, "geo_restriction_type", None),
            allowed_countries_json=getattr(row, "allowed_countries_json", None),
            us_state_restrictions_json=getattr(row, "us_state_restrictions_json", None),
        ),
        benefits=Pass1Benefits(
            equity_mentioned=getattr(row, "equity_mentioned", None),
            learning_budget_mentioned=getattr(row, "learning_budget_mentioned", None),
            pto_policy=getattr(row, "pto_policy", None),
            benefits_json=getattr(row, "benefits_json", None),
        ),
        context=Pass1Context(
            team_info_text=getattr(row, "team_info_text", None),
            company_description_text=getattr(row, "company_description_text", None),
        ),
    )


def _build_pass2_inference(row) -> Optional[Pass2InferenceResult]:
    """Build Pass2 inference result from row."""
    return Pass2InferenceResult(
        seniority_and_role=Pass2SeniorityAndRole(
            seniority_level=getattr(row, "seniority_level", None),
            job_family=getattr(row, "job_family", None),
            sub_specialty=getattr(row, "sub_specialty", None),
            leadership_expectation=getattr(row, "leadership_expectation", None),
        ),
        stack_and_cloud=Pass2StackAndCloud(
            primary_cloud=getattr(row, "primary_cloud", None),
            secondary_clouds_json=getattr(row, "secondary_clouds_json", None),
            processing_paradigm=getattr(row, "processing_paradigm", None),
            orchestrator_category=getattr(row, "orchestrator_category", None),
            storage_layer=getattr(row, "storage_layer", None),
        ),
        geo_and_work_model=Pass2GeoAndWorkModel(
            remote_restriction=getattr(row, "remote_restriction", None),
            timezone_focus=getattr(row, "timezone_focus", None),
            relocation_required=getattr(row, "relocation_required", None),
        ),
        visa_and_authorization=Pass2VisaAndAuthorization(
            h1b_friendly=getattr(row, "h1b_friendly", None),
            opt_cpt_friendly=getattr(row, "opt_cpt_friendly", None),
            citizenship_required=getattr(row, "citizenship_required", None),
        ),
        contract_and_compensation=Pass2ContractAndCompensation(
            w2_vs_1099=getattr(row, "w2_vs_1099", None),
            benefits_level=getattr(row, "benefits_level", None),
        ),
        career_development=Pass2CareerDevelopment(
            growth_path_clarity=getattr(row, "growth_path_clarity", None),
            mentorship_signals=getattr(row, "mentorship_signals", None),
            promotion_path_mentioned=getattr(row, "promotion_path_mentioned", None),
            internal_mobility_mentioned=getattr(row, "internal_mobility_mentioned", None),
            career_tracks_json=getattr(row, "career_tracks_json", None),
        ),
        requirements_classification=Pass2RequirementsClassification(
            requirement_strictness=getattr(row, "requirement_strictness", None),
            scope_definition=getattr(row, "scope_definition", None),
            skill_inflation_detected=getattr(row, "skill_inflation_detected", None),
        ),
    )


def _build_pass3_analysis(row) -> Optional[Pass3AnalysisResult]:
    """Build Pass3 analysis result from row."""
    return Pass3AnalysisResult(
        scores=Pass3Scores(
            data_maturity_score=getattr(row, "data_maturity_score", None),
            scope_creep_score=getattr(row, "scope_creep_score", None),
            overtime_risk_score=getattr(row, "overtime_risk_score", None),
            overall_red_flag_score=getattr(row, "overall_red_flag_score", None),
            work_life_balance_score=getattr(row, "work_life_balance_score", None),
            growth_opportunities_score=getattr(row, "growth_opportunities_score", None),
            tech_culture_score=getattr(row, "tech_culture_score", None),
            recommendation_score=getattr(row, "recommendation_score", None),
            recommendation_confidence=getattr(row, "recommendation_confidence", None),
        ),
        company_maturity=Pass3CompanyMaturity(
            data_maturity_level=getattr(row, "data_maturity_level", None),
            maturity_signals_json=getattr(row, "maturity_signals_json", None),
        ),
        red_flags=Pass3RedFlags(
            role_clarity=getattr(row, "role_clarity", None),
        ),
        stakeholders=Pass3Stakeholders(
            reporting_structure_clarity=getattr(row, "reporting_structure_clarity", None),
            manager_level_inferred=getattr(row, "manager_level_inferred", None),
            team_growth_velocity=getattr(row, "team_growth_velocity", None),
            cross_functional_embedded=getattr(row, "cross_functional_embedded", None),
        ),
        tech_culture_assessment=Pass3TechCultureAssessment(
            tech_culture_signals_json=getattr(row, "tech_culture_signals_json", None),
            dev_practices_json=getattr(row, "dev_practices_json", None),
            innovation_signals=getattr(row, "innovation_signals", None),
            tech_debt_awareness=getattr(row, "tech_debt_awareness", None),
        ),
        ai_ml_integration=Pass3AIMLIntegration(
            ai_integration_level=getattr(row, "ai_integration_level", None),
            ml_tools_json=getattr(row, "ml_tools_json", None),
        ),
        competition_timing=Pass3CompetitionTiming(
            hiring_urgency=getattr(row, "hiring_urgency", None),
            competition_level=getattr(row, "competition_level", None),
        ),
        company_context=Pass3CompanyContext(
            company_stage_inferred=getattr(row, "company_stage_inferred", None),
            hiring_velocity=getattr(row, "hiring_velocity", None),
            role_creation_type=getattr(row, "role_creation_type", None),
        ),
        summary=Pass3Summary(
            overall_assessment=getattr(row, "overall_assessment", None),
            strength_categories_json=getattr(row, "strength_categories_json", None),
            concern_categories_json=getattr(row, "concern_categories_json", None),
            best_fit_categories_json=getattr(row, "best_fit_categories_json", None),
            probe_categories_json=getattr(row, "probe_categories_json", None),
            leverage_categories_json=getattr(row, "leverage_categories_json", None),
        ),
    )


def _get_hard_skills(requirement_type: str) -> SkillsResult:
    """Get hard skills from Delta Lake (must_have or nice_to_have)."""
    spark = get_spark_session()
    df = spark.read.format("delta").load(DELTA_SILVER_PATH)
    pass1 = df.filter(col("pass_num") == 1)

    json_col = "must_have_skills_json" if requirement_type == "must_have" else "nice_to_have_skills_json"

    skills_df = (pass1
        .filter(col(json_col).isNotNull())
        .select(from_json(col(json_col), ArrayType(StringType())).alias("skills"))
        .select(explode(col("skills")).alias("skill"))
        .filter(col("skill").isNotNull())
        .withColumn("skill_normalized", lower(trim(col("skill"))))
        .groupBy("skill_normalized")
        .agg(count("*").alias("occurrences"))
        .orderBy(col("occurrences").desc())
        .collect()
    )

    skills = [SkillCount(skill=r.skill_normalized, count=r.occurrences) for r in skills_df]
    total_occurrences = sum(s.count for s in skills)

    return SkillsResult(
        skills=skills,
        total_unique=len(skills),
        total_occurrences=total_occurrences
    )


def _get_soft_skills(requirement_type: str) -> SkillsResult:
    """Get soft skills from bronze JSON files (must_have or nice_to_have)."""
    bronze_dir = PROJECT_ROOT / "data" / "local" / "ai_enrichment" / "bronze"

    field_name = "ext_must_have_soft_skills" if requirement_type == "must_have" else "ext_nice_to_have_soft_skills"
    all_skills = []

    for pass1_file in bronze_dir.glob("*/pass1-*.json"):
        try:
            with open(pass1_file) as f:
                data = json.load(f)
            result = data.get("result", {})
            skills_list = result.get(field_name, []) or []
            all_skills.extend([s.lower().strip() for s in skills_list])
        except Exception:
            pass

    skill_counts = Counter(all_skills)
    skills = [SkillCount(skill=skill, count=cnt) for skill, cnt in skill_counts.most_common()]
    total_occurrences = sum(s.count for s in skills)

    return SkillsResult(
        skills=skills,
        total_unique=len(skills),
        total_occurrences=total_occurrences
    )


def _get_job_by_id(job_id: str) -> Optional[Job]:
    """Helper para buscar job por ID."""
    spark = get_spark_session()
    df = spark.read.format("delta").load(DELTA_SILVER_PATH)

    job_id_long = int(job_id)
    rows = df.filter(df.job_id == job_id_long).collect()
    if not rows:
        return None

    # Agrupa por modelo
    models_dict: dict = {}
    job_title = company_name = job_location = None

    for row in rows:
        # Pega metadata do primeiro registro
        if job_title is None:
            job_title = getattr(row, "job_title", None)
            company_name = getattr(row, "company_name", None)
            job_location = getattr(row, "job_location", None)

        model_name = row.model_name
        if model_name not in models_dict:
            models_dict[model_name] = []

        pass_num = row.pass_num

        # Build nested results based on pass_num
        extraction = _build_pass1_extraction(row) if pass_num == 1 else None
        inference = _build_pass2_inference(row) if pass_num == 2 else None
        analysis = _build_pass3_analysis(row) if pass_num == 3 else None

        models_dict[model_name].append(PassResult(
            pass_num=pass_num,
            source_file=getattr(row, "source_file", None),
            tokens=getattr(row, "tokens", None),
            cost=getattr(row, "cost", None),
            extraction=extraction,
            inference=inference,
            analysis=analysis,
            result_json=getattr(row, "result_json", None),
        ))

    models = [
        ModelResult(model_name=name, passes=sorted(passes, key=lambda p: p.pass_num))
        for name, passes in models_dict.items()
    ]

    return Job(
        job_id=str(job_id),
        job_title=job_title,
        company_name=company_name,
        job_location=job_location,
        models=models,
    )


# =============================================================================
# GraphQL Resolvers
# =============================================================================

@strawberry.type
class Query:
    @strawberry.field
    def job(self, job_id: strawberry.ID) -> Optional[Job]:
        """Busca um job por ID com estrutura hierárquica (modelos → passes)."""
        return _get_job_by_id(str(job_id))

    @strawberry.field
    def jobs(self, limit: int = 100) -> List[JobSummary]:
        """Lista todos os jobs disponíveis com contagem de modelos."""
        spark = get_spark_session()
        df = spark.read.format("delta").load(DELTA_SILVER_PATH)

        # Agrupa por job_id para contar modelos distintos
        summary = (
            df.groupBy("job_id", "job_title", "company_name", "job_location")
            .agg(countDistinct("model_name").alias("models_count"))
            .orderBy("job_id")
            .limit(limit)
            .collect()
        )

        return [
            JobSummary(
                job_id=str(row.job_id),
                job_title=row.job_title,
                company_name=row.company_name,
                job_location=row.job_location,
                models_count=row.models_count,
            )
            for row in summary
        ]

    @strawberry.field
    def stats(self) -> JobStats:
        """Estatísticas gerais dos dados."""
        spark = get_spark_session()
        df = spark.read.format("delta").load(DELTA_SILVER_PATH)

        total = df.count()
        unique_jobs = df.select("job_id").distinct().count()
        models = [row.model_name for row in df.select("model_name").distinct().collect()]
        passes = [row.pass_num for row in df.select("pass_num").distinct().collect()]

        return JobStats(
            total_records=total,
            unique_jobs=unique_jobs,
            models=sorted(models),
            passes=sorted(passes),
        )

    @strawberry.field
    def compare_models(self, job_id: strawberry.ID, pass_num: Optional[int] = None) -> List[ModelResult]:
        """Compara resultados de diferentes modelos para o mesmo job."""
        job = _get_job_by_id(str(job_id))
        if not job:
            return []

        if pass_num is not None:
            # Filtra apenas o pass especificado
            return [
                ModelResult(
                    model_name=m.model_name,
                    passes=[p for p in m.passes if p.pass_num == pass_num]
                )
                for m in job.models
            ]
        return job.models

    @strawberry.field
    def hard_skills_required(self, limit: Optional[int] = None) -> SkillsResult:
        """Lista hard skills obrigatórias (must-have) ordenadas por frequência."""
        result = _get_hard_skills("must_have")
        if limit:
            result.skills = result.skills[:limit]
        return result

    @strawberry.field
    def hard_skills_nice_to_have(self, limit: Optional[int] = None) -> SkillsResult:
        """Lista hard skills desejáveis (nice-to-have) ordenadas por frequência."""
        result = _get_hard_skills("nice_to_have")
        if limit:
            result.skills = result.skills[:limit]
        return result

    @strawberry.field
    def soft_skills_required(self, limit: Optional[int] = None) -> SkillsResult:
        """Lista soft skills obrigatórias (must-have) ordenadas por frequência."""
        result = _get_soft_skills("must_have")
        if limit:
            result.skills = result.skills[:limit]
        return result

    @strawberry.field
    def soft_skills_nice_to_have(self, limit: Optional[int] = None) -> SkillsResult:
        """Lista soft skills desejáveis (nice-to-have) ordenadas por frequência."""
        result = _get_soft_skills("nice_to_have")
        if limit:
            result.skills = result.skills[:limit]
        return result


# =============================================================================
# FastAPI App
# =============================================================================

schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)

app = FastAPI(title="Delta Lake GraphQL API", version="0.1.0")

# CORS para permitir acesso do frontend (Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Create React App
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graphql_app, prefix="/graphql")


@app.get("/")
def root():
    return {"message": "GraphQL API para Delta Lake", "graphql_url": "/graphql"}


@app.on_event("shutdown")
def shutdown():
    global _spark
    if _spark:
        _spark.stop()


if __name__ == "__main__":
    import uvicorn
    print(f"Iniciando GraphQL Server...")
    print(f"Delta Path: {DELTA_SILVER_PATH}")
    print(f"GraphQL Playground: http://localhost:8001/graphql")
    uvicorn.run(app, host="0.0.0.0", port=8001)
