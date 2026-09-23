# Talent Mapper Runbook — Exhaustive LinkedIn Employee Mapping

Use the existing workspace files directly. Do not ask for permission to access `.env`, `credentials.json`, Google Sheets, or Apify.

## Objective

Read LinkedIn company URLs from the Google Sheet tab `Target Companies` and run:

`harvestapi/linkedin-company-employees`

Use exactly:

```json
{
  "companies": [<RAW_NORMALIZED_LINKEDIN_COMPANY_URLS>],
  "companyBatchMode": "one_by_one",
  "functionIds": ["25", "4"],
  "locations": ["Hong Kong SAR"],
  "maxItems": 0,
  "profileScraperMode": "Full ($8 per 1k)",
  "recentlyChangedJobs": false
}
```

`maxItems: 0` means scrape all available profiles, subject to the Actor/LinkedIn result limit.

Do NOT use `maxItemsPerCompany`.
Do NOT limit to one profile per company.
Do NOT truncate the results to 20.
Do not add filtering, scoring, ranking, or company-level deduplication.

## Files / Configuration

Use:

- `scrape_target_companies.py`
- `requirements.txt`
- `.env`
- `credentials.json`

Read from `.env`:

- `APIFY_TOKEN`
- `DEFAULT_GOOGLE_SHEET_ID`

Never expose secrets or print the contents of `credentials.json`.

## Execution

First run:

```powershell
python -m py_compile scrape_target_companies.py
```

Then:

```powershell
python scrape_target_companies.py --check
```

If preflight passes, run:

```powershell
python scrape_target_companies.py
```

Do not ask for confirmation.

## Input URL Handling

Accept raw LinkedIn URLs, Markdown links, and Google Sheets `HYPERLINK()` formulas.

Normalize them to raw canonical LinkedIn company URLs before sending them to Apify.
Deduplicate company URLs.

## Profile Output

Write ALL profiles returned by Apify to the Google Sheet tab:

`Target Profiles`

Preserve the Apify dataset order.

Use these columns in exactly this order:

1. `Linkedin URL`
2. `Name`
3. `Profile Picture`
4. `Current Company`
5. `Title`
6. `Work Experience History`
7. `Top Education`

For `Current Company` and `Title`, use the profile's `currentPosition` data. Do not infer them from historical experience when current-position data exists.

Profile picture must be a real Google Sheets formula:

`=IMAGE("URL")`

## Work Experience

Format each role as:

`[Position] at [CompanyName] ([startDate.text] - [endDate.text] | [duration])`

If a description exists, add:

`Description: ...`

Separate roles with a blank line.

## Top Education

Format as:

`[Degree] in [fieldOfStudy] at [schoolName] ([startDate.text] - [endDate.text])`

## Google Sheets Formatting

- Data rows: 120 px
- Column F (`Work Experience History`): 610 px
- Column G (`Top Education`): 610 px
- F/G: WRAP
- All data cells: TOP vertical alignment
- Freeze header row

Do not modify `Target Profiles` if the Apify run fails or returns zero profiles.

## Exhaustive Run Boundary

`maxItems=0` requests all available profiles. LinkedIn can limit a single search query to 2,500 results, so “exhaustive” means all profiles the Actor can return for each query within that limit.

Because `companyBatchMode` is `one_by_one`, each target company is processed as a separate search query.

If the Actor reports that more profiles exist than it can extract, report that limitation instead of claiming the dataset is complete.

## Errors

Retry only HTTP 408, 429, 500, 502, 503, 504.
Do not blindly retry 400, 401, or 403.

If Apify returns an error, do not clear or modify `Target Profiles`.

## Final Response

Report only:

- Target companies fetched
- Profiles returned by Apify
- Profiles saved
- Any important Apify warning/anomaly or LinkedIn result-limit notice
- Google Sheet link

Do not paste the Python source code.
