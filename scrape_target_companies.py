from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import gspread
import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ============================================================
# Configuration
# ============================================================

ACTOR_ID = "harvestapi~linkedin-company-employees"
TARGET_COMPANIES_SHEET = "Target Companies"
TARGET_PROFILES_SHEET = "Target Profiles"

FUNCTION_IDS = ["25", "4"]  # 25 = Sales, 4 = Business Development
LOCATION = "Hong Kong SAR"
PROFILE_SCRAPER_MODE = "Full ($8 per 1k)"
RECENTLY_CHANGED_JOBS = False

MAX_PROFILES = 0  # 0 = all available profiles (subject to Actor/LinkedIn limits)
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_MAX_COMPANIES_PER_RUN = 50
MAX_RETRIES = 3

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MARKDOWN_LINK_RE = re.compile(
    r"\[[^\]]*\]\((https?://[^)\s]+)\)", re.IGNORECASE
)
HYPERLINK_FORMULA_RE = re.compile(
    r'=HYPERLINK\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
RAW_LINKEDIN_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/company/[^\s<>\]\)\"']+",
    re.IGNORECASE,
)


# ============================================================
# Generic helpers
# ============================================================

def fail(message: str) -> None:
    raise RuntimeError(message)


def text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def nested_text(obj: Any, *keys: str) -> str:
    data = safe_dict(obj)
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return text_value(value)
    return ""


def date_text(value: Any) -> str:
    if isinstance(value, dict):
        return text_value(value.get("text") or value.get("date") or value.get("value"))
    return text_value(value)


def sanitize_error_text(value: str, token: str | None = None) -> str:
    text = value or ""
    if token:
        text = text.replace(token, "***REDACTED***")
    return text[:6000]


# ============================================================
# LinkedIn URL extraction / normalization
# ============================================================

def extract_linkedin_url(value: Any) -> str | None:
    """
    Accept:
      - raw LinkedIn company URL
      - Markdown hyperlink
      - HYPERLINK() formula
      - a string containing a LinkedIn company URL
    """
    text = text_value(value)
    if not text:
        return None

    markdown_match = MARKDOWN_LINK_RE.search(text)
    if markdown_match:
        text = markdown_match.group(1)

    formula_match = HYPERLINK_FORMULA_RE.search(text)
    if formula_match:
        text = formula_match.group(1)

    raw_match = RAW_LINKEDIN_RE.search(text)
    if raw_match:
        text = raw_match.group(0)

    text = text.strip().strip("'\"")
    return text if text.lower().startswith(("http://", "https://")) else None


def normalize_company_url(value: Any) -> str | None:
    """
    Canonical representation used for matching:
      https://www.linkedin.com/company/<slug>/
    """
    url = extract_linkedin_url(value)
    if not url:
        return None

    parsed = urlsplit(url.strip())
    host = parsed.netloc.lower().split(":", 1)[0]
    if host == "www.linkedin.com":
        host = "linkedin.com"

    if host != "linkedin.com":
        return None

    path = unquote(parsed.path).strip()
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2 or parts[0].lower() != "company":
        return None

    slug = parts[1].strip().lower()
    if not slug:
        return None

    return f"https://www.linkedin.com/company/{slug}/"


# ============================================================
# Google Sheets
# ============================================================

def load_configuration() -> tuple[str, str]:
    load_dotenv(dotenv_path=ENV_PATH)

    apify_token = text_value(os.getenv("APIFY_TOKEN"))
    sheet_id = text_value(os.getenv("DEFAULT_GOOGLE_SHEET_ID"))

    if not apify_token:
        fail(
            f"APIFY_TOKEN is missing. Expected it in {ENV_PATH}. "
            "Do not paste the token into the Python file."
        )

    if not sheet_id:
        fail(
            f"DEFAULT_GOOGLE_SHEET_ID is missing. Expected it in {ENV_PATH}."
        )

    if not CREDENTIALS_PATH.exists():
        fail(
            f"credentials.json not found at {CREDENTIALS_PATH}. "
            "Place the Google service-account file beside this script."
        )

    return apify_token, sheet_id


def authenticate_google(sheet_id: str):
    creds = Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES,
    )
    gc = gspread.authorize(creds)
    sheets_service = build("sheets", "v4", credentials=creds)
    spreadsheet = gc.open_by_key(sheet_id)
    return gc, sheets_service, spreadsheet


def read_target_company_urls(spreadsheet, sheets_service) -> list[str]:
    """
    Read the actual hyperlink URL when Google Sheets exposes it.
    Falls back to formulas / raw URL text.
    This avoids sending Markdown display syntax to Apify.
    """
    try:
        worksheet = spreadsheet.worksheet(TARGET_COMPANIES_SHEET)
    except gspread.WorksheetNotFound:
        fail(f"Worksheet '{TARGET_COMPANIES_SHEET}' not found.")

    try:
        data = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet.id,
            includeGridData=True,
            ranges=[TARGET_COMPANIES_SHEET],
            fields="sheets(data(rowData(values(hyperlink,userEnteredValue,effectiveValue))))",
        ).execute()
    except Exception:
        # Fallback to gspread values if the grid-data request fails.
        rows = worksheet.get_all_values()
        return read_target_company_urls_from_values(rows)
    sheets = data.get("sheets", [])
    if not sheets:
        return []

    row_data = sheets[0].get("data", [{}])[0].get("rowData", [])
    if not row_data:
        return []

    header_cells = row_data[0].get("values", [])

    linkedin_col = None
    for idx, cell in enumerate(header_cells):
        header = (
            safe_dict(cell.get("effectiveValue"))
            .get("stringValue")
            or safe_dict(cell.get("userEnteredValue"))
            .get("stringValue")
            or ""
        )
        header_lower = text_value(header).lower()
        if "linkedin" in header_lower or "company url" in header_lower:
            linkedin_col = idx
            break

    if linkedin_col is None:
        # Fallback because some Sheets cells may have no effectiveValue metadata.
        rows = worksheet.get_all_values()
        return read_target_company_urls_from_values(rows)

    company_urls: list[str] = []
    seen: set[str] = set()

    for row_number, row in enumerate(row_data[1:], start=2):
        cells = row.get("values", [])
        cell = cells[linkedin_col] if linkedin_col < len(cells) else {}

        candidate = (
            cell.get("hyperlink")
            or safe_dict(cell.get("userEnteredValue")).get("formulaValue")
            or safe_dict(cell.get("effectiveValue")).get("stringValue")
        )

        raw_url = extract_linkedin_url(candidate)
        normalized = normalize_company_url(raw_url)

        if not normalized:
            if text_value(candidate):
                print(
                    f"WARNING: Row {row_number} in '{TARGET_COMPANIES_SHEET}' "
                    "does not contain a valid LinkedIn company URL; skipped."
                )
            continue

        if normalized not in seen:
            seen.add(normalized)
            company_urls.append(normalized)

    return company_urls


def read_target_company_urls_from_values(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []

    headers = [text_value(x).lower() for x in rows[0]]
    linkedin_col = None

    for idx, header in enumerate(headers):
        if "linkedin" in header or "company url" in header:
            linkedin_col = idx
            break

    if linkedin_col is None:
        fail(
            f"Could not find a LinkedIn/company URL column in "
            f"'{TARGET_COMPANIES_SHEET}'."
        )

    company_urls: list[str] = []
    seen: set[str] = set()

    for row_number, row in enumerate(rows[1:], start=2):
        value = row[linkedin_col] if linkedin_col < len(row) else ""
        normalized = normalize_company_url(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            company_urls.append(normalized)

    return company_urls


# ============================================================
# Apify
# ============================================================

def build_apify_payload(company_urls: list[str]) -> dict[str, Any]:
    """Build the exact Apify input for an exhaustive profile run."""
    return {
        "companies": company_urls,
        "companyBatchMode": "one_by_one",
        "functionIds": FUNCTION_IDS,
        "locations": [LOCATION],
        "maxItems": MAX_PROFILES,
        "profileScraperMode": PROFILE_SCRAPER_MODE,
        "recentlyChangedJobs": RECENTLY_CHANGED_JOBS,
    }


def apify_get_actor_metadata(session: requests.Session, token: str) -> None:
    endpoint = f"https://api.apify.com/v2/acts/{ACTOR_ID}"
    response = session.get(
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if response.status_code >= 400:
        detail = sanitize_error_text(response.text, token)
        fail(
            f"Apify token / actor access check failed: "
            f"HTTP {response.status_code}\n{detail}"
        )


def call_apify(
    session: requests.Session,
    token: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    endpoint = (
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/"
        "run-sync-get-dataset-items"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    timeout_seconds = int(
        os.getenv("APIFY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Calling Apify Actor (attempt {attempt}/{MAX_RETRIES})...")

        try:
            response = session.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=timeout_seconds,
            )
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                fail(f"Apify network error after {MAX_RETRIES} attempts: {exc}")
            sleep_seconds = 2 ** (attempt - 1)
            print(f"Network error; retrying in {sleep_seconds}s...")
            time.sleep(sleep_seconds)
            continue

        if 200 <= response.status_code < 300:
            try:
                data = response.json()
            except ValueError:
                fail(
                    "Apify returned a non-JSON success response:\n"
                    + sanitize_error_text(response.text, token)
                )

            if isinstance(data, list):
                profiles = data
            elif isinstance(data, dict) and isinstance(data.get("items"), list):
                profiles = data["items"]
            else:
                fail(
                    "Unexpected Apify response shape:\n"
                    + sanitize_error_text(json.dumps(data), token)
                )

            return [item for item in profiles if isinstance(item, dict)]

        retryable = response.status_code in {
            408, 429, 500, 502, 503, 504
        }

        detail = sanitize_error_text(response.text, token)

        if not retryable:
            fail(
                f"Apify request failed: HTTP {response.status_code}\n{detail}"
            )

        if attempt == MAX_RETRIES:
            fail(
                f"Apify request failed after {MAX_RETRIES} attempts: "
                f"HTTP {response.status_code}\n{detail}"
            )

        retry_after = response.headers.get("Retry-After")
        try:
            sleep_seconds = max(1, int(retry_after)) if retry_after else 2 ** (attempt - 1)
        except ValueError:
            sleep_seconds = 2 ** (attempt - 1)

        print(
            f"Retryable Apify response HTTP {response.status_code}; "
            f"retrying in {sleep_seconds}s..."
        )
        time.sleep(sleep_seconds)

    fail("Unreachable Apify retry state.")


# ============================================================
# Profile matching / parsing
# ============================================================

def get_current_position_details(profile: dict[str, Any]) -> tuple[str, str]:
    """Return the first usable current-position company name and title."""
    positions = safe_list(profile.get("currentPosition"))

    for position in positions:
        pos = safe_dict(position)
        company_name = nested_text(pos, "companyName", "company", "name")
        title = nested_text(pos, "position", "title", "jobTitle")
        if company_name or title:
            return company_name, title

    return "", ""


def profile_picture_formula(profile: dict[str, Any]) -> str:
    candidates = []

    for key in ("profilePicture", "photo"):
        value = profile.get(key)
        if isinstance(value, dict):
            candidates.extend(
                [
                    value.get("url"),
                    value.get("displayImageUrl"),
                    value.get("displayImage"),
                ]
            )
        elif isinstance(value, str):
            candidates.append(value)

    for candidate in candidates:
        url = text_value(candidate)
        if url.lower().startswith(("http://", "https://")):
            escaped_url = url.replace('"', '""')
            return f'=IMAGE("{escaped_url}")'

    return "no picture"


def format_work_experience(profile: dict[str, Any]) -> str:
    lines: list[str] = []

    for exp in safe_list(profile.get("experience")):
        if not isinstance(exp, dict):
            continue

        position = nested_text(exp, "position", "title")
        company_name = nested_text(exp, "companyName", "company")
        start_text = date_text(exp.get("startDate"))
        end_text = date_text(exp.get("endDate"))
        duration = text_value(exp.get("duration"))
        description = text_value(exp.get("description"))

        date_range = f"{start_text} - {end_text}"
        if duration:
            date_range += f" | {duration}"

        line = f"[{position}] at [{company_name}] ({date_range})"
        if description:
            line += f"\nDescription: {description}"

        lines.append(line)

    return "\n\n".join(lines)


def format_top_education(profile: dict[str, Any]) -> str:
    education_value = profile.get("profileTopEducation")
    education = safe_list(education_value)

    if not education:
        education = safe_list(profile.get("education"))

    if not education:
        return ""

    edu = safe_dict(education[0])

    degree = nested_text(edu, "degree")
    field = nested_text(edu, "fieldOfStudy")
    school = nested_text(edu, "schoolName")
    start_text = date_text(edu.get("startDate"))
    end_text = date_text(edu.get("endDate"))

    parts: list[str] = []

    if degree:
        parts.append(degree)
    if field:
        parts.append(f"in {field}")
    if school:
        parts.append(f"at {school}")
    if start_text or end_text:
        parts.append(f"({start_text} - {end_text})")

    return " ".join(parts)


def format_profile(profile: dict[str, Any]) -> dict[str, str]:
    first_name = text_value(profile.get("firstName"))
    last_name = text_value(profile.get("lastName"))
    name = f"{first_name} {last_name}".strip()

    linkedin_url = text_value(
        profile.get("linkedinUrl") or profile.get("profileUrl")
    )

    current_company, title = get_current_position_details(profile)

    return {
        "linkedin_url": linkedin_url,
        "name": name,
        "profile_picture": profile_picture_formula(profile),
        "current_company": current_company,
        "title": title,
        "work_experience": format_work_experience(profile),
        "top_education": format_top_education(profile),
    }



# ============================================================
# Google Sheets output
# ============================================================

def ensure_sheet_size(worksheet, min_rows: int, min_cols: int = 7) -> None:
    if worksheet.row_count < min_rows:
        worksheet.add_rows(min_rows - worksheet.row_count)
    if worksheet.col_count < min_cols:
        worksheet.add_cols(min_cols - worksheet.col_count)


def write_target_profiles(
    spreadsheet,
    sheets_service,
    sheet_id: str,
    formatted_profiles: list[dict[str, str]],
) -> str:
    try:
        profiles_sheet = spreadsheet.worksheet(TARGET_PROFILES_SHEET)
    except gspread.WorksheetNotFound:
        profiles_sheet = spreadsheet.add_worksheet(
            title=TARGET_PROFILES_SHEET,
            rows=max(1000, len(formatted_profiles) + 10),
            cols=7,
        )

    ensure_sheet_size(profiles_sheet, max(100, len(formatted_profiles) + 1), 7)

    # Only modify the output sheet after Apify has succeeded and parsing is complete.
    profiles_sheet.clear()

    headers = [
        "Linkedin URL",
        "Name",
        "Profile Picture",
        "Current Company",
        "Title",
        "Work Experience History",
        "Top Education",
    ]

    data_rows = [
        [
            item["linkedin_url"],
            item["name"],
            item["profile_picture"],
            item["current_company"],
            item["title"],
            item["work_experience"],
            item["top_education"],
        ]
        for item in formatted_profiles
    ]

    profiles_sheet.update(
        range_name="A1:G1",
        values=[headers],
        value_input_option="USER_ENTERED",
    )

    if data_rows:
        profiles_sheet.update(
            range_name=f"A2:G{len(data_rows) + 1}",
            values=data_rows,
            value_input_option="USER_ENTERED",
        )

    sheet_gid = profiles_sheet.id
    requests_body: list[dict[str, Any]] = []

    # Data row height: 120 px
    if data_rows:
        requests_body.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_gid,
                        "dimension": "ROWS",
                        "startIndex": 1,
                        "endIndex": len(data_rows) + 1,
                    },
                    "properties": {"pixelSize": 120},
                    "fields": "pixelSize",
                }
            }
        )

    # Work Experience (F) and Top Education (G): 610 px
    for col_index in (5, 6):
        requests_body.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_gid,
                        "dimension": "COLUMNS",
                        "startIndex": col_index,
                        "endIndex": col_index + 1,
                    },
                    "properties": {"pixelSize": 610},
                    "fields": "pixelSize",
                }
            }
        )

    # Wrap + top alignment for F/G
    for col_index in (5, 6):
        requests_body.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_gid,
                        "startRowIndex": 1,
                        "startColumnIndex": col_index,
                        "endColumnIndex": col_index + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "wrapStrategy": "WRAP",
                            "verticalAlignment": "TOP",
                        }
                    },
                    "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
                }
            }
        )

    # Top alignment for all data cells
    if data_rows:
        requests_body.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_gid,
                        "startRowIndex": 1,
                        "endRowIndex": len(data_rows) + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 7,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "verticalAlignment": "TOP"
                        }
                    },
                    "fields": "userEnteredFormat.verticalAlignment",
                }
            }
        )

    # Header formatting
    requests_body.extend(
        [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_gid,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 7,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat.textFormat.bold,userEnteredFormat.verticalAlignment",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_gid,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]
    )

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": requests_body},
    ).execute()

    return profiles_sheet.url



# ============================================================
# Preflight / execution
# ============================================================

def print_manifest(company_urls: list[str], payload: dict[str, Any]) -> None:
    print("\n=== EXECUTION MANIFEST ===")
    print(f"Target companies: {len(company_urls)}")
    for idx, url in enumerate(company_urls, start=1):
        print(f"  {idx}. {url}")

    print("\nApify configuration:")
    print("  Actor: harvestapi/linkedin-company-employees")
    print(f"  Batch mode: {payload['companyBatchMode']}")
    print(f"  Max profiles: {payload['maxItems']} (0 = all available)")
    print(f"  Location: {LOCATION}")
    print(f"  Function IDs: {FUNCTION_IDS} (Sales + Business Development)")
    print(f"  Profile mode: {PROFILE_SCRAPER_MODE}")
    print(f"  Recently changed jobs: {RECENTLY_CHANGED_JOBS}")
    print("===========================\n")


def run(preflight_only: bool = False, dry_run: bool = False) -> int:
    apify_token, sheet_id = load_configuration()
    _, sheets_service, spreadsheet = authenticate_google(sheet_id)

    company_urls = read_target_company_urls(spreadsheet, sheets_service)

    if not company_urls:
        fail(
            f"No valid LinkedIn company URLs were found in "
            f"'{TARGET_COMPANIES_SHEET}'. Nothing was run."
        )

    max_companies = int(
        os.getenv(
            "MAX_COMPANIES_PER_RUN",
            DEFAULT_MAX_COMPANIES_PER_RUN,
        )
    )
    if len(company_urls) > max_companies:
        fail(
            f"Safety stop: {len(company_urls)} companies exceeds "
            f"MAX_COMPANIES_PER_RUN={max_companies}. "
            "No Apify run was started."
        )

    payload = build_apify_payload(company_urls)
    print_manifest(company_urls, payload)

    session = requests.Session()

    # Preflight API token/actor access check; this does NOT run the Actor.
    print("Preflight: checking Apify token and Actor access (no Actor run)...")
    apify_get_actor_metadata(session, apify_token)
    print("Preflight: Apify access OK.")

    if preflight_only or dry_run:
        print(
            "\nNo Apify Actor run was started. "
            "No scraping charge was triggered by this script."
        )
        if dry_run:
            print("\nPayload:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    profiles = call_apify(session, apify_token, payload)
    print(f"Received {len(profiles)} profiles from Apify.")

    if not profiles:
        fail(
            "Apify returned 0 profiles. Existing 'Target Profiles' sheet "
            "was left untouched."
        )

    # Keep every profile returned by Apify, preserving dataset order.
    formatted_profiles = [format_profile(profile) for profile in profiles]
    print(f"Writing all {len(formatted_profiles)} returned profiles in Apify dataset order.")

    sheet_url = write_target_profiles(
        spreadsheet=spreadsheet,
        sheets_service=sheets_service,
        sheet_id=sheet_id,
        formatted_profiles=formatted_profiles,
    )

    print("\n=== COMPLETED ===")
    print(f"Target companies fetched: {len(company_urls)}")
    print(f"Profiles returned by Apify: {len(profiles)}")
    print(f"Profiles saved to '{TARGET_PROFILES_SHEET}': {len(formatted_profiles)}")
    print("Exhaustive mode: maxItems=0 (all available, subject to Actor/LinkedIn limits)")
    print(f"Google Sheet: {sheet_url}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an exhaustive LinkedIn talent-mapping scrape and write all returned profiles."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run preflight checks only; do not start Apify Actor.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print payload; do not start Apify Actor.",
    )
    args = parser.parse_args()

    try:
        return run(
            preflight_only=args.check,
            dry_run=args.dry_run,
        )
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
