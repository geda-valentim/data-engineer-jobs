#!/usr/bin/env python3
"""
Teste local de detecção de skills (sem Spark).

Uso:
  # Testar com texto direto
  python src/scripts/test_skills_local.py "Senior Python Developer with AWS and Kafka experience"

  # Testar com arquivo de vagas (JSON lines)
  python src/scripts/test_skills_local.py --file data/sample_jobs.jsonl

  # Ver estatísticas do catálogo
  python src/scripts/test_skills_local.py --stats
"""

import argparse
import json
import sys
from pathlib import Path

# Adiciona src ao path para importar o módulo
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills_detection.skill_matcher import SkillMatcher, CATALOG_VERSION


def load_catalog() -> dict:
    """Carrega o catálogo JSON (mesmo formato usado em produção)."""
    config_dir = Path(__file__).parent.parent / "skills_detection" / "config"
    json_path = config_dir / "skills_catalog.json"

    if json_path.exists():
        with open(json_path) as f:
            return json.load(f)

    raise FileNotFoundError(
        f"Skills catalog not found: {json_path}\n"
        f"Run 'make skills-catalog' to generate from YAML."
    )


def test_text(text: str, matcher: SkillMatcher) -> None:
    """Testa detecção em um texto."""
    result = matcher.detect(text)

    print(f"\nTexto: {text[:100]}{'...' if len(text) > 100 else ''}")
    print(f"Catalog version: {result['catalog_version']}")
    print(f"\nSkills encontradas ({len(result['skills_canonical'])}):")

    if result["skills_canonical"]:
        for skill in result["skills_canonical"]:
            print(f"  - {skill}")
    else:
        print("  (nenhuma)")

    print(f"\nFamílias ({len(result['skills_families'])}):")
    if result["skills_families"]:
        for family in result["skills_families"]:
            print(f"  - {family}")
    else:
        print("  (nenhuma)")

    print(f"\nTermos detectados ({len(result['skills_raw_hits'])}):")
    if result["skills_raw_hits"]:
        for hit in result["skills_raw_hits"]:
            print(f"  - '{hit}'")


def test_file(file_path: str, matcher: SkillMatcher) -> None:
    """Testa detecção em arquivo de vagas (JSON lines)."""
    path = Path(file_path)
    if not path.exists():
        print(f"Arquivo não encontrado: {file_path}")
        sys.exit(1)

    jobs = []
    with open(path) as f:
        for line in f:
            if line.strip():
                jobs.append(json.loads(line))

    print(f"Processando {len(jobs)} vagas de {file_path}...")

    all_skills = set()
    all_families = set()
    jobs_with_skills = 0

    for job in jobs:
        title = job.get("job_title", "")
        description = job.get("job_description_text", job.get("job_description", ""))
        text = f"{title} {description}"

        result = matcher.detect(text)

        if result["skills_canonical"]:
            jobs_with_skills += 1
            all_skills.update(result["skills_canonical"])
            all_families.update(result["skills_families"])

    print(f"\nResultados:")
    print(f"  Vagas processadas: {len(jobs)}")
    print(f"  Vagas com skills: {jobs_with_skills} ({jobs_with_skills/len(jobs)*100:.1f}%)")
    print(f"  Skills únicas: {len(all_skills)}")
    print(f"  Famílias: {len(all_families)}")

    print(f"\nTop skills encontradas:")
    # Para um relatório mais detalhado, precisaria contar frequências
    for skill in sorted(all_skills)[:20]:
        print(f"  - {skill}")


def show_stats(catalog: dict, matcher: SkillMatcher) -> None:
    """Mostra estatísticas do catálogo."""
    print(f"Catálogo de Skills - Versão {CATALOG_VERSION}")
    print("=" * 50)

    families = {}
    total_skills = 0
    total_variations = 0

    for family, family_obj in catalog.items():
        if not isinstance(family_obj, dict):
            continue

        family_count = 0
        for group_key, group_obj in family_obj.items():
            if not isinstance(group_obj, dict):
                continue

            family_count += 1
            total_skills += 1
            total_variations += len(group_obj.get("variations", []))

            for sub in group_obj.get("sub_skills", []) or []:
                family_count += 1
                total_skills += 1
                total_variations += len(sub.get("variations", []))

        families[family] = family_count

    print(f"\nTotal de skills: {total_skills}")
    print(f"Total de variações: {total_variations}")
    print(f"Média de variações por skill: {total_variations/total_skills:.1f}")

    print(f"\nSkills por família:")
    for family, count in sorted(families.items(), key=lambda x: -x[1]):
        print(f"  {family}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Teste local de detecção de skills")
    parser.add_argument("text", nargs="?", help="Texto para testar")
    parser.add_argument("--file", "-f", help="Arquivo JSON lines com vagas")
    parser.add_argument("--stats", "-s", action="store_true", help="Mostra estatísticas do catálogo")

    args = parser.parse_args()

    # Carrega catálogo
    try:
        catalog = load_catalog()
    except FileNotFoundError as e:
        print(f"Erro: {e}")
        sys.exit(1)

    matcher = SkillMatcher.from_dict(catalog, version=CATALOG_VERSION)
    print(f"Catálogo carregado: {len(matcher.skills)} skills")

    if args.stats:
        show_stats(catalog, matcher)
    elif args.file:
        test_file(args.file, matcher)
    elif args.text:
        test_text(args.text, matcher)
    else:
        # Modo interativo
        print("\nModo interativo. Digite texto para testar (Ctrl+C para sair):\n")
        try:
            while True:
                text = input("> ")
                if text.strip():
                    test_text(text, matcher)
                    print()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")


if __name__ == "__main__":
    main()
