# Talent Mapper

## Demo

[![▶ Watch the AI Talent Mapping Demo](https://img.youtube.com/vi/73BS80pkQRE/maxresdefault.jpg)](https://youtu.be/73BS80pkQRE)

*Click the image to watch the demo on YouTube.*

**AI-assisted talent mapping for recruiters entering a new market**

Talent Mapper is a recruitment intelligence workflow built around **OpenCode + Apify + Python + Google Sheets**.

Its purpose is not to replace recruiters. Its purpose is to give a recruiter a structured head start when entering a new market, especially when the recruiter does not yet have a deep candidate network or a mature market map.

The workflow turns a list of target companies into an initial, searchable talent map, then uses an LLM to interpret career trajectories and surface plausible candidates for a defined hiring persona.

> **AI gives the recruiter a head start. The recruiter owns the market.**

---

## Why Talent Mapper Exists

When entering a new industry or market, a recruiter first needs to understand the landscape:

- Which companies matter?
- Who are the relevant employers?
- What job titles do they use?
- How are commercial teams structured?
- Which people appear to be relevant to the hiring problem?

The first objective is therefore not to immediately find the perfect candidate.

It is to **accelerate the learning curve for market entry**.

A recruiter can then use that initial map to become more knowledgeable, better connected and more effective in conversations with hiring managers and candidates.

The resulting candidate database is not the end product. It is a tool for processing information at a scale that a human brain cannot comfortably hold.

---

## End-to-End Workflow

```mermaid
flowchart TB

    subgraph S1["1. DISCOVER"]
        direction LR
        A["Target<br/>Companies"]
        B["LinkedIn<br/>Company URLs"]
        C["Apify<br/>Employee Scraping"]
        D["Target<br/>Profiles"]

        A --> B --> C --> D
    end

    subgraph S2["2. QUALIFY"]
        direction LR
        E["LLM Career /<br/>Persona Review"]
        F["Sales Manager<br/>Pipeline"]
        G["Recruiter<br/>Review"]
        H["Internal Database<br/>Cross-check"]

        E --> F --> G --> H
    end

    subgraph S3["3. INTELLIGENCE"]
        direction LR
        I["Local Job Platforms /<br/>Contact Research"]
        J["Candidate<br/>Outreach"]
        K["Candidate<br/>Intelligence"]

        I --> J --> K
    end

    D --> E
    H --> I

    K --> L["Market Reality<br/>to P&L Owners"]
    K --> M["Candidate<br/>Database"]

## 1. Define the Competitive Landscape

Start with a list of competitor or comparable companies.

Example asset-management universe:

- BlackRock Asset Management
- Franklin Templeton Investments
- AXA Investment Managers
- First Sentier
- T. Rowe Price
- Fidelity Investments
- Morgan Stanley Investment Management
- Aberdeen Investments

The list is the starting point for the talent map, not the final candidate pool.

---

## 2. Resolve Company LinkedIn URLs

The company list is stored in **Google Sheets**.

OpenCode agents can use an Apify Google Search workflow to resolve company names into LinkedIn company URLs and populate the sheet.

The result is a normalized company list that can be passed into the employee-scraping workflow.

---

## 3. Build the Exhaustive Talent Pool

The recruiter supplies the target company URLs to the Apify Actor:

**`harvestapi/linkedin-company-employees`**

The current workflow is configured for:

```json
{
  "companies": ["<target company LinkedIn URLs>"],
  "companyBatchMode": "one_by_one",
  "functionIds": ["25", "4"],
  "locations": ["Hong Kong SAR"],
  "maxItems": 0,
  "profileScraperMode": "Full ($8 per 1k)",
  "recentlyChangedJobs": false
}
```

Where:

- `25` = Sales
- `4` = Business Development
- `maxItems: 0` = request all available profiles
- `one_by_one` = process each company separately

The Actor returns structured profile information including current and previous positions, work experience, education, profile picture and other profile metadata.

The current implementation writes the results to the Google Sheet tab:

**`Target Profiles`**

The purpose of this stage is **coverage**.

It intentionally does not try to make the final hiring decision.

---

## 4. Give the LLM the Whole Career Story

The second stage reads the full `Target Profiles` dataset.

The LLM is used for the part that is difficult to express as rigid Python rules:

- understanding career trajectories
- interpreting commercial relevance
- recognizing progression
- distinguishing individual contributors from emerging leaders
- understanding equivalent titles across companies
- identifying plausible fits for the hiring persona
- explaining why a candidate is relevant

The workflow deliberately avoids turning the persona into a brittle Boolean filter.

For example, the hiring brief may describe an ideal candidate as:

> Someone in their late 20s or early 30s who has just been promoted into a manager-grade commercial role.

Rather than trying to infer someone's exact age, the LLM uses observable career signals such as:

- roughly 8–15 years of experience as a benchmark
- sales / business development / distribution / institutional / relationship-management experience
- increasing commercial responsibility
- movement into manager / team-lead / director / VP-level responsibility
- evidence of career progression
- a coherent career story

These are **signals**, not rigid pass/fail conditions.

The resulting shortlist is written to:

**`Sales Manager Pipeline`**

---

# The Role of AI

AI is used where it provides leverage over information volume and pattern recognition.

### AI is good at

**1. Market entry acceleration**

Build an initial map of companies, titles, functions and visible people much faster than a recruiter starting from zero.

**2. Large-scale information processing**

Review hundreds of profiles and long career histories that would be difficult for one person to inspect manually.

**3. Pattern recognition**

Identify plausible career trajectories across different company naming conventions and job titles.

**4. Structuring unstructured information**

Convert scraped profile data into a consistent database that a recruiter can search, compare and work from.

**5. Candidate discovery support**

Surface people who deserve human review. The AI output is a starting point for recruiter judgment, not the final decision.

---

# What AI Does Not Own

AI should not own the parts of recruitment that depend on trust, context, relationships or proprietary human intelligence.

### AI does not own candidate judgment

The recruiter makes the final call on which candidates are actually suitable.

A profile can look strong on paper and still be wrong because of factors that are not visible online.

### AI does not own candidate relationships

The recruiter is still responsible for:

- approaching candidates
- building trust
- understanding motivations
- maintaining relationships
- keeping candidates engaged over time

### AI does not own confidential market intelligence

Public profiles cannot reliably tell you:

- the real culture of a company
- compensation and commission structures
- internal politics
- promotion reality
- why people leave
- deeper business strategy
- how a team really operates

That intelligence comes from conversations with candidates and people inside the market.

### AI does not replace the recruiter's network

Some of the most valuable candidates may have little or no digital footprint.

These are the **“secret candidates”** — people found through referrals, reputation and the recruiter grapevine.

They are outside the reach of a purely digital sourcing workflow.

---

# Human Recruiter Ownership

The recruiter remains at the centre of the workflow.

## 1. Learn the market

Use the initial AI-generated talent map to understand:

- company names
- job titles
- organizational structures
- talent movement
- competitor landscape

The recruiter then validates this understanding through hiring-manager conversations and candidate conversations.

## 2. Make the final hiring judgment

AI can surface candidates.

The recruiter decides:

> **“Is this actually a person I would put in front of my hiring manager?”**

## 3. Build the relationship

The database is not the relationship.

The recruiter is responsible for building and maintaining the human connection with candidates.

## 4. Gather intelligence

Candidates are a source of information about the market, not just potential hires.

The recruiter can learn from conversations about:

- compensation
- culture
- career prospects
- leadership
- competitor movements
- hiring activity
- business strategy

## 5. Communicate market reality

The recruiter's job is ultimately to turn candidate conversations into useful market intelligence and communicate that reality to hiring managers and P&L owners.

---

# A Deliberate Division of Labour

| Task | AI | Human Recruiter |
|---|:---:|:---:|
| Discover competitor companies | ✓ | ✓ |
| Resolve company LinkedIn URLs | ✓ | Review |
| Collect public profile data | ✓ | Oversight |
| Process large candidate datasets | ✓ | |
| Interpret career trajectories | ✓ | ✓ |
| Surface plausible candidates | ✓ | ✓ |
| Make final candidate judgment | | **✓** |
| Validate market reality | | **✓** |
| Gather candidate intelligence | | **✓** |
| Build candidate relationships | | **✓** |
| Find referral / “secret” candidates | | **✓** |
| Maintain candidate network | | **✓** |
| Advise hiring managers | | **✓** |
| Communicate market intelligence to P&L owners | | **✓** |

The objective is not maximum automation.

The objective is to **automate the information-heavy work while keeping ownership of judgment and relationships with the recruiter**.

---

# Why Use an Open-Source AI Agent?

The project uses **OpenCode** as the agent layer and connects it to Apify through MCP.

The repository configuration enables the Apify MCP server through the local OpenCode configuration, with the Apify token supplied through the environment rather than hard-coded into the workflow.

The workflow does not require a frontier model for every task.

For the initial talent-mapping stage, the work is largely:

- structured data extraction
- transformation
- classification
- career-pattern interpretation
- spreadsheet operations

The principle is therefore:

> **Use the simplest model that performs the job reliably.**

The goal is not “AI for AI's sake”. The goal is a repeatable recruitment system that produces commercially useful output.

---

# Why Python Is Still Used

Python is intentionally kept relatively simple.

It handles deterministic tasks such as:

- reading `.env`
- authenticating to Google Sheets
- reading and writing spreadsheet data
- normalizing LinkedIn URLs
- calling Apify APIs
- preserving output structure and formatting
- moving LLM decisions back into Google Sheets

The **judgment layer** should remain with the LLM rather than being buried inside a large collection of rigid regex and Boolean rules.

This separation keeps the workflow easier to inspect and modify.

---

# Current Data Flow

### Input

`Target Companies`

A Google Sheet containing competitor company names and their LinkedIn company URLs.

### Output 1

`Target Profiles`

An exhaustive, structured talent pool containing visible sales / business-development profiles from the selected companies in Hong Kong.

Typical fields include:

- LinkedIn URL
- Name
- Profile Picture
- Current Company
- Current Title
- Work Experience History
- Top Education

### Output 2

`Sales Manager Pipeline`

A human-review shortlist produced from the full profile pool using LLM-based career and persona interpretation.

The output includes the original profile information plus fields explaining the LLM's assessment, such as:

- Fit Type
- Promotion / Progression Signal
- Career Stage
- Previous Title
- Previous Company
- Reason

---

# What Comes After Talent Mapper

Talent Mapper is not the end of the recruitment workflow.

Once a candidate pool has been created, the recruiter can combine it with internal and external sources.

### 1. Cross-check against the internal database

Identify whether the recruiter or company already has:

- previous contact history
- candidate notes
- previous applications
- existing relationships
- referrals

### 2. Enrich contact information

Where appropriate and compliant with the relevant platform's terms and applicable law, use local recruiting platforms such as:

- eFinancials
- JobsDB / JobStreet
- other local market sources

The objective is to help the recruiter identify a way to start a relationship.

### 3. Contact the market directly

The recruiter becomes proactive:

`AI-generated map → recruiter outreach → candidate conversation → intelligence → relationship → better market map`

That feedback loop is the real value of the system.

---

# Known Limitations

Talent Mapper is intentionally limited by what can be observed from public digital information.

### Digital footprint limitation

Some highly relevant candidates will not appear in the source data or will have incomplete profiles.

### Data quality limitation

LinkedIn profile information can be incomplete, outdated or inconsistent across companies and titles.

### Judgment limitation

A CV or LinkedIn profile cannot fully capture candidate quality.

### Relationship limitation

No scraping workflow can reproduce trust built through years of conversations and referrals.

### Intelligence limitation

The deepest market intelligence is often generated only through candidate conversations.

These limitations are not bugs to eliminate. They define where the human recruiter remains essential.

---

# Cost Philosophy

The project is designed to be inexpensive relative to the time required for manual market mapping.

The current employee-scraping configuration uses Apify's **Full profile** mode at the referenced **$8 per 1,000 events** pricing tier. Apify also provides a Full profile + email-search tier at a higher event price, which can be used when contact enrichment is required.

The economic question is not whether the workflow costs zero.

It is whether a small scraping and compute cost can remove a large amount of repetitive research time while leaving the high-value human work intact.

---

# Core Principle

> **Judgement and relationships should never be outsourced to AI.**
>
> AI is used to give recruiters a head start for market entry.
>
> The recruiter is still the person who talks to candidates, gathers business intelligence, builds the candidate network and maintains the database.

The database exists because the recruiter encounters more information than a human brain can reliably process.

AI helps organize and process that information.

**The recruiter remains the owner of the market.**

---

# Repository Structure

```text
.
├── README.md
├── RUN_TALENT_MAPPER.md
├── scrape_target_companies.py
├── SALES_MANAGER_PIPELINE_RUNBOOK.md
├── filter_sales_manager_pipeline.py
├── requirements.txt
├── opencode.json
├── actor_info.json
├── .env                  # local secrets; do not commit
└── credentials.json      # Google service-account credentials; do not commit
```

---

# Quick Start

The workflow is designed to be executed through OpenCode runbooks.

### Talent mapping

```text
Read RUN_TALENT_MAPPER.md and execute it.
```

### Candidate persona review

```text
Read SALES_MANAGER_PIPELINE_RUNBOOK.md and execute it.
```

The first run builds the exhaustive talent pool.

The second run reviews that pool and creates the candidate pipeline.

---

## Disclaimer

This project is a recruitment workflow experiment. It is intended to assist human recruiters with research and information processing, not to make autonomous hiring decisions.

The workflow should be operated in accordance with applicable employment, privacy, platform and data-protection requirements.
