# Sprint 3: Decision Quality and Human Review

## Sprint goal

Improve the quality of the product decision—not merely the complexity of the AI
architecture. Sprint 3 will measure the existing single-analysis pipeline, add a
human decision workflow, introduce specialist perspectives, and compare the new
pipeline against the Sprint 2 baseline.

## Product principle

Specialist agents are an experiment, not an assumed improvement. They earn their
place only if reviewers find their output more grounded, specific, actionable,
risk-aware, or useful for making a decision.

## Stage 1: Evaluation baseline

### Automatic checks

Application code can objectively verify whether a report:

- Contains one to three focused opportunities.
- Avoids duplicate opportunity titles.
- Uses source evidence.
- Identifies risks and safeguards for every opportunity.
- Includes measurable success signals.
- States what still needs to be learned.

These checks measure completeness and traceability. They do not claim to judge
whether a recommendation is intelligent or commercially sound.

### Human-review rubric

A reviewer scores each criterion from 1 to 5. All five criteria are initially
weighted equally so that the aggregate remains understandable and does not imply
unsupported precision.

| Criterion | 1 — Weak | 3 — Useful with revision | 5 — Strong |
| --- | --- | --- | --- |
| Evidence grounding | Claims are unsupported or citations do not substantiate them. | Most important claims have relevant support, with some gaps. | Material claims are traceable to specific and persuasive evidence. |
| Specificity | Advice is generic and could apply to almost any workflow. | Recommendations reference parts of the workflow but leave important details open. | Recommendations clearly identify users, workflow placement, data, and boundaries. |
| Actionability | The next step is unclear. | A plausible next step exists but needs refinement. | A bounded validation or pilot can be planned directly from the recommendation. |
| Risk awareness | Material harms or constraints are ignored. | Major risks are named, but safeguards need development. | Risks, safeguards, human oversight, and decision boundaries are concrete and proportionate. |
| Decision usefulness | The report does not help prioritize investment. | The report narrows the options but still requires substantial interpretation. | The report clearly supports an advance, investigate, defer, or reject decision. |

Every score requires a written rationale. The aggregate score is a comparison aid,
not an objective measure of truth and not a predicted business outcome.

### Benchmark cases

The first evaluation set will contain several synthetic workflows with different
opportunity and risk profiles:

1. Customer support — high-volume knowledge work with privacy and human-review constraints.
2. Invoice processing — document extraction and exception handling with financial controls.
3. Employee onboarding — cross-functional coordination with access and employment-data risks.

The same source documents and assessment instructions must be used when comparing
pipeline versions. Live model output will be reviewed and stored as evaluation
evidence; automated tests will continue to use deterministic fixtures and spend no
API credits.

## Stage 2: Human decision workflow

Reviewers can assign one decision to each opportunity:

- Advance to validation
- Needs more evidence
- Defer
- Reject

A required decision note captures why the reviewer chose that status. Changed
decisions create new revisions instead of overwriting earlier judgment, providing
a local audit history. The AI proposes; the human remains accountable for the
product decision.

## Stage 3: Specialist assessment

The candidate pipeline will introduce three bounded perspectives:

- Business value
- Technical feasibility
- Risk and governance

A synthesis step will reconcile their findings into the same report contract used
by Sprint 2. Specialist output must remain source-grounded, and trusted citation
metadata will still be attached by application code.

## Stage 4: Comparison

Each benchmark case will be run through both pipelines. The comparison will show:

- Automatic-check results.
- Overall human-review score and criterion-level changes.
- Model and prompt versions.
- Reviewer rationales.
- Additional latency and API usage where available.

The specialist pipeline will be retained only if the measured benefit justifies
its additional cost and complexity.

## Definition of done

Sprint 3 is complete when:

- At least three benchmark workflows can be evaluated consistently.
- Automatic report checks and the human rubric are visible in the application.
- Human decisions and notes persist with the saved report.
- The specialist pipeline produces the same validated report contract as Sprint 2.
- Baseline and specialist results can be compared by case and criterion.
- Tests cover evaluation, review persistence, orchestration, and failure recovery.
- The README explains what improved, what did not, and what the comparison cannot prove.
