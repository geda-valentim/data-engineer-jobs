import os
import boto3
import requests
import shared
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------
# Logging basico (vai direto pro CloudWatch Logs)
# --------------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --------------------------------------------------
# Clients globais (reusados pela Lambda)
# --------------------------------------------------
s3_resource = boto3.resource("s3")
cloudwatch = boto3.client("cloudwatch")
sqs_client = boto3.client("sqs")

data_bright_api = shared.get_brightdata_api_key()

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def _parse_snapshot(raw_body: bytes, file_format: str) -> Tuple[int, Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Tenta interpretar o conteudo do snapshot para:
      - contar quantos registros vieram
      - pegar o primeiro item (para exemplo/log)
      - retornar todos os items para processamento

    Suporta:
      - json  -> array ou objeto unico
      - jsonl -> um JSON por linha

    Retorna:
      (count, first_item_dict_ou_None, all_items)
    """
    text = raw_body.decode("utf-8", errors="replace").strip()
    if not text:
        return 0, None, []

    try:
        if file_format == "jsonl":
            items = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        elif file_format == "json":
            data = json.loads(text)
            if isinstance(data, list):
                items = data
            else:
                items = [data]
        else:
            # formatos nao-JSON (csv, etc.) -> nao vamos tentar parsear
            return 0, None, []

        if not items:
            return 0, None, []

        return len(items), items[0], items

    except Exception as e:
        logger.warning("Nao consegui fazer parse do snapshot (%s): %s", file_format, e, exc_info=True)
        return 0, None, []


def _extract_unique_companies(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extrai companies unicas dos jobs.

    Retorna lista de dicts com company_id, company_url, company_name.
    Usa company_id como chave de deduplicacao.
    """
    seen = set()
    companies = []

    for item in items:
        company_id = item.get("company_id")
        company_url = item.get("company_url")
        company_name = item.get("company_name")

        # Precisa ter pelo menos company_id ou company_url
        if not company_id and not company_url:
            continue

        # Usa company_id como chave, ou URL se nao tiver ID
        key = company_id or company_url
        if key in seen:
            continue

        seen.add(key)
        companies.append({
            "company_id": company_id,
            "company_url": company_url,
            "company_name": company_name,
        })

    return companies


def _send_companies_to_sqs(companies: List[Dict[str, Any]], first_seen_at: str) -> int:
    """
    Envia companies para a fila SQS para serem buscadas.

    Retorna quantidade de mensagens enviadas.
    """
    queue_url = os.getenv("COMPANIES_QUEUE_URL")
    if not queue_url:
        logger.info("COMPANIES_QUEUE_URL nao configurada, pulando envio de companies")
        return 0

    sent_count = 0
    for company in companies:
        try:
            message = {
                "company_id": company.get("company_id"),
                "company_url": company.get("company_url"),
                "company_name": company.get("company_name"),
                "source": "job_ingestion",
                "first_seen_at": first_seen_at,
            }

            sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message),
            )
            sent_count += 1

        except Exception as e:
            logger.warning(
                "Erro ao enviar company %s para SQS: %s",
                company.get("company_id") or company.get("company_url"),
                e,
            )

    if sent_count > 0:
        logger.info("Enviadas %d companies para SQS", sent_count)

    return sent_count


def _put_metric(namespace: str, name: str, value: float, dimensions: Optional[Dict[str, str]] = None):
    """
    Envia uma metrica simples para o CloudWatch Metrics.
    Da pra usar depois em dashboards/alarms.
    """
    dims = []
    if dimensions:
        for k, v in dimensions.items():
            if v is None:
                continue
            dims.append({"Name": k, "Value": str(v)})

    try:
        cloudwatch.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": name,
                    "Value": value,
                    "Unit": "Count",
                    "Dimensions": dims,
                }
            ],
        )
        logger.info(
            "✅ Métrica enviada para CloudWatch: %s/%s = %s (dims=%s)",
            namespace,
            name,
            value,
            dimensions,
        )
    except Exception as e:
        logger.warning("❌ Erro ao enviar métrica para o CloudWatch: %s", e, exc_info=True)


# --------------------------------------------------
# Lambda handler
# --------------------------------------------------
def save_to_s3(event, context):
    """
    Lambda responsável por:
      1. Buscar snapshot no Bright Data
      2. Salvar conteúdo bruto no bucket Bronze (particionado)
      3. Retornar metadados úteis pro Step Functions
      4. Enviar métrica de quantidade de registros pro CloudWatch

    Espera no event:
      - snapshot_id   (obrigatório)
      - bronze_prefix (ex: "linkedin")
      - file_format   (opcional) ex: "jsonl" | "json"
    """

    logger.info("📥 Evento recebido: %s", json.dumps(event))

    snapshot_id = event.get("snapshot_id")
    bronze_prefix = event.get("bronze_prefix")
    file_format = event.get("file_format", "jsonl")

    if not snapshot_id:
        raise ValueError(f"snapshot_id não encontrado no event: {event}")

    if not bronze_prefix:
        raise ValueError("bronze_prefix não encontrado no event (ex: 'linkedin').")

    bucket_name = shared.get_bronze_bucket_name()

    if not bucket_name:
        raise ValueError(
            "bronze_bucket_name não está configurado. "
            "shared.get_bronze_bucket_name() retornou vazio."
        )

    # --------------------------------------------------
    # Estrutura de data/hora para particionamento
    # --------------------------------------------------
    # Assumindo que shared.get_current_date_structure() devolve algo como:
    # { "year": 2025, "month": 12, "day": 3, "hour": 14 }
    curdate = shared.get_current_date_structure()
    year = int(curdate["year"])
    month = int(curdate["month"])
    day = int(curdate["day"])
    hour = int(curdate["hour"])

    # Strings zero-padded (pra ficar bonitinho e consistente com Glue)
    year_str = f"{year:04d}"
    month_str = f"{month:02d}"
    day_str = f"{day:02d}"
    hour_str = f"{hour:02d}"

    # Caminho final do arquivo no Bronze (compatível com o Glue job)
    # s3://bucket/bronze_prefix/year=YYYY/month=MM/day=DD/hour=HH/bright-data-<snapshot>.jsonl
    key = (
        f"{bronze_prefix}/"
        f"year={year_str}/month={month_str}/day={day_str}/hour={hour_str}/"
        f"bright-data-{snapshot_id}.{file_format}"
    )

    # --------------------------------------------------
    # Bright Data: baixa o snapshot
    # --------------------------------------------------
    url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
    headers = {
        "Authorization": f"Bearer {data_bright_api}",
    }

    logger.info("🌐 Buscando snapshot Bright Data: %s", url)

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    raw_body = response.content
    content_length = len(raw_body)
    logger.info("📦 Snapshot baixado com %d bytes", content_length)

    # --------------------------------------------------
    # Faz um parse leve pra ter contagem, 1o registro e todos items
    # --------------------------------------------------
    record_count, first_item, all_items = _parse_snapshot(raw_body, file_format)

    # Tenta pegar alguns campos do 1o job (quando existir)
    first_job_title = None
    first_company_name = None
    search_url = None

    if isinstance(first_item, dict):
        first_job_title = first_item.get("job_title")
        first_company_name = first_item.get("company_name")
        # Bright Data costuma mandar discovery_input.url com a URL da busca
        discovery = first_item.get("discovery_input") or {}
        search_url = discovery.get("url")

    logger.info(
        "Snapshot parseado: records=%s, first_job_title=%s, first_company_name=%s",
        record_count,
        first_job_title,
        first_company_name,
    )

    # --------------------------------------------------
    # Salva bruto no S3 (camada Bronze)
    # --------------------------------------------------
    try:
        s3_resource.Object(bucket_name, key).put(Body=raw_body)
        logger.info("✅ Arquivo salvo em s3://%s/%s", bucket_name, key)
    except Exception as e:
        logger.error("❌ Erro ao fazer upload para S3: %s", e, exc_info=True)
        raise

    # --------------------------------------------------
    # Envia metrica pro CloudWatch (pra dashboard/alarme)
    # --------------------------------------------------
    try:
        _put_metric(
            namespace="LinkedInJobs",
            name="JobCount",
            value=float(record_count),
            dimensions={
                "BronzePrefix": bronze_prefix,
                "FileFormat": file_format,
            },
        )
    except Exception:
        # Ja loga dentro do helper; nao quebra a Lambda
        pass

    # --------------------------------------------------
    # Envia companies para SQS (para serem buscadas)
    # --------------------------------------------------
    companies_sent = 0
    if all_items:
        try:
            unique_companies = _extract_unique_companies(all_items)
            first_seen_at = f"{year_str}-{month_str}-{day_str}T{hour_str}:00:00Z"
            companies_sent = _send_companies_to_sqs(unique_companies, first_seen_at)
        except Exception as e:
            # Nao quebra a Lambda se falhar envio de companies
            logger.warning("Erro ao enviar companies para SQS: %s", e, exc_info=True)

    status = "SAVED_EMPTY" if record_count == 0 else "SAVED"

    result = {
        "bucket": bucket_name,
        "key": key,
        "snapshot_id": snapshot_id,
        "status": status,
        "file_format": file_format,
        "content_length_bytes": content_length,
        "record_count": record_count,
        # particionamento (usado pelo Step Functions -> Glue)
        "source_system": bronze_prefix,
        "year": year_str,
        "month": month_str,
        "day": day_str,
        "hour": hour_str,
        # Exemplos para debug / observabilidade
        "example_job_title": first_job_title,
        "example_company_name": first_company_name,
        "search_url": search_url,
        # Companies enviadas para busca
        "companies_sent_to_sqs": companies_sent,
    }

    logger.info("Retorno para Step Functions: %s", json.dumps(result, ensure_ascii=False))
    return result


# --------------------------------------------------
# Execução local para teste (python save_to_s3.py)
# --------------------------------------------------
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_event = {
        "snapshot_id": "sd_mipj1e7waxj8rrarm",
        "attempts": 1,
        "source_id": "linkedin_brightdata_jobs_data_engineer_worldwide",
        "dataset_id": "gd_lpfll7v5hcqtkxl6l",
        "domain": "linkedin",
        "entity": "jobs",
        "bronze_prefix": "linkedin",
        "file_format": "jsonl",
        "status": "READY",
        "provider_status": "ready"
    }

    print(save_to_s3(test_event, None))
