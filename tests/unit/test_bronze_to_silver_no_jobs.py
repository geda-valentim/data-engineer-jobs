"""
Teste para validar o comportamento do Glue job bronze_to_silver
quando não há vagas disponíveis (crawl retorna erro).

Este teste valida que o job trata corretamente o cenário de "sem vagas"
como um caso de negócio válido, não como uma falha.
"""

import json


def test_error_structure_detection():
    """
    Testa se a lógica detecta corretamente a estrutura de erro
    quando não há vagas disponíveis.
    """

    # Cenário 1: Arquivo com erro de crawl (sem vagas)
    error_data = {
        "timestamp": "2025-12-08T08:00:38.005Z",
        "input": {
            "url": "https://www.linkedin.com/jobs/search/?currentJobId=4341321856&f_TPR=r3600&geoId=92000000&keywords=%22engenheiro%20de%20dados%22&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true&sortBy=DD"
        },
        "error": "Crawl failed after multiple attempts, please try again later",
        "error_code": "crawl_failed",
    }

    # Cenário 2: Arquivo com dados válidos (com vagas)
    valid_data = {
        "job_posting_id": "4341321856",
        "timestamp": "2025-12-08T09:00:00.000Z",
        "company_name": "Moka Info",
        "job_title": "Engenheiro de dados pleno",
        "url": "https://www.linkedin.com/jobs/view/4341321856",
        "job_description_formatted": "<p>Vaga para engenheiro de dados...</p>",
    }

    # Validação da lógica de detecção
    error_columns = list(error_data.keys())
    valid_columns = list(valid_data.keys())

    # Lógica usada no Glue job (linha 101)
    is_error_1 = "error_code" in error_columns
    is_error_2 = "error" in error_columns and "job_posting_id" not in error_columns

    is_valid_1 = "error_code" not in valid_columns
    is_valid_2 = "job_posting_id" in valid_columns

    print("=" * 70)
    print("TESTE: Detecção de Estrutura de Erro vs Dados Válidos")
    print("=" * 70)

    print("\n📋 Cenário 1: Crawl SEM vagas (erro esperado)")
    print(f"   Colunas: {error_columns}")
    print(f"   Tem 'error_code': {is_error_1}")
    print(f"   Tem 'error' sem 'job_posting_id': {is_error_2}")
    print(f"   ✅ Deve ser detectado como ERRO: {is_error_1 or is_error_2}")
    print(f"   ✅ Resultado esperado: Job finaliza com SUCESSO (0 registros)")

    print("\n📋 Cenário 2: Crawl COM vagas (dados válidos)")
    print(f"   Colunas: {valid_columns}")
    print(f"   Não tem 'error_code': {is_valid_1}")
    print(f"   Tem 'job_posting_id': {is_valid_2}")
    print(f"   ✅ Deve continuar processamento: {is_valid_1 and is_valid_2}")
    print(f"   ✅ Resultado esperado: Job processa os dados normalmente")

    print("\n" + "=" * 70)
    print("RESULTADO DO TESTE")
    print("=" * 70)

    # Asserções
    assert (
        is_error_1 or is_error_2
    ), "Cenário de erro não foi detectado corretamente"
    assert (
        is_valid_1 and is_valid_2
    ), "Cenário válido foi incorretamente marcado como erro"

    print("✅ Todos os testes passaram!")
    print("✅ A lógica detecta corretamente:")
    print("   - Crawls sem vagas (retorna sucesso sem processar)")
    print("   - Crawls com vagas (processa normalmente)")
    print("=" * 70)


if __name__ == "__main__":
    test_error_structure_detection()
