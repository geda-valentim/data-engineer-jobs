
from dotenv import load_dotenv
import pendulum
import os 
import boto3
from functools import lru_cache

load_dotenv()

destiny_folder = "linkedin/jobs-listing"

ssm = boto3.client("ssm")


@lru_cache
def get_brightdata_api_key() -> str:
    api_key = os.getenv("BRIGHTDATA_API_KEY")
    if api_key:
        return api_key

    param_name = os.getenv("BRIGHTDATA_API_KEY_PARAM")
    if not param_name:
        raise RuntimeError(
            "Nenhuma cred configurada. "
            "Defina BRIGHTDATA_API_KEY (local) ou BRIGHTDATA_API_KEY_PARAM (AWS)."
        )

    ssm = boto3.client("ssm")
    resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
    return resp["Parameter"]["Value"]

def get_current_date_structure():
    tz_string = os.getenv("APP_TIMEZONE", "UTC")
    now = pendulum.now(tz_string)

    return {
        "year": f"{now.year:04d}",
        "month": f"{now.month:02d}",
        "day": f"{now.day:02d}",
        "hour": f"{now.hour:02d}",
        "full_date": now.to_datetime_string(),
        "timezone": now.timezone.name,
    }


def get_bronze_bucket_name():
    return os.getenv('bronze_bucket_name')

def get_s3_folder_path():
    curdate = get_current_date_structure()
    return (
        f"year={curdate['year']}/"
        f"month={curdate['month']}/"
        f"day={curdate['day']}/"
        f"hour={curdate['hour']}"
    )

