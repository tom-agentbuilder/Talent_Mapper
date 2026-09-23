from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"

TARGET_SHEET = "Target Profiles"
OUTPUT_SHEET = "Sales Manager Pipeline"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

INPUT_JSON = BASE_DIR / "target_profiles_llm_input.json"

OUTPUT_HEADERS = [
    "Linkedin URL",
    "Name",
    "Profile Picture",
    "Current Company",
    "Current Title",
    "Fit Type",
    "Promotion / Progression Signal",
    "Career Stage",
    "Previous Title",
    "Previous Company",
    "Reason",
    "Work Experience History",
    "Top Education",
]


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_config() -> str:
    load_dotenv(dotenv_path=ENV_PATH)

    sheet_id = text_value(os.getenv("DEFAULT_GOOGLE_SHEET_ID"))
    if not sheet_id:
        fail(f"DEFAULT_GOOGLE_SHEET_ID is missing from {ENV_PATH}")

    if not CREDENTIALS_PATH.exists():
        fail(f"credentials.json not found at {CREDENTIALS_PATH}")

    return sheet_id


def authenticate(sheet_id: str):
    creds = Credentials.from_service_account_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES,
    )
    gc = gspread.authorize(creds)
    sheets_service = build("sheets", "v4", credentials=creds)
    spreadsheet = gc.open_by_key(sheet_id)
    return gc, sheets_service, spreadsheet


def read_target_profiles(spreadsheet, sheets_service) -> list[dict[str, Any]]:
    try:
        spreadsheet.worksheet(TARGET_SHEET)
    except gspread.WorksheetNotFound:
        fail(f"Worksheet '{TARGET_SHEET}' not found.")

    values_result = (
        sheets_service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet.id,
            range=f"'{TARGET_SHEET}'!A1:G",
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    values = values_result.get("values", [])
    if not values:
        fail(f"'{TARGET_SHEET}' is empty.")

    formula_result = (
        sheets_service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet.id,
            range=f"'{TARGET_SHEET}'!A1:G",
            valueRenderOption="FORMULA",
        )
        .execute()
    )
    formula_values = formula_result.get("values", [])

    headers = [text_value(x) for x in values[0]]

    expected = [
        "Linkedin URL",
        "Name",
        "Profile Picture",
        "Current Company",
        "Title",
        "Work Experience History",
        "Top Education",
    ]
    missing = [h for h in expected if h not in headers]
    if missing:
        fail(
            "Missing expected columns in Target Profiles: "
            + ", ".join(missing)
        )

    records: list[dict[str, Any]] = []

    for idx, row in enumerate(values[1:], start=2):
        padded = row + [""] * max(0, len(headers) - len(row))
        record = {
            headers[col]: padded[col] if col < len(padded) else ""
            for col in range(len(headers))
        }

        if idx - 1 < len(formula_values):
            formula_row = formula_values[idx - 1]
            if len(formula_row) > 2 and str(formula_row[2]).startswith("=IMAGE("):
                record["Profile Picture"] = formula_row[2]

        if not any(text_value(v) for v in record.values()):
            continue

        record["_source_row"] = idx
        records.append(record)

    if not records:
        fail(f"No profile rows found in '{TARGET_SHEET}'.")

    return records


def export_profiles(spreadsheet, sheets_service) -> int:
    records = read_target_profiles(spreadsheet, sheets_service)

    payload = {
        "source_sheet": TARGET_SHEET,
        "profile_count": len(records),
        "columns": [
            "Linkedin URL",
            "Name",
            "Profile Picture",
            "Current Company",
            "Title",
            "Work Experience History",
            "Top Education",
        ],
        "profiles": records,
    }

    INPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Exported {len(records)} profiles.")
    print(f"LLM input file: {INPUT_JSON}")
    return 0


def validate_llm_output(
    raw: Any,
    source_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        fail("LLM output JSON must be a list.")

    by_row = {
        int(record["_source_row"]): record
        for record in source_records
    }

    seen_rows: set[int] = set()
    cleaned: list[dict[str, Any]] = []

    allowed_fit = {"Strong Fit", "Potential Fit", "Stretch Fit"}
    allowed_progression = {
        "Strong",
        "Possible",
        "Established",
        "None / Unclear",
    }

    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            fail(f"LLM output item {idx} is not an object.")

        source_row = item.get("source_row")
        if not isinstance(source_row, int):
            fail(f"LLM output item {idx} has invalid source_row.")

        if source_row not in by_row:
            fail(
                f"LLM output item {idx} references unknown source_row "
                f"{source_row}."
            )

        if source_row in seen_rows:
            fail(f"Duplicate source_row in LLM output: {source_row}")
        seen_rows.add(source_row)

        fit_type = text_value(item.get("fit_type"))
        if fit_type not in allowed_fit:
            fail(
                f"Invalid fit_type for source_row {source_row}: "
                f"{fit_type!r}"
            )

        progression = text_value(
            item.get("promotion_progression_signal")
        )
        if progression not in allowed_progression:
            fail(
                f"Invalid promotion_progression_signal for "
                f"source_row {source_row}: {progression!r}"
            )

        career_stage = text_value(item.get("career_stage"))
        reason = text_value(item.get("reason"))

        if not career_stage:
            fail(f"Missing career_stage for source_row {source_row}.")
        if not reason:
            fail(f"Missing reason for source_row {source_row}.")

        cleaned.append(
            {
                "source_row": source_row,
                "fit_type": fit_type,
                "promotion_progression_signal": progression,
                "career_stage": career_stage,
                "previous_title": text_value(item.get("previous_title")),
                "previous_company": text_value(item.get("previous_company")),
                "reason": reason,
            }
        )

    if not cleaned:
        fail(
            "LLM returned zero candidates. Re-run the review and ensure the "
            "entire Target Profiles dataset was considered. Python does not "
            "apply hard candidate filters."
        )

    return cleaned


def ensure_sheet_size(ws, min_rows: int, min_cols: int) -> None:
    if ws.row_count < min_rows:
        ws.add_rows(min_rows - ws.row_count)
    if ws.col_count < min_cols:
        ws.add_cols(min_cols - ws.col_count)


def column_letter(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def write_output(
    spreadsheet,
    sheets_service,
    sheet_id: str,
    source_records: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> str:
    by_row = {
        int(record["_source_row"]): record
        for record in source_records
    }

    try:
        ws = spreadsheet.worksheet(OUTPUT_SHEET)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=OUTPUT_SHEET,
            rows=max(100, len(decisions) + 10),
            cols=len(OUTPUT_HEADERS),
        )

    ensure_sheet_size(
        ws,
        max(100, len(decisions) + 1),
        len(OUTPUT_HEADERS),
    )

    rows = [OUTPUT_HEADERS]

    for decision in decisions:
        source = by_row[decision["source_row"]]

        rows.append(
            [
                source.get("Linkedin URL", ""),
                source.get("Name", ""),
                source.get("Profile Picture", ""),
                source.get("Current Company", ""),
                source.get("Title", ""),
                decision["fit_type"],
                decision["promotion_progression_signal"],
                decision["career_stage"],
                decision["previous_title"],
                decision["previous_company"],
                decision["reason"],
                source.get("Work Experience History", ""),
                source.get("Top Education", ""),
            ]
        )

    ws.clear()

    end_col = column_letter(len(OUTPUT_HEADERS))
    ws.update(
        range_name=f"A1:{end_col}{len(rows)}",
        values=rows,
        value_input_option="USER_ENTERED",
    )

    gid = ws.id
    requests: list[dict[str, Any]] = []

    if len(decisions) > 0:
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": gid,
                        "dimension": "ROWS",
                        "startIndex": 1,
                        "endIndex": len(decisions) + 1,
                    },
                    "properties": {"pixelSize": 120},
                    "fields": "pixelSize",
                }
            }
        )

    widths = {
        0: 250,
        1: 180,
        2: 150,
        3: 230,
        4: 300,
        5: 120,
        6: 190,
        7: 160,
        8: 260,
        9: 260,
        10: 520,
        11: 610,
        12: 610,
    }

    for col_idx, width in widths.items():
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": gid,
                        "dimension": "COLUMNS",
                        "startIndex": col_idx,
                        "endIndex": col_idx + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                }
            }
        )

    for col_idx in (4, 8, 9, 10, 11, 12):
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": gid,
                        "startRowIndex": 1,
                        "endRowIndex": len(decisions) + 1,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "wrapStrategy": "WRAP",
                            "verticalAlignment": "TOP",
                        }
                    },
                    "fields": (
                        "userEnteredFormat(wrapStrategy,"
                        "verticalAlignment)"
                    ),
                }
            }
        )

    if len(decisions) > 0:
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": gid,
                        "startRowIndex": 1,
                        "endRowIndex": len(decisions) + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(OUTPUT_HEADERS),
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

    requests.append(
        {
            "repeatCell": {
                "range": {
                    "sheetId": gid,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(OUTPUT_HEADERS),
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": (
                    "userEnteredFormat.textFormat.bold,"
                    "userEnteredFormat.verticalAlignment"
                ),
            }
        }
    )

    requests.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": gid,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        }
    )

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": requests},
    ).execute()

    return ws.url


def write_llm_output(
    spreadsheet,
    sheets_service,
    sheet_id: str,
    output_path: Path,
) -> int:
    if not output_path.exists():
        fail(f"LLM output file not found: {output_path}")

    try:
        raw = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid LLM output JSON: {exc}")

    source_records = read_target_profiles(spreadsheet, sheets_service)
    decisions = validate_llm_output(raw, source_records)

    sheet_url = write_output(
        spreadsheet,
        sheets_service,
        sheet_id,
        source_records,
        decisions,
    )

    print("=== SALES MANAGER PIPELINE COMPLETE ===")
    print(f"Profiles reviewed: {len(source_records)}")
    print(f"Candidates selected: {len(decisions)}")
    print(f"Google Sheet: {sheet_url}")
    return 0


def check(spreadsheet, sheets_service) -> int:
    records = read_target_profiles(spreadsheet, sheets_service)
    print("Preflight OK.")
    print(f"Source sheet: {TARGET_SHEET}")
    print(f"Profiles available: {len(records)}")
    print(f"LLM input path: {INPUT_JSON}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Spreadsheet bridge for LLM-based Sales Manager Pipeline review. "
            "Python does not make candidate judgments."
        )
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration and read access only.",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export all Target Profiles for LLM review.",
    )
    parser.add_argument(
        "--write",
        metavar="JSON_FILE",
        help="Write validated LLM decisions to Sales Manager Pipeline.",
    )

    args = parser.parse_args()

    if not (args.check or args.export or args.write):
        parser.error("Specify --check, --export, or --write JSON_FILE.")

    try:
        sheet_id = load_config()
        _, sheets_service, spreadsheet = authenticate(sheet_id)

        if args.check:
            return check(spreadsheet, sheets_service)

        if args.export:
            return export_profiles(spreadsheet, sheets_service)

        if args.write:
            return write_llm_output(
                spreadsheet,
                sheets_service,
                sheet_id,
                Path(args.write).resolve(),
            )

        return 0

    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
