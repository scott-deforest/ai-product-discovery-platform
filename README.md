# AI Product Discovery Platform

[![Tests](https://github.com/scott-deforest/ai-product-discovery-platform/actions/workflows/tests.yml/badge.svg)](https://github.com/scott-deforest/ai-product-discovery-platform/actions/workflows/tests.yml)

A local assessment application that turns product, process, and workflow
documentation into evidence-grounded, reviewable AI opportunities.

The platform is designed to help a product leader answer:

> Where could AI create measurable value in this workflow, what evidence supports
> that conclusion, and what should we validate before investing?

![Ranked assessment report](docs/images/ranked-opportunities.png)

## Project status

**Employer-preview MVP — Sprints 1–3 complete; Sprint 4 specialist analysis is
planned.**

The end-to-end workflow is functional: documents can be ingested, searched, used
to generate structured opportunities, scored with a transparent rubric, and
reopened as saved reports. Automatic checks assess report completeness, while a
human reviewer can score report quality and make revisioned decisions on every
opportunity. The application is intentionally local and single-user. It is a
portfolio demonstration, not a production SaaS product.

## What it demonstrates

- Product framing around a real decision workflow rather than a generic chatbot.
- Evidence-grounded generation with source citations and explicit uncertainty.
- Structured OpenAI responses validated through Pydantic before persistence.
- Assessment-scoped retrieval that prevents evidence crossing between projects.
- Transparent, deterministic scoring instead of an unexplained model ranking.
- Human-review safeguards, plain-language errors, and technical operational logs.
- Automatic report checks that distinguish structural completeness from human judgment.
- Persistent human decisions with explanatory notes and revision history.
- A revisioned five-part human rubric for measuring report quality across pipelines.
- Migration-safe SQLite persistence and automated tests that do not spend API
  credits.

## User workflow

1. Create a named assessment with business context.
2. Upload PDF, TXT, Markdown, or DOCX source material.
3. Extract, inspect, chunk, and index the text.
4. Preview evidence retrieved across four assessment dimensions.
5. Run the AI assessment using only the displayed evidence.
6. Review ranked opportunities, score rationales, risks, safeguards, evidence
   gaps, success measures, and exact source excerpts.
7. Evaluate the report's grounding, specificity, actionability, risk awareness,
   and decision usefulness using a human-scored rubric.
8. Advance, request more evidence, defer, or reject each opportunity and record why.
9. Reopen any saved report, evaluation, and decision history without another API call.

See the [sample assessment report](docs/SAMPLE_REPORT.md) for a compact example.

## Architecture

```text
Streamlit interface
       |
       +-- SQLite -------- assessments, runs, reports, evaluations, decisions
       |
       +-- Local files --- uploads and extracted text
       |
       +-- Chroma -------- assessment-scoped vectors and similarity search
       |
       +-- OpenAI API ---- embeddings and validated structured analysis
```

One Chroma collection stores all document chunks. Each vector carries an
`assessment_id`, `document_id`, filename, and chunk index. Every retrieval is
filtered by `assessment_id`.

The analysis workflow creates stable evidence identifiers such as `E1` and `E2`.
The model can reference those identifiers, but the application—not the model—
attaches the trusted filename, chunk ID, and source excerpt. Unknown citations
are rejected before results are saved.

## Assessment framework

Evidence is retrieved across four lenses:

- Workflow pain points
- Data and technical readiness
- Business value
- Risk and human oversight

Each opportunity receives four 1–5 component scores. Application code applies the
published weighting and ranks the candidates deterministically:

| Component | Weight |
| --- | ---: |
| Business value | 35% |
| Feasibility | 25% |
| Evidence strength | 25% |
| Risk readiness | 15% |

The interface translates the composite into a decision band from **Weak
candidate** through **High-priority validation candidate**. Scores are comparison
aids—not predicted ROI, confidence percentages, or implementation approval.

The report then passes through two explicitly human-controlled layers:

1. A reviewer scores evidence grounding, specificity, actionability, risk
   awareness, and decision usefulness. Every score requires a rationale.
2. The reviewer advances, requests more evidence for, defers, or rejects each
   opportunity and records why.

Both evaluation changes and opportunity-decision changes are saved as new
revisions. Earlier reasoning remains visible instead of being overwritten.

## Local setup

Python 3.9 or newer is required.

```bash
git clone https://github.com/scott-deforest/ai-product-discovery-platform.git
cd ai-product-discovery-platform
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Add your OpenAI API key to `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_ANALYSIS_MODEL=gpt-5.6-sol
```

Never commit `.env` or share an API key.

## Run the application

```bash
python -m streamlit run app.py
```

Open `http://localhost:8501` if the browser does not open automatically.

## Demo workflow

1. Create an assessment named **Customer Support Workflow**.
2. Upload `data/sample_docs/customer_support_workflow.md`.
3. Extract the text, create chunks, and index them.
4. Preview the assessment evidence.
5. Select **Run and save assessment**.
6. Review the ranked opportunities and expand their score explanations and
   source evidence.
7. Complete the five-part human quality evaluation.
8. Record and revise a decision on each opportunity.
9. Refresh the page and reopen the report to demonstrate report, evaluation,
   decision, and revision-history persistence.

The model response can vary between runs. Source-grounding and validation rules
remain consistent.

## Tests

```bash
python -m unittest discover -s tests -v
```

The test suite covers persistence, extraction, chunking, vector filtering,
readiness rules, evidence deduplication, structured generation, citation
validation, failure recovery, deterministic ranking, score interpretation, and
saved-report reconstruction. It also verifies automatic report evaluation,
revisioned human quality scores, and append-only decision history. Model and
embedding clients are faked in automated tests, so the suite does not require an
API key or spend API credits.

GitHub Actions runs the same suite on every push and pull request.

## Project structure

```text
app.py                         Streamlit interface and report review
src/assessment_runner.py       Readiness, evidence, generation, and run lifecycle
src/chunking.py                Deterministic overlapping chunks
src/config.py                  Local paths and model configuration
src/database.py                SQLite persistence and report reconstruction
src/evaluation.py              Automatic checks and human quality comparison
src/ingestion.py               Upload storage and text extraction
src/models.py                  Validated Pydantic domain models
src/prompts/                   Versioned analysis prompts
src/reporting.py               Deterministic scoring and interpretation
src/vector_store.py            Embeddings, Chroma, and scoped retrieval
data/sample_docs/              Safe demo documents
docs/                          Sprint plan, screenshots, and sample output
tests/                         Offline automated tests
```

## Data handling

- API keys, uploaded files, extracted text, SQLite data, and vectors are excluded
  from Git.
- Uploaded files and persisted reports remain on the local machine.
- Document chunks and search queries are sent to OpenAI to create embeddings.
- The displayed evidence pack is sent to OpenAI when the user runs an assessment.
- Generated recommendations require citations and retain human review as the
  decision boundary.

Do not use sensitive or regulated documents without confirming that the selected
API account, retention settings, and organizational policies permit that use.

## Current limitations

- Local, single-user application with no authentication or access controls.
- No OCR for scanned PDFs.
- No duplicate-upload management or document deletion interface yet.
- The retrieval and assessment model configuration is developer-managed.
- Scores depend on source quality and model judgment even though weighting and
  ranking are deterministic.
- Benchmark workflows are synthetic and do not constitute a statistically
  representative evaluation dataset.
- No production monitoring or deployment configuration.

## Roadmap

- **Sprint 1:** Document ingestion, chunking, embeddings, and scoped retrieval.
- **Sprint 2:** Evidence-grounded opportunity generation, transparent scoring,
  persistence, and report review.
- **Sprint 3:** Automatic evaluation, human quality scoring, human opportunity
  decisions, and revision history.
- **Sprint 4:** Role-specialized analysis and measured comparison against the
  simpler pipeline.

Sprint 4 begins by capturing baseline evaluations for all three synthetic
workflows before specialist results can influence reviewer expectations. A later
UI/UX sprint will improve navigation, report density, information hierarchy, and
visual polish. See the [Sprint 4 plan](docs/SPRINT_4.md), [Sprint 3 design](docs/SPRINT_3.md),
and [Sprint 2 design](docs/SPRINT_2.md).

## License

Copyright © 2026 Scott DeForest. All rights reserved.

The source is available for portfolio evaluation and demonstration. No license
for reuse, modification, or distribution is granted. See the full
[copyright notice](COPYRIGHT.md).
