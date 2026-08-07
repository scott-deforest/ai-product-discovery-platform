# Sprint 4: Specialist Analysis and Measured Comparison

## Sprint goal

Determine whether role-specialized analysis produces more useful product
decisions than the simpler Sprint 2 pipeline. Sprint 4 will establish a baseline,
introduce bounded specialist perspectives, synthesize their findings into the
existing report contract, and compare both approaches using the Sprint 3 human
quality rubric.

## Product principle

Additional AI calls and orchestration are costs, not accomplishments. Specialist
analysis earns its place only if reviewers find the result more grounded,
specific, actionable, risk-aware, or useful enough to justify the added latency,
expense, and failure modes.

## Stage 1: Establish the baseline

Run the existing single-analysis pipeline against the three synthetic workflows:

1. Customer support
2. Invoice processing
3. Employee onboarding

For every saved report:

- Complete the five-part human quality evaluation with written rationales.
- Record a decision and note for each generated opportunity.
- Preserve the model, prompt version, automatic checks, and report version.
- Summarize recurring strengths and weaknesses across the three cases.

The same documents and assessment instructions will be reused for the specialist
pipeline. Baseline results must be captured before specialist output can influence
review expectations.

## Stage 2: Define bounded specialist roles

### Business value specialist

Examines workflow pain, affected users, volume, expected outcomes, success
measures, and missing commercial evidence. It does not make technical or risk
approval decisions.

### Technical feasibility specialist

Examines data availability, data quality, integration needs, workflow placement,
implementation constraints, and validation requirements. It does not claim
business priority or compliance approval.

### Risk and governance specialist

Examines privacy, security, accuracy, human oversight, prohibited actions,
escalation boundaries, and necessary safeguards. It identifies risk; it does not
serve as legal or compliance approval.

Every specialist receives the same trusted evidence pack, returns validated
structured findings, and references only known citation IDs.

## Stage 3: Synthesize one report

A synthesis step will reconcile the three perspectives into the existing
`AssessmentResult` contract so downstream scoring, persistence, automatic checks,
human evaluation, and opportunity decisions continue to work unchanged.

The orchestrator must:

- Keep specialist outputs inspectable.
- Reject unknown evidence citations.
- Persist technical failure details while showing plain-language recovery guidance.
- Avoid saving a partial final report as completed.
- Record pipeline and prompt versions for reproducibility.
- Use deterministic fake clients in automated tests.

## Stage 4: Compare both pipelines

For each benchmark case, compare:

- Automatic report-check results.
- Overall human quality score.
- Criterion-level score changes and reviewer rationales.
- Opportunity decisions and evidence gaps.
- Model calls, latency, and usage where available.
- New failure modes or operational complexity.

The comparison must describe limitations. Three synthetic cases and one reviewer
can support a product-development decision, but they cannot prove general model
superiority or statistical significance.

## Explicit non-goals

Sprint 4 will not include:

- Autonomous execution of recommendations.
- A free-form agent conversation or debate loop.
- Replacement of human product, legal, security, or compliance judgment.
- Production deployment, authentication, or team permissions.
- The deferred UI/UX redesign.

## Definition of done

Sprint 4 is complete when:

- All three benchmark cases have saved baseline evaluations.
- Three specialist outputs are validated and source-grounded.
- Synthesis produces the same trusted report contract as the baseline pipeline.
- Specialist failures are recoverable and do not create completed partial reports.
- Both pipelines can be compared by case and human-review criterion.
- Added model usage and latency are visible where the API provides them.
- Tests cover role boundaries, orchestration, citation validation, synthesis, and
  failure recovery without spending API credits.
- The README reports what improved, what did not, and whether specialization earned
  its additional complexity.
