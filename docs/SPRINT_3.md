# Sprint 3: Decision Quality and Human Review

## Sprint goal

Add explicit quality checks and human accountability to the evidence-grounded
assessment workflow. Sprint 3 makes report quality reviewable, keeps opportunity
decisions in human hands, and preserves changes in judgment over time.

## Product principle

The AI proposes; a person evaluates the report and decides what moves forward.
Automated checks may verify completeness and traceability, but they must not be
presented as substitutes for human judgment.

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

The application saves each completed rubric as a new revision, including the
reviewer, criterion rationales, aggregate score, optional notes, and timestamp.
Earlier evaluations remain available so changes in judgment are visible.

### Benchmark cases

The repository contains three synthetic workflows with different opportunity and
risk profiles:

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

## Deferred UI/UX sprint

The current interface prioritizes functional transparency over visual polish. A
future sprint will improve navigation, information hierarchy, report density,
summary views, responsive behavior, and the visual distinction between generated
analysis, human evaluation, and human decisions. That work is intentionally
separate from validating the Sprint 3 decision workflow.

## Definition of done

Sprint 3 is complete when:

- Three synthetic benchmark workflows are available for repeatable assessment.
- Automatic report checks and the human rubric are visible in the application.
- Human quality evaluations and their rationales persist as revision history.
- Human decisions and notes persist with the saved report.
- Tests cover automatic evaluation, quality scores, decision persistence, and
  revision history without making live API calls.
- The README explains the human decision boundary and current limitations.

Sprint 3 met this definition of done. Role-specialized analysis and comparison
against the simpler pipeline move to Sprint 4.
