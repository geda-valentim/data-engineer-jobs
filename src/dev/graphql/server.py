"""
GraphQL Server para consultar Delta Lake local.
Uso: PYTHONPATH=. poetry run python src/dev/graphql/server.py
"""
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from typing import List, Optional
from pathlib import Path
from pyspark.sql.functions import countDistinct

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
# GraphQL Types
# =============================================================================

@strawberry.type
class PassResult:
    """Resultado de um pass específico de um modelo."""
    pass_num: int
    source_file: Optional[str] = None
    # Métricas (todos os passes)
    tokens: Optional[int] = None
    cost: Optional[float] = None
    # Pass1 - Extração
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    work_model: Optional[str] = None
    contract_type: Optional[str] = None
    years_experience_min: Optional[float] = None
    education_level: Optional[str] = None
    must_have_skills_json: Optional[str] = None
    # Pass2 - Inferências
    seniority_level: Optional[str] = None
    primary_cloud: Optional[str] = None
    # Pass3 - Análise
    recommendation_score: Optional[float] = None
    overall_assessment: Optional[str] = None
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


# =============================================================================
# Helper Functions
# =============================================================================

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

        models_dict[model_name].append(PassResult(
            pass_num=row.pass_num,
            source_file=getattr(row, "source_file", None),
            # Métricas
            tokens=getattr(row, "tokens", None),
            cost=getattr(row, "cost", None),
            # Pass1
            salary_min=getattr(row, "salary_min", None),
            salary_max=getattr(row, "salary_max", None),
            salary_currency=getattr(row, "salary_currency", None),
            work_model=getattr(row, "work_model", None),
            contract_type=getattr(row, "contract_type", None),
            years_experience_min=getattr(row, "years_experience_min", None),
            education_level=getattr(row, "education_level", None),
            must_have_skills_json=getattr(row, "must_have_skills_json", None),
            # Pass2
            seniority_level=getattr(row, "seniority_level", None),
            primary_cloud=getattr(row, "primary_cloud", None),
            # Pass3
            recommendation_score=getattr(row, "recommendation_score", None),
            overall_assessment=getattr(row, "overall_assessment", None),
            # Raw
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


# =============================================================================
# FastAPI App
# =============================================================================

schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)

app = FastAPI(title="Delta Lake GraphQL API", version="0.1.0")
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
    print(f"GraphQL Playground: http://localhost:8000/graphql")
    uvicorn.run(app, host="0.0.0.0", port=8000)
