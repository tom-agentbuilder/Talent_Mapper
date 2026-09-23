Use the existing workspace files directly. Do not ask for permission to access .env, credentials.json, Google Sheets, or the Python script.

Objective

Review ALL profiles in the Google Sheet tab:

Target Profiles

Identify people who plausibly fit this hiring persona:

A relatively early-to-mid career commercial professional in asset management / financial services who has meaningful sales, business-development, distribution, wholesale, institutional or relationship-management experience and is moving toward, or already holds, a manager-grade commercial role.

The benchmark of roughly 8–15 years of experience and "late 20s / early 30s" is a useful reference, NOT a hard filter.

This is a recruiter-style persona matching exercise, not a rigid rules engine.

Important: Use the LLM for Candidate Judgment

The LLM should make the actual candidate assessment by reading the complete career history.

Do NOT implement Boolean candidate filtering, fixed experience cutoffs, fixed recency cutoffs, or rigid title rules in Python.

Python is only the spreadsheet / JSON I/O layer.

Read the whole profile and combine the available signals into a professional recruiting judgment.

What to Look For

Consider the combination of:

sales / business development / distribution / wholesale / institutional sales

relationship management / client business / client management

increasing commercial responsibility

manager / team-lead / director / VP / head-level progression

clear career progression

recent or relatively recent step-up

career stage consistent with a cost-conscious team-building sales hire

a coherent career story

Useful patterns include:

Sales / BD → Senior commercial role → Manager

Commercial IC → Team Lead / Manager

Associate / Executive → Manager / Director

Commercial role → broader client / distribution responsibility

Do not require a specific title or every signal.

What Not to Do

Do NOT reject someone automatically because:

experience is slightly below or above 8–15 years

the current role started more than 24 months ago

the person changed companies before taking the current role

the title is not literally "Sales Manager"

the person is Director / VP / Head but the career trajectory is still relevant

exact age is unavailable

Do NOT infer or invent exact age.

Use career stage as an observable proxy for the intended persona.

Be cautious with profiles whose career is primarily:

investment / portfolio management

research

operations

compliance / legal

finance / accounting

technology

marketing

But do not automatically exclude someone whose career also contains substantial commercial responsibility.

Assessment

Classify retained profiles as:

Strong Fit

Potential Fit

Stretch Fit

Use Not Relevant for profiles that have little credible evidence of relevance to the commercial leadership need, but do not include those profiles in the final output.

Assess promotion / progression as:

Strong — clear internal or career step-up

Possible — progression is plausible but not proven

Established — clear progression, but not recent

None / Unclear — insufficient evidence

Never fabricate a promotion.

Output

Create / refresh:

Sales Manager Pipeline

The LLM should return retained candidates in overall relevance order.

Output columns:

Linkedin URL

Name

Profile Picture

Current Company

Current Title

Fit Type

Promotion / Progression Signal

Career Stage

Previous Title

Previous Company

Reason

Work Experience History

Top Education

Reason should be concise, evidence-based, and explain both the relevant signals and any meaningful gap from the persona.

Execution

1. Preflight

Run:

python -m py_compile filter_sales_manager_pipeline.py
python filter_sales_manager_pipeline.py --check

2. Export

Run:

python filter_sales_manager_pipeline.py --export

This creates:

target_profiles_llm_input.json

It must contain the complete Target Profiles dataset.

3. LLM Review

Read:

target_profiles_llm_input.json

Review ALL profiles.

You may process profiles in batches, but the final decision must consider the complete dataset.

Write the final structured decisions to:

sales_manager_pipeline_llm_output.json

Use this structure:

[
  {
    "source_row": 2,
    "fit_type": "Strong Fit",
    "promotion_progression_signal": "Strong",
    "career_stage": "Early-mid career",
    "previous_title": "Senior Sales Executive",
    "previous_company": "Example Company",
    "reason": "Clear progression from a senior commercial individual-contributor role into a manager-grade client-facing role, with a career stage broadly aligned to the hiring need."
  }
]

Rules:

One object per retained candidate.

source_row must exactly match the source row in target_profiles_llm_input.json.

fit_type must be Strong Fit, Potential Fit, or Stretch Fit.

Do not invent profile identity, URLs, promotions, age, experience, or responsibilities.

Keep candidates in overall relevance order.

Do not include Not Relevant profiles.

4. Write to Google Sheets

Run:

python filter_sales_manager_pipeline.py --write sales_manager_pipeline_llm_output.json

Python should only validate the LLM output against the source rows and transfer the selected data into:

Sales Manager Pipeline

Python must not re-score, re-filter, or override the LLM's decisions.

Google Sheets Formatting

Freeze header row

Data rows: 120 px

Wrap long-text columns

TOP vertical alignment

Work Experience History: 610 px

Top Education: 610 px

Reason: readable width

Preserve Profile Picture as the original =IMAGE("URL") formula

Never modify or destroy Target Profiles.

Only modify Sales Manager Pipeline after the source and LLM output have been successfully validated.

Final Response

Report only:

Profiles reviewed

Candidates selected

Google Sheet link

Any notable data-quality issue

Do not paste the Python source code.
Do not expose secrets.