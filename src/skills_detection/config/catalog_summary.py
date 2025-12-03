#!/usr/bin/env python3
"""
Script para visualizar o resumo do skills_catalog.yaml
"""

import yaml
from pathlib import Path
from collections import Counter

def load_catalog(catalog_path: Path) -> dict:
    """Carrega o catálogo de skills"""
    with open(catalog_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def count_skills(catalog: dict) -> dict:
    """Conta skills por categoria"""
    stats = {
        'total_categories': 0,
        'total_skills': 0,
        'by_category': {},
        'by_priority': Counter()
    }

    def count_recursive(data, category_name=''):
        skill_count = 0

        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['canonical', 'variations', 'priority', 'sub_variations']:
                    continue

                if key == 'sub_skills':
                    skill_count += len(value)
                    for skill in value:
                        if 'priority' in skill:
                            stats['by_priority'][skill['priority']] += 1
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and 'canonical' in item:
                            skill_count += 1
                            if 'priority' in item:
                                stats['by_priority'][item['priority']] += 1
                        elif isinstance(item, dict):
                            skill_count += count_recursive(item, key)
                elif isinstance(value, dict):
                    if 'canonical' in value:
                        skill_count += 1
                        if 'priority' in value:
                            stats['by_priority'][value['priority']] += 1
                    else:
                        skill_count += count_recursive(value, key)

        return skill_count

    for category, content in catalog.items():
        if category == 'config':
            continue

        stats['total_categories'] += 1
        count = count_recursive(content, category)
        stats['by_category'][category] = count
        stats['total_skills'] += count

    return stats

def print_summary(stats: dict):
    """Imprime resumo do catálogo"""
    print("\n" + "="*60)
    print("SKILLS CATALOG SUMMARY")
    print("="*60)

    print(f"\n📊 Estatísticas Gerais:")
    print(f"   Total de Categorias: {stats['total_categories']}")
    print(f"   Total de Skills:     {stats['total_skills']}")

    print(f"\n📈 Skills por Prioridade:")
    for priority in ['high', 'medium', 'low']:
        count = stats['by_priority'].get(priority, 0)
        percentage = (count / stats['total_skills'] * 100) if stats['total_skills'] > 0 else 0
        bar = '█' * int(percentage / 5)
        print(f"   {priority.capitalize():<8} {count:>3} skills ({percentage:>5.1f}%) {bar}")

    print(f"\n🗂️  Skills por Categoria:")
    sorted_categories = sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True)

    for category, count in sorted_categories:
        percentage = (count / stats['total_skills'] * 100) if stats['total_skills'] > 0 else 0
        bar = '█' * int(percentage / 5)
        print(f"   {category:<30} {count:>3} skills ({percentage:>5.1f}%) {bar}")

    print("\n" + "="*60)

def main():
    catalog_path = Path(__file__).parent / 'skills_catalog.yaml'

    print(f"📂 Carregando catálogo: {catalog_path}")
    catalog = load_catalog(catalog_path)

    stats = count_skills(catalog)
    print_summary(stats)

    # Exemplos de skills
    print("\n💡 Exemplos de Skills no Catálogo:")
    print("\n   Cloud Platforms:")
    print("   • Azure Data Factory, Synapse, Databricks, Fabric")
    print("   • AWS Glue, Redshift, S3, EMR, Lambda")
    print("   • GCP BigQuery, Dataflow, Cloud Storage")

    print("\n   Data Processing:")
    print("   • Apache Spark, Kafka, Flink, Databricks")
    print("   • Delta Lake, Iceberg, Hudi")

    print("\n   Languages:")
    print("   • Python, SQL, Scala, Java, Go")

    print("\n   DevOps:")
    print("   • Docker, Kubernetes, Terraform, CI/CD")
    print("   • GitHub Actions, Jenkins, GitLab CI")

    print("\n   BI Tools:")
    print("   • Power BI, Tableau, Looker, Grafana")

    print("\n✅ Catálogo carregado com sucesso!\n")

if __name__ == '__main__':
    main()
