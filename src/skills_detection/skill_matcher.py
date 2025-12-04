"""
Módulo de detecção de skills em textos de vagas.

Uso standalone (Python puro):
    matcher = SkillMatcher.from_json(catalog_dict)
    result = matcher.detect("Senior Python Developer with AWS")

Uso no Glue/Spark:
    from skills_detection.skill_matcher import create_skills_udf
    udf = create_skills_udf(spark_context, catalog_dict, version="v1.0")
    df.withColumn("skills", udf(col("text")))
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import re


CATALOG_VERSION = "v1.0"


@dataclass
class SkillDefinition:
    """Representa uma skill do catálogo."""
    family: str
    group: str
    canonical: str
    variations: List[str]
    priority: str | None = None


def parse_catalog(catalog: dict) -> List[SkillDefinition]:
    """
    Transforma o dict do catálogo em lista de SkillDefinition.

    Formato esperado (dict aninhado):
        family_name:
          skill_key:
            canonical: "Skill Name"
            variations: [...]
            priority: high|medium|low
            sub_skills:  # opcional
              - canonical: "Sub Skill"
                variations: [...]

    Exemplo:
        cloud_platforms:
          azure:
            canonical: "Azure"
            variations: ["azure", "microsoft azure"]
            sub_skills:
              - canonical: "Azure Data Factory"
                variations: ["adf", "data factory"]
    """
    skills: List[SkillDefinition] = []

    if not isinstance(catalog, dict):
        return skills

    for family, family_obj in catalog.items():
        # Ignora seção de config
        if family == "config":
            continue

        if not isinstance(family_obj, dict):
            continue

        for group_key, group_obj in family_obj.items():
            if not isinstance(group_obj, dict):
                continue

            canonical = group_obj.get("canonical", group_key)
            variations = group_obj.get("variations", []) or []
            priority = group_obj.get("priority")

            skills.append(
                SkillDefinition(
                    family=family,
                    group=group_key,
                    canonical=canonical,
                    variations=variations,
                    priority=priority,
                )
            )

            # Sub-skills (para hierarquias como Azure > Azure Data Factory)
            for sub in group_obj.get("sub_skills", []) or []:
                sub_canonical = sub.get("canonical")
                if not sub_canonical:
                    continue
                skills.append(
                    SkillDefinition(
                        family=family,
                        group=group_key,
                        canonical=sub_canonical,
                        variations=sub.get("variations", []) or [],
                        priority=sub.get("priority"),
                    )
                )

    return skills


class SkillMatcher:
    """Detecta skills em textos usando o catálogo."""

    def __init__(self, skills: List[SkillDefinition], catalog_version: str = CATALOG_VERSION):
        self.skills = skills
        self.catalog_version = catalog_version

    @classmethod
    def from_dict(cls, catalog: dict, version: str = CATALOG_VERSION) -> "SkillMatcher":
        """Cria matcher a partir de dict (JSON ou YAML parseado)."""
        skills = parse_catalog(catalog)
        return cls(skills=skills, catalog_version=version)

    # Alias para compatibilidade
    from_json = from_dict

    @classmethod
    def from_yaml_str(cls, yaml_str: str, version: str = CATALOG_VERSION) -> "SkillMatcher":
        """Cria matcher a partir de string YAML."""
        import yaml
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data, version)

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detecta skills no texto.

        Args:
            text: Texto para analisar (título + descrição concatenados)

        Returns:
            Dict com skills_canonical, skills_families, skills_raw_hits, catalog_version
        """
        if not text:
            return {
                "skills_canonical": [],
                "skills_families": [],
                "skills_raw_hits": [],
                "catalog_version": self.catalog_version,
            }

        normalized = text.lower()
        found_canonical = set()
        found_families = set()
        raw_hits = set()

        for skill in self.skills:
            all_variations = [skill.canonical] + skill.variations

            for var in all_variations:
                v = (var or "").lower().strip()
                if not v:
                    continue

                pattern = r"\b" + re.escape(v) + r"\b"
                if re.search(pattern, normalized):
                    found_canonical.add(skill.canonical)
                    found_families.add(skill.family)
                    raw_hits.add(v)

        return {
            "skills_canonical": sorted(found_canonical),
            "skills_families": sorted(found_families),
            "skills_raw_hits": sorted(raw_hits),
            "catalog_version": self.catalog_version,
        }


def create_skills_udf(spark_context, catalog_dict: dict, version: str = CATALOG_VERSION):
    """
    Cria UDF do Spark para detecção de skills.

    Args:
        spark_context: SparkContext para broadcast
        catalog_dict: Catálogo parseado (dict)
        version: Versão do catálogo

    Returns:
        UDF que recebe (title, description) e retorna struct com skills

    Exemplo:
        udf = create_skills_udf(sc, catalog_dict)
        df.withColumn("skills_struct", udf(col("job_title"), col("job_description")))
    """
    from pyspark.sql.functions import udf
    from pyspark.sql.types import (
        ArrayType,
        StringType,
        StructType,
        StructField,
    )

    # Parse uma vez e broadcast
    skills_list = [
        {
            "family": s.family,
            "canonical": s.canonical,
            "variations": s.variations,
        }
        for s in parse_catalog(catalog_dict)
    ]
    skills_bc = spark_context.broadcast(skills_list)
    version_bc = spark_context.broadcast(version)

    def _detect(title: str, description: str):
        """Função interna executada nos workers."""
        parts = []
        if title:
            parts.append(str(title))
        if description:
            parts.append(str(description))

        if not parts:
            return ([], [], [], version_bc.value)

        text = " ".join(parts).lower()
        found_canonical = set()
        found_families = set()
        raw_hits = set()

        for skill in skills_bc.value:
            family = skill["family"]
            canonical = skill["canonical"]
            variations = skill["variations"] or []

            for term in [canonical] + variations:
                v = (term or "").lower().strip()
                if not v:
                    continue

                pattern = r"\b" + re.escape(v) + r"\b"
                if re.search(pattern, text):
                    found_canonical.add(canonical)
                    found_families.add(family)
                    raw_hits.add(v)

        return (
            sorted(found_canonical),
            sorted(found_families),
            sorted(raw_hits),
            version_bc.value,
        )

    schema = StructType([
        StructField("skills_canonical", ArrayType(StringType()), True),
        StructField("skills_families", ArrayType(StringType()), True),
        StructField("skills_raw_hits", ArrayType(StringType()), True),
        StructField("skills_catalog_version", StringType(), True),
    ])

    return udf(_detect, schema)
