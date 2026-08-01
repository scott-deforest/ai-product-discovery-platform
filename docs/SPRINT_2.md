# Sprint 2: Evidence-Grounded Opportunity Assessment

## Sprint goal

Turn an indexed assessment into a reviewable set of ranked AI opportunities.
Every recommendation must be supported by evidence from the assessment's source
documents and must expose its reasoning, limitations, and risks.

At the end of Sprint 2, a user can:

1. Open an assessment with indexed documents.
2. Run an AI opportunity assessment.
3. Review the evidence used during analysis.
4. Compare ranked opportunities using a transparent scoring rubric.
5. Read a concise assessment report with citations and recommended next steps.

This release will become `v0.2.0 — Employer Preview` after the public-readiness
checks pass.

## Product principle

The platform should help a human make a better decision; it should not present an
AI-generated answer as an autonomous decision.

The workflow will therefore separate:

- Source evidence retrieved from uploaded documents.
- AI-generated interpretation of that evidence.
- Transparent scores based on an explicit rubric.
- Human review of the final recommendations.

## End-to-end user flow

```text
Select assessment
      |
      v
Validate indexed evidence
      |
      v
Retrieve evidence across assessment dimensions
      |
      v
Generate candidate AI opportunities
      |
      v
Score value, feasibility, evidence, and risk readiness
      |
      v
Rank and persist recommendations
      |
      v
Review report and supporting citations
```

## Assessment dimensions

The assessment runner will retrieve evidence for four dimensions:

### 1. Workflow pain points

Identify repetitive work, delays, handoff failures, inconsistent decisions,
information-search problems, and gaps in visibility.

### 2. Data and technical readiness

Identify available data, data quality concerns, system constraints, integration
requirements, and measurable signals that could support an AI capability.

### 3. Business value

Identify desired outcomes, affected users, current volume, time or cost drivers,
quality problems, and candidate success measures.

### 4. Risk and human oversight

Identify privacy, security, compliance, accuracy, explainability, escalation, and
human-review requirements.

## Opportunity output

Each recommended opportunity must include:

- Title and one-sentence summary.
- Problem being addressed.
- Proposed AI capability.
- Primary users and workflow placement.
- Expected business value.
- Required data and dependencies.
- Material risks and safeguards.
- Suggested success metrics.
- Confidence limitations and missing information.
- At least one source citation.

## Scoring rubric

Each opportunity receives four scores on a 1–5 scale:

| Dimension | Weight | A high score means |
| --- | ---: | --- |
| Business value | 35% | The opportunity addresses a meaningful, frequent problem with measurable impact. |
| Feasibility | 25% | Required data, integrations, and workflow changes appear achievable. |
| Evidence strength | 25% | Multiple specific source passages support the problem and proposed value. |
| Risk readiness | 15% | Material risks are understood and can be controlled with appropriate oversight. |

The report will show the component scores and rationale, not only a composite
ranking. Scores are decision aids rather than precise forecasts.

## Persistence model

Sprint 2 will add three SQLite concepts:

### Assessment run

- Run ID and assessment ID.
- Status: `pending`, `running`, `completed`, or `failed`.
- Model and prompt version.
- Start and completion timestamps.
- Error message when a run fails.

### Opportunity

- Opportunity ID and run ID.
- Structured recommendation fields.
- Four component scores and overall rank.
- Human-review status for future expansion.

### Opportunity evidence

- Opportunity ID.
- Source document ID and chunk ID.
- Filename and chunk index.
- Short supporting excerpt.

Persisting runs makes results reproducible, reviewable, and comparable without
requiring the model to regenerate them on every page load.

## Implementation plan

### Work package 1: Assessment readiness and data model

- Add run, opportunity, and evidence tables.
- Add readiness checks for indexed documents and available chunks.
- Define structured Python models for assessment results.
- Add database tests and migration-safe table initialization.

Acceptance criteria:

- An assessment cannot run without indexed evidence.
- Run status and errors persist across application restarts.
- Structured results reject missing required fields or invalid scores.

### Work package 2: Evidence-pack retrieval

- Define one retrieval query for each assessment dimension.
- Retrieve assessment-scoped chunks through the existing vector store.
- Deduplicate overlapping evidence.
- Create a compact evidence pack with stable citation identifiers.

Acceptance criteria:

- Evidence never crosses assessment boundaries.
- Every evidence item maps back to a document and chunk.
- The evidence pack can be inspected before model analysis.

### Work package 3: Structured opportunity generation

- Add versioned prompts for opportunity analysis.
- Use an OpenAI structured response rather than parsing free-form prose.
- Generate a small candidate set from the evidence pack.
- Require citation IDs for material claims.
- Validate model output before persistence.

Acceptance criteria:

- Invalid or uncited opportunities are rejected or clearly flagged.
- A failed API call leaves a recoverable failed run instead of partial results.
- Tests use a fake model client and do not spend API credits.

### Work package 4: Scoring and ranking

- Apply the explicit four-part rubric.
- Require a short rationale for every component score.
- Rank opportunities while preserving component-score visibility.
- Flag missing evidence and uncertain assumptions.

Acceptance criteria:

- Scores remain within the 1–5 range.
- Ranking is deterministic once structured results are saved.
- No opportunity can rank without cited evidence.

### Work package 5: Assessment report and review interface

- Add a clear **Run assessment** action.
- Display run status and recoverable errors.
- Present an executive summary and ranked opportunity cards.
- Show scores, safeguards, success metrics, and expandable citations.
- Preserve existing ingestion controls without overwhelming the report view.

Acceptance criteria:

- A user can move from indexed documents to a completed report without using the
  terminal.
- Every opportunity visibly links to supporting evidence.
- Previously completed reports reload from SQLite without another API call.

### Work package 6: Employer-preview hardening

- Add an end-to-end sample assessment result.
- Add GitHub Actions for automated tests.
- Add screenshots or a short demo recording to the README.
- Add a license and explicit project-status section.
- Test setup from a fresh clone.
- Review error handling, duplicate uploads, and empty states.
- Confirm that secrets and runtime data are absent from Git history.

Acceptance criteria:

- Automated tests pass on GitHub.
- A new user can follow the README and complete the demo workflow.
- The repository is safe and coherent enough to change from private to public.

## Testing strategy

Sprint 2 tests will cover:

- Assessment readiness rules.
- Run-status transitions and failure recovery.
- Assessment-scoped evidence retrieval.
- Evidence deduplication and citation mapping.
- Structured-output validation.
- Score validation and deterministic ranking.
- Persistence and reload of completed reports.
- Streamlit smoke testing for the complete flow.

Live OpenAI calls will be limited to explicit integration checks. Automated tests
will use deterministic fake clients.

## Explicit non-goals

Sprint 2 will not include:

- Autonomous execution of recommendations.
- Multiple agents debating or handing work to one another.
- User accounts, team permissions, or cloud deployment.
- External document connectors.
- Exact financial ROI forecasts without customer-supplied cost data.
- OCR for scanned PDFs.
- Compliance approval or replacement of human judgment.

These may become later roadmap items after the core assessment workflow proves
useful.

## Sprint 3 direction

After Sprint 2 proves the structured assessment baseline, Sprint 3 can add
complexity intentionally. Candidate capabilities include role-specialized analysis
agents, orchestration and synthesis, cross-assessment comparison, configurable
assessment frameworks, and richer report workflows. Those additions should be
measured against the simpler Sprint 2 pipeline so that complexity earns its place.

## Definition of done

Sprint 2 is complete when the sample customer-support assessment produces a saved,
ranked report containing at least three evidence-backed AI opportunities, and:

- Every opportunity has visible source citations.
- Scores and score rationales are transparent.
- Risks, safeguards, success metrics, and missing information are included.
- Failed runs can be understood and retried.
- All automated tests and the end-to-end demo pass.
- The README demonstrates the completed product flow.
- The repository passes the public-readiness checklist.
