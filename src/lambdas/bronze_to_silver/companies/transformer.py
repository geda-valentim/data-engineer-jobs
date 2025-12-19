"""
Transformer for LinkedIn Companies Bronze to Silver conversion.

Handles JSON to flat row transformation with proper type handling,
JSON serialization of nested arrays, and derived field computation.

Partitioning: Uses bucket hash (MD5) with 50 buckets for even distribution.
"""

import json
import re
from datetime import datetime, date, timezone
from typing import Any, Optional

# Handle imports for both Lambda (flat structure) and local execution (package structure)
try:
    # Lambda execution - flat structure
    from schema import compute_bucket
except ImportError:
    # Local execution - package structure
    from .schema import compute_bucket


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely convert a value to int."""
    if value is None:
        return default
    try:
        # Handle float company_ids like "1001344.0"
        if isinstance(value, str) and "." in value:
            return int(float(value))
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: Optional[str] = None) -> Optional[str]:
    """Safely convert a value to string."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() if value.strip() else default
    return str(value)


def safe_json(value: Any) -> Optional[str]:
    """Safely serialize a value to JSON string."""
    if value is None:
        return None
    if isinstance(value, list) and len(value) == 0:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return None


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Parse ISO format datetime string to datetime object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if not isinstance(value, str):
        return None

    try:
        # Handle various ISO formats
        value = value.strip()

        # Remove trailing 'Z' and add UTC
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        # Try parsing with timezone
        try:
            dt = datetime.fromisoformat(value)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            pass

        # Try common formats
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None
    except Exception:
        return None


def parse_date(value: Any) -> Optional[date]:
    """Parse date from various formats."""
    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    if not isinstance(value, str):
        return None

    try:
        # Try ISO format first
        dt = parse_iso_datetime(value)
        if dt:
            return dt.date()

        # Try date-only format
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def extract_snapshot_date(filename: str) -> Optional[date]:
    """Extract snapshot date from filename like 'snapshot_2025-12-08.json'."""
    match = re.search(r"snapshot_(\d{4}-\d{2}-\d{2})", filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def compute_latest_update_date(updates: Optional[list]) -> Optional[datetime]:
    """Find the most recent update date from updates array."""
    if not updates or not isinstance(updates, list):
        return None

    latest = None
    for update in updates:
        if isinstance(update, dict) and "date" in update:
            dt = parse_iso_datetime(update["date"])
            if dt and (latest is None or dt > latest):
                latest = dt

    return latest


def transform_company(
    raw_data: dict[str, Any],
    snapshot_filename: str,
    processed_at: Optional[datetime] = None
) -> dict[str, Any]:
    """
    Transform raw LinkedIn company JSON to Silver schema format.

    Args:
        raw_data: Raw company JSON data from Bronze layer
        snapshot_filename: Name of the source file (for extracting snapshot date)
        processed_at: Timestamp when processing occurred (defaults to now)

    Returns:
        Dictionary with Silver schema column values
    """
    if processed_at is None:
        processed_at = datetime.now(timezone.utc)

    # Extract snapshot date from filename
    snapshot_date = extract_snapshot_date(snapshot_filename)
    if snapshot_date is None:
        # Fall back to timestamp field or today
        scraped_at = parse_iso_datetime(raw_data.get("timestamp"))
        snapshot_date = scraped_at.date() if scraped_at else date.today()

    # Extract funding info
    funding = raw_data.get("funding") or {}
    has_funding_info = bool(funding and isinstance(funding, dict) and any(funding.values()))

    # Get nested arrays
    employees = raw_data.get("employees")
    similar = raw_data.get("similar")
    affiliated = raw_data.get("affiliated")
    updates = raw_data.get("updates")

    # Compute derived fields
    employees_count = len(employees) if isinstance(employees, list) else None
    similar_count = len(similar) if isinstance(similar, list) else None
    affiliated_count = len(affiliated) if isinstance(affiliated, list) else None
    updates_count = len(updates) if isinstance(updates, list) else None
    latest_update_date = compute_latest_update_date(updates)

    # Get company_id for bucket calculation
    company_id = safe_str(raw_data.get("company_id"))

    return {
        # Partition Key (must be first)
        "bucket": compute_bucket(company_id) if company_id else 0,

        # Core Identifiers
        "company_id": company_id,
        "linkedin_id": safe_str(raw_data.get("id")),
        "name": safe_str(raw_data.get("name")),
        "slogan": safe_str(raw_data.get("slogan")),
        "headquarters": safe_str(raw_data.get("headquarters")),
        "country_code": safe_str(raw_data.get("country_code")),
        "website": safe_str(raw_data.get("website")),
        "website_domain": safe_str(raw_data.get("website_simplified")),
        "linkedin_url": safe_str(raw_data.get("url")),

        # Company Info
        "about": safe_str(raw_data.get("about")),
        "industries": safe_str(raw_data.get("industries")),
        "specialties": safe_str(raw_data.get("specialties")),
        "organization_type": safe_str(raw_data.get("organization_type")),
        "company_size": safe_str(raw_data.get("company_size")),
        "founded_year": safe_int(raw_data.get("founded")),

        # Metrics
        "followers": safe_int(raw_data.get("followers")),
        "employees_on_linkedin": safe_int(raw_data.get("employees_in_linkedin")),

        # Location (JSON arrays)
        "locations_json": safe_json(raw_data.get("locations")),
        "formatted_locations_json": safe_json(raw_data.get("formatted_locations")),
        "country_codes_json": safe_json(raw_data.get("country_codes_array")),

        # Media
        "logo_url": safe_str(raw_data.get("logo")),
        "cover_image_url": safe_str(raw_data.get("image")),

        # Funding
        "funding_last_round_date": parse_date(funding.get("last_round_date")),
        "funding_last_round_type": safe_str(funding.get("last_round_type")),
        "funding_rounds_count": safe_int(funding.get("rounds")),
        "funding_last_round_amount": safe_str(funding.get("last_round_raised")),

        # External Links
        "crunchbase_url": safe_str(raw_data.get("crunchbase_url")),

        # Nested Data as JSON
        "employees_json": safe_json(employees),
        "similar_companies_json": safe_json(similar),
        "affiliated_pages_json": safe_json(affiliated),
        "updates_json": safe_json(updates),

        # Derived Fields
        "employees_featured_count": employees_count,
        "similar_companies_count": similar_count,
        "affiliated_pages_count": affiliated_count,
        "updates_count": updates_count,
        "has_funding_info": has_funding_info,
        "latest_update_date": latest_update_date,

        # Metadata
        "snapshot_date": snapshot_date,
        "scraped_at": parse_iso_datetime(raw_data.get("timestamp")),
        "source_url": safe_str((raw_data.get("input") or {}).get("url")),
        "processed_at": processed_at,
    }


def transform_companies_batch(
    companies: list[tuple[dict[str, Any], str]],
    processed_at: Optional[datetime] = None
) -> list[dict[str, Any]]:
    """
    Transform a batch of companies.

    Args:
        companies: List of (raw_data, snapshot_filename) tuples
        processed_at: Timestamp when processing occurred

    Returns:
        List of transformed company dictionaries
    """
    if processed_at is None:
        processed_at = datetime.now(timezone.utc)

    return [
        transform_company(raw_data, filename, processed_at)
        for raw_data, filename in companies
    ]
