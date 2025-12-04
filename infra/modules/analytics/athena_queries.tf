########################################
# Athena Named Queries (SQL Templates)
########################################

resource "aws_athena_named_query" "top_skills" {
  name        = "top_skills"
  workgroup   = aws_athena_workgroup.this.name
  database    = aws_glue_catalog_database.data_engineer_jobs.name
  description = "Top 20 skills mais demandadas"

  query = <<-SQL
    SELECT
      skill,
      COUNT(*) as job_count,
      ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ${aws_glue_catalog_database.data_engineer_jobs.name}.linkedin_silver), 1) as percentage
    FROM ${aws_glue_catalog_database.data_engineer_jobs.name}.linkedin_silver
    CROSS JOIN UNNEST(skills_canonical) AS t(skill)
    GROUP BY skill
    ORDER BY job_count DESC
    LIMIT 20
  SQL
}

resource "aws_athena_named_query" "skills_by_family" {
  name        = "skills_by_family"
  workgroup   = aws_athena_workgroup.this.name
  database    = aws_glue_catalog_database.data_engineer_jobs.name
  description = "Distribuicao de skills por familia"

  query = <<-SQL
    SELECT
      family,
      COUNT(*) as job_count,
      ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ${aws_glue_catalog_database.data_engineer_jobs.name}.linkedin_silver), 1) as percentage
    FROM ${aws_glue_catalog_database.data_engineer_jobs.name}.linkedin_silver
    CROSS JOIN UNNEST(skills_families) AS t(family)
    GROUP BY family
    ORDER BY job_count DESC
  SQL
}

resource "aws_athena_named_query" "jobs_by_location" {
  name        = "jobs_by_location"
  workgroup   = aws_athena_workgroup.this.name
  database    = aws_glue_catalog_database.data_engineer_jobs.name
  description = "Vagas por localizacao"

  query = <<-SQL
    SELECT
      job_location,
      country_code,
      COUNT(*) as job_count
    FROM ${aws_glue_catalog_database.data_engineer_jobs.name}.linkedin_silver
    WHERE job_location IS NOT NULL
    GROUP BY job_location, country_code
    ORDER BY job_count DESC
    LIMIT 50
  SQL
}

resource "aws_athena_named_query" "salary_stats" {
  name        = "salary_stats"
  workgroup   = aws_athena_workgroup.this.name
  database    = aws_glue_catalog_database.data_engineer_jobs.name
  description = "Estatisticas de salario por nivel de senioridade"

  query = <<-SQL
    SELECT
      job_seniority_level,
      salary_currency,
      COUNT(*) as jobs_with_salary,
      ROUND(AVG(salary_min), 0) as avg_salary_min,
      ROUND(AVG(salary_max), 0) as avg_salary_max,
      ROUND(MIN(salary_min), 0) as min_salary,
      ROUND(MAX(salary_max), 0) as max_salary
    FROM ${aws_glue_catalog_database.data_engineer_jobs.name}.linkedin_silver
    WHERE salary_min IS NOT NULL
      AND salary_max IS NOT NULL
      AND salary_currency IS NOT NULL
    GROUP BY job_seniority_level, salary_currency
    ORDER BY jobs_with_salary DESC
  SQL
}

resource "aws_athena_named_query" "daily_job_trend" {
  name        = "daily_job_trend"
  workgroup   = aws_athena_workgroup.this.name
  database    = aws_glue_catalog_database.data_engineer_jobs.name
  description = "Tendencia diaria de vagas publicadas"

  query = <<-SQL
    SELECT
      job_posted_date_only as date,
      COUNT(*) as jobs_posted
    FROM ${aws_glue_catalog_database.data_engineer_jobs.name}.linkedin_silver
    WHERE job_posted_date_only IS NOT NULL
    GROUP BY job_posted_date_only
    ORDER BY job_posted_date_only DESC
    LIMIT 30
  SQL
}

resource "aws_athena_named_query" "top_companies" {
  name        = "top_companies"
  workgroup   = aws_athena_workgroup.this.name
  database    = aws_glue_catalog_database.data_engineer_jobs.name
  description = "Empresas que mais contratam"

  query = <<-SQL
    SELECT
      company_name,
      COUNT(*) as job_count,
      ARRAY_AGG(DISTINCT job_seniority_level) as seniority_levels
    FROM ${aws_glue_catalog_database.data_engineer_jobs.name}.linkedin_silver
    WHERE company_name IS NOT NULL
    GROUP BY company_name
    ORDER BY job_count DESC
    LIMIT 30
  SQL
}
