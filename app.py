"""Streamlit entry point for the AI Product Discovery Platform."""

import logging
from datetime import datetime

import streamlit as st
from pydantic import ValidationError

from src.assessment_runner import (
    build_evidence_pack,
    check_assessment_readiness,
    run_assessment,
)
from src.chunking import chunk_text
from src.database import (
    create_assessment,
    get_assessment_run,
    get_document_extraction,
    get_latest_human_evaluation,
    initialize_database,
    list_assessment_runs,
    list_assessments,
    list_document_chunks,
    list_documents,
    list_human_evaluation_history,
    list_latest_opportunity_reviews,
    list_opportunity_review_history,
    load_completed_assessment,
    replace_document_chunks,
    save_human_evaluation,
    save_opportunity_review,
)
from src.ingestion import (
    extract_and_save_document,
    read_extracted_text,
    save_uploaded_document,
)
from src.evaluation import evaluate_report_structure, score_human_evaluation
from src.models import (
    CompletedAssessment,
    EvidencePack,
    HumanEvaluation,
    ReviewDecision,
    SavedHumanEvaluation,
)
from src.reporting import score_interpretation
from src.vector_store import (
    count_indexed_document_chunks,
    delete_document_vectors,
    index_document_chunks,
    search_assessment,
)


LOGGER = logging.getLogger(__name__)

REVIEW_DECISION_LABELS = {
    ReviewDecision.ADVANCE.value: "Advance to validation",
    ReviewDecision.NEEDS_EVIDENCE.value: "Needs more evidence",
    ReviewDecision.DEFER.value: "Defer",
    ReviewDecision.REJECT.value: "Reject",
}

HUMAN_EVALUATION_CRITERIA = (
    (
        "evidence_grounding",
        "Evidence grounding",
        "Do the cited sources meaningfully support the report's important claims?",
    ),
    (
        "specificity",
        "Specificity",
        "Is the guidance tailored to this workflow, its users, data, and boundaries?",
    ),
    (
        "actionability",
        "Actionability",
        "Could a team plan a bounded validation step from this report?",
    ),
    (
        "risk_awareness",
        "Risk awareness",
        "Are material risks, safeguards, and human oversight handled concretely?",
    ),
    (
        "decision_usefulness",
        "Decision usefulness",
        "Does the report help you advance, investigate, defer, or reject the ideas?",
    ),
)


def _render_list(items: list[str], empty_message: str) -> None:
    """Render a readable list while handling model-declared empty sections."""
    if items:
        for item in items:
            st.markdown(f"- {item}")
    else:
        st.write(empty_message)


def _format_report_label(run: dict[str, object]) -> str:
    """Create a human-readable label for a saved report version."""
    completed_at = str(run["completed_at"] or run["created_at"])
    try:
        local_time = datetime.fromisoformat(completed_at).astimezone()
    except ValueError:
        return "Saved report"
    return local_time.strftime("%b %-d, %Y at %-I:%M %p")


def render_automatic_evaluation(report: CompletedAssessment) -> None:
    """Show deterministic report checks with plain-language recovery guidance."""
    evaluation = evaluate_report_structure(report)
    passed_count = sum(check.passed for check in evaluation.checks)
    check_count = len(evaluation.checks)

    st.markdown("#### Automatic report checks")
    st.caption(
        "These checks confirm that the report is complete and traceable. They do "
        "not decide whether an opportunity is a good investment."
    )
    if evaluation.passed:
        st.success(f"Passed all {check_count} report checks.")
    else:
        st.warning(
            f"Passed {passed_count} of {check_count} report checks. Review the "
            "items marked for attention before using this report to make a decision."
        )

    with st.expander(
        "Review automatic checks",
        expanded=not evaluation.passed,
    ):
        for check in evaluation.checks:
            status_icon = "✅" if check.passed else "⚠️"
            st.markdown(f"{status_icon} **{check.label}**")
            if not check.passed:
                st.caption(f"How to improve: {check.guidance}")


def _render_saved_quality_evaluation(
    evaluation: SavedHumanEvaluation,
) -> None:
    """Render the scores and rationales from one persisted human evaluation."""
    score = score_human_evaluation(evaluation)
    st.markdown(
        f"**Reviewer quality score: {score.overall_score:.2f} / 5**"
    )
    st.caption(
        f"Reviewed by {evaluation.reviewer} · "
        f"{_format_review_time(evaluation.evaluated_at)} · "
        f"Revision {evaluation.revision}"
    )
    for criterion_id, label, _question in HUMAN_EVALUATION_CRITERIA:
        rating = getattr(evaluation, criterion_id)
        st.markdown(f"**{label}: {rating.score}/5**")
        st.write(rating.rationale)
    if evaluation.notes:
        st.markdown("**Additional notes**")
        st.write(evaluation.notes)


def render_human_quality_evaluation(report: CompletedAssessment) -> None:
    """Capture a revisioned human assessment of the report's decision quality."""
    run = get_assessment_run(report.run_id)
    if run is None:
        LOGGER.error("human_evaluation_run_missing run_id=%s", report.run_id)
        st.error(
            "We couldn't open the human evaluation for this report. "
            "Check the app logs for technical details."
        )
        return

    latest = get_latest_human_evaluation(report.run_id)
    flash_key = f"human-evaluation-saved-{report.run_id}"

    st.markdown("#### Human quality evaluation")
    st.caption(
        "Use this rubric to judge the report itself. This score comes from a "
        "person—not the AI—and is separate from the score shown for each opportunity."
    )
    if st.session_state.pop(flash_key, False):
        st.success("Your report evaluation was saved.")

    with st.expander("How to use the 1–5 review scale"):
        st.markdown(
            """
| Score | Meaning |
| --- | --- |
| 1 | Weak — the report does not meet the criterion. |
| 2 | Limited — major problems remain. |
| 3 | Useful with revision. |
| 4 | Strong — only minor improvements are needed. |
| 5 | Excellent — clear, persuasive, and ready to support a decision. |
"""
        )
        st.caption(
            "The five criteria are weighted equally. The result is a comparison "
            "aid, not an objective measure of truth or a predicted business outcome."
        )

    if latest:
        latest_score = score_human_evaluation(latest)
        st.metric(
            "Latest human quality score",
            f"{latest_score.overall_score:.2f} / 5",
        )
        with st.expander(
            f"View saved quality evaluation · Revision {latest.revision}"
        ):
            _render_saved_quality_evaluation(latest)

    with st.expander(
        "Evaluate this report" if latest is None else "Update this evaluation",
        expanded=latest is None,
    ):
        with st.form(f"human-quality-evaluation-{report.run_id}", border=False):
            reviewer = st.text_input(
                "Reviewer name",
                value=latest.reviewer if latest else "",
                placeholder="Your name",
            )
            submitted_ratings = {}
            for criterion_id, label, question in HUMAN_EVALUATION_CRITERIA:
                current_rating = getattr(latest, criterion_id) if latest else None
                st.markdown(f"**{label}**")
                st.caption(question)
                submitted_ratings[criterion_id] = {
                    "score": st.slider(
                        f"{label} score",
                        min_value=1,
                        max_value=5,
                        value=current_rating.score if current_rating else 3,
                        key=f"{report.run_id}-{criterion_id}-score",
                    ),
                    "rationale": st.text_area(
                        f"Why did you give {label.lower()} this score?",
                        value=current_rating.rationale if current_rating else "",
                        placeholder="Describe what worked and what should improve.",
                        key=f"{report.run_id}-{criterion_id}-rationale",
                    ),
                }
            notes = st.text_area(
                "Additional notes (optional)",
                value=latest.notes if latest else "",
                key=f"{report.run_id}-evaluation-notes",
            )
            save_evaluation = st.form_submit_button("Save report evaluation")

        if save_evaluation:
            try:
                evaluation = HumanEvaluation(
                    case_id=str(run["assessment_id"]),
                    pipeline_version=str(run["prompt_version"]),
                    reviewer=reviewer,
                    notes=notes,
                    **submitted_ratings,
                )
                save_human_evaluation(report.run_id, evaluation)
            except ValidationError:
                LOGGER.warning(
                    "human_evaluation_validation_failed run_id=%s",
                    report.run_id,
                    exc_info=True,
                )
                st.error(
                    "Complete your name and explain every score before saving "
                    "the evaluation."
                )
            except Exception:
                LOGGER.exception(
                    "human_evaluation_save_failed run_id=%s",
                    report.run_id,
                )
                st.error(
                    "We couldn't save this evaluation. Your report is safe. "
                    "Check the app logs for technical details and try again."
                )
            else:
                st.session_state[flash_key] = True
                st.rerun()

    history = list_human_evaluation_history(report.run_id)
    if len(history) > 1:
        with st.expander(f"View evaluation history · {len(history)} revisions"):
            for evaluation in history:
                _render_saved_quality_evaluation(evaluation)
                st.divider()


def _format_review_time(reviewed_at: str) -> str:
    """Format a stored UTC review timestamp for the local interface."""
    try:
        return datetime.fromisoformat(reviewed_at).astimezone().strftime(
            "%b %-d, %Y at %-I:%M %p"
        )
    except ValueError:
        return "Saved previously"


def render_human_review(
    report: CompletedAssessment,
    opportunity_rank: int,
) -> None:
    """Capture the accountable human decision for one generated opportunity."""
    reviews_by_rank = {
        review.opportunity_rank: review
        for review in list_latest_opportunity_reviews(report.run_id)
    }
    current_review = reviews_by_rank.get(opportunity_rank)

    st.markdown("**Human review decision**")
    st.caption(
        "The AI proposes this opportunity. A person decides whether it should "
        "move forward and records why."
    )
    if current_review:
        st.info(
            f"Current decision: "
            f"{REVIEW_DECISION_LABELS[current_review.decision.value]}"
        )
        st.caption(
            f"Saved {_format_review_time(current_review.reviewed_at)} · "
            f"Revision {current_review.revision}"
        )
        with st.expander(
            f"View saved decision note · Revision {current_review.revision}"
        ):
            st.write(current_review.note)

    decision_options = [""] + list(REVIEW_DECISION_LABELS)
    current_decision = current_review.decision.value if current_review else ""
    with st.form(
        f"human-review-{report.run_id}-{opportunity_rank}",
        border=False,
    ):
        selected_decision = st.selectbox(
            "Decision",
            options=decision_options,
            index=decision_options.index(current_decision),
            format_func=lambda value: (
                REVIEW_DECISION_LABELS[value]
                if value
                else "Choose a decision"
            ),
        )
        review_note = st.text_area(
            "Decision note",
            value=current_review.note if current_review else "",
            placeholder=(
                "Explain the evidence, uncertainty, or constraint behind your decision."
            ),
        )
        save_review = st.form_submit_button("Save decision")

    if save_review:
        try:
            save_opportunity_review(
                run_id=report.run_id,
                opportunity_rank=opportunity_rank,
                decision=selected_decision,
                note=review_note,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("Your review decision was saved.")

    history = list_opportunity_review_history(report.run_id, opportunity_rank)
    if len(history) > 1:
        with st.expander(f"View full decision history · {len(history)} revisions"):
            for review in history:
                st.markdown(
                    f"**Revision {review.revision} · "
                    f"{REVIEW_DECISION_LABELS[review.decision.value]}**"
                )
                st.caption(_format_review_time(review.reviewed_at))
                st.write(review.note)


def render_assessment_report(report: CompletedAssessment) -> None:
    """Render a saved, evidence-linked assessment for human review."""
    st.markdown("### Assessment report")
    st.info(report.executive_summary)
    st.caption(
        "Scores compare opportunities across value, feasibility, evidence, and "
        "risk readiness. They support human judgment; they are not implementation "
        "approval or predicted ROI."
    )
    with st.expander("How to interpret the overall score"):
        st.markdown(
            """
| Score | Interpretation |
| --- | --- |
| 1.00–1.49 | Weak candidate |
| 1.50–2.49 | Limited potential |
| 2.50–3.49 | Worth exploring |
| 3.50–4.49 | Strong pilot candidate |
| 4.50–5.00 | High-priority validation candidate |
"""
        )

    render_automatic_evaluation(report)
    render_human_quality_evaluation(report)

    evidence_by_id = {
        citation.citation_id: citation for citation in report.evidence
    }
    for opportunity in report.opportunities:
        interpretation, guidance = score_interpretation(
            opportunity.composite_score
        )
        with st.container(border=True):
            st.markdown(f"#### #{opportunity.rank} · {opportunity.title}")
            score_column, interpretation_column = st.columns([1, 3])
            score_column.metric(
                "Overall score",
                f"{opportunity.composite_score:.2f} / 5",
            )
            interpretation_column.markdown(f"**{interpretation}**")
            interpretation_column.write(guidance)
            st.write(opportunity.summary)
            st.caption("Sources: " + ", ".join(opportunity.citation_ids))

            with st.expander("Recommendation details"):
                st.markdown(f"**Problem**  \n{opportunity.problem}")
                st.markdown(
                    f"**Proposed capability**  \n{opportunity.proposed_capability}"
                )
                st.markdown(
                    f"**Primary users**  \n{', '.join(opportunity.primary_users)}"
                )
                st.markdown(
                    f"**Workflow placement**  \n{opportunity.workflow_placement}"
                )
                st.markdown(f"**Expected value**  \n{opportunity.expected_value}")

                st.markdown("**Data and dependencies**")
                _render_list(
                    opportunity.data_requirements,
                    "No specific data requirements were identified.",
                )
                st.markdown("**Material risks**")
                _render_list(opportunity.risks, "No material risks were identified.")
                st.markdown("**Safeguards and human oversight**")
                _render_list(
                    opportunity.safeguards,
                    "No safeguards were identified.",
                )
                st.markdown("**Suggested success measures**")
                _render_list(
                    opportunity.success_metrics,
                    "No success measures were identified.",
                )
                st.markdown("**What we still need to learn**")
                _render_list(
                    opportunity.missing_information,
                    "No evidence gaps were identified.",
                )

            with st.expander("Why it received this score"):
                for label, weight, score_detail in (
                    ("Business value", "35%", opportunity.business_value),
                    ("Feasibility", "25%", opportunity.feasibility),
                    ("Evidence strength", "25%", opportunity.evidence_strength),
                    ("Risk readiness", "15%", opportunity.risk_readiness),
                ):
                    st.markdown(
                        f"**{label}: {score_detail.score}/5 · {weight} of overall**"
                    )
                    st.write(score_detail.rationale)

            with st.expander("Review supporting evidence"):
                for citation_id in opportunity.citation_ids:
                    citation = evidence_by_id[citation_id]
                    st.markdown(
                        f"**{citation.citation_id} · {citation.filename} · "
                        f"Chunk {citation.chunk_index + 1}**"
                    )
                    st.write(citation.excerpt)

            st.divider()
            render_human_review(report, opportunity.rank)


st.set_page_config(
    page_title="AI Product Discovery Platform",
    page_icon="🔎",
    layout="wide",
)

st.title("AI Product Discovery Platform")
st.write(
    "Upload product, process, or workflow documentation to identify where AI "
    "may create measurable value."
)

initialize_database()

st.subheader("Start a new assessment")

with st.form("new_assessment", clear_on_submit=True):
    name = st.text_input(
        "Assessment name",
        placeholder="Customer Support Workflow",
    )
    description = st.text_area(
        "What process or opportunity are you evaluating?",
        placeholder="Review the current support workflow for valuable AI opportunities.",
    )
    submitted = st.form_submit_button("Create assessment")

if submitted:
    try:
        assessment_id = create_assessment(name, description)
    except ValueError as error:
        st.error(str(error))
    else:
        st.success(f"Assessment created. ID: {assessment_id}")

st.subheader("Assessments")
assessments = list_assessments()

if not assessments:
    st.info("No assessments yet. Create one above to get started.")
else:
    for assessment in assessments:
        with st.container(border=True):
            st.markdown(f"**{assessment['name']}**")
            if assessment["description"]:
                st.write(assessment["description"])
            st.caption(
                f"Status: {assessment['status']} · ID: {assessment['id']}"
            )

    st.divider()
    st.subheader("Assessment workspace")
    st.write("Choose the assessment you want to review or continue working on.")

    assessment_by_id = {
        str(assessment["id"]): assessment for assessment in assessments
    }
    selected_assessment_id = st.selectbox(
        "Assessment",
        options=list(assessment_by_id),
        format_func=lambda assessment_id: str(
            assessment_by_id[assessment_id]["name"]
        ),
    )

    assessment_runs = list_assessment_runs(selected_assessment_id)
    displayed_report_run_id = None
    if assessment_runs and assessment_runs[0]["status"] == "failed":
        latest_failed_run = assessment_runs[0]
        LOGGER.warning(
            "latest_assessment_run_failed assessment_id=%s run_id=%s error=%s",
            selected_assessment_id,
            latest_failed_run["id"],
            latest_failed_run["error_message"],
        )
        st.warning(
            "The most recent assessment attempt did not finish. Your source "
            "documents are safe, and you can run it again when ready."
        )

    completed_runs = [
        run for run in assessment_runs if run["status"] == "completed"
    ]
    if completed_runs:
        st.divider()
        st.subheader("Saved reports")
        completed_runs_by_id = {
            str(run["id"]): run for run in completed_runs
        }
        report_selection_key = f"saved-report-selection-{selected_assessment_id}"
        preferred_report_key = f"preferred-report-{selected_assessment_id}"
        preferred_report_id = st.session_state.pop(preferred_report_key, None)
        if preferred_report_id in completed_runs_by_id:
            st.session_state[report_selection_key] = preferred_report_id
        selected_run_id = st.selectbox(
            "Report version",
            options=list(completed_runs_by_id),
            format_func=lambda run_id: _format_report_label(
                completed_runs_by_id[run_id]
            ),
            key=report_selection_key,
        )
        try:
            saved_report = load_completed_assessment(selected_run_id)
        except (ValueError, TypeError):
            LOGGER.exception(
                "saved_report_load_failed assessment_id=%s run_id=%s",
                selected_assessment_id,
                selected_run_id,
            )
            st.error(
                "We couldn't open this saved report. Your source documents are "
                "safe. Check the app logs for technical details."
            )
        else:
            displayed_report_run_id = selected_run_id
            render_assessment_report(saved_report)

    st.divider()
    st.subheader("Source documents")
    st.write("Upload and prepare the evidence for this assessment.")

    uploaded_files = st.file_uploader(
        "Choose documents",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
        help="Supported file types: PDF, TXT, Markdown, and Word documents.",
    )

    if st.button(
        "Upload selected files",
        type="primary",
        disabled=not uploaded_files,
    ):
        uploaded_count = 0
        for uploaded_file in uploaded_files:
            try:
                save_uploaded_document(
                    selected_assessment_id,
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                )
            except (OSError, ValueError) as error:
                st.error(f"Could not upload {uploaded_file.name}: {error}")
            else:
                uploaded_count += 1

        if uploaded_count:
            st.success(f"Uploaded {uploaded_count} document(s).")

    documents = list_documents(selected_assessment_id)
    if documents:
        st.markdown("#### Uploaded documents")
        for document in documents:
            size_kb = int(document["size_bytes"]) / 1024
            document_id = str(document["id"])
            with st.container(border=True):
                st.write(f"📄 {document['filename']} · {size_kb:.1f} KB")

                extraction = get_document_extraction(document_id)
                button_label = "Re-extract text" if extraction else "Extract text"
                if st.button(button_label, key=f"extract-{document_id}"):
                    try:
                        extract_and_save_document(
                            document_id=document_id,
                            assessment_id=selected_assessment_id,
                            stored_path=str(document["stored_path"]),
                            file_type=str(document["file_type"]),
                        )
                    except (OSError, ValueError) as error:
                        st.error(
                            f"Could not extract {document['filename']}: {error}"
                        )
                    else:
                        delete_document_vectors(document_id)
                        st.success(f"Extracted text from {document['filename']}.")
                        extraction = get_document_extraction(document_id)

                if extraction:
                    st.caption(
                        f"Text extracted · {extraction['character_count']} characters"
                    )
                    try:
                        extracted_text = read_extracted_text(
                            str(extraction["text_path"])
                        )
                    except OSError as error:
                        st.error(f"Could not load the extracted text: {error}")
                    else:
                        with st.expander("Preview extracted text"):
                            st.text_area(
                                "Extracted content",
                                value=extracted_text,
                                height=300,
                                disabled=True,
                                key=f"preview-{document_id}",
                            )

                        chunks = list_document_chunks(document_id)
                        chunk_button_label = (
                            "Recreate chunks" if chunks else "Create chunks"
                        )
                        if st.button(
                            chunk_button_label,
                            key=f"chunk-{document_id}",
                        ):
                            chunks_to_save = chunk_text(extracted_text)
                            replace_document_chunks(
                                document_id=document_id,
                                assessment_id=selected_assessment_id,
                                chunks=chunks_to_save,
                            )
                            delete_document_vectors(document_id)
                            chunks = list_document_chunks(document_id)
                            st.success(f"Created {len(chunks)} text chunk(s).")

                        if chunks:
                            st.caption(
                                f"{len(chunks)} chunks · "
                                "180 words maximum · 30-word overlap"
                            )
                            with st.expander("Preview chunks"):
                                for chunk in chunks:
                                    chunk_number = int(chunk["chunk_index"]) + 1
                                    st.markdown(
                                        f"**Chunk {chunk_number} · "
                                        f"{chunk['word_count']} words**"
                                    )
                                    st.text_area(
                                        f"Chunk {chunk_number} content",
                                        value=str(chunk["content"]),
                                        height=180,
                                        disabled=True,
                                        label_visibility="collapsed",
                                        key=(
                                            f"chunk-preview-{document_id}-"
                                            f"{chunk_number}"
                                        ),
                                    )

                            indexed_count = count_indexed_document_chunks(
                                document_id
                            )
                            index_button_label = (
                                "Re-index chunks"
                                if indexed_count
                                else "Index chunks"
                            )
                            if st.button(
                                index_button_label,
                                key=f"index-{document_id}",
                            ):
                                try:
                                    indexed_count = index_document_chunks(
                                        chunks,
                                        filename=str(document["filename"]),
                                    )
                                except Exception as error:
                                    st.error(
                                        f"Could not index chunks: {error}"
                                    )
                                else:
                                    st.success(
                                        f"Indexed {indexed_count} chunk(s)."
                                    )

                            if indexed_count:
                                st.caption(
                                    f"{indexed_count} chunk vectors indexed"
                                )
    else:
        st.info("No documents have been uploaded to this assessment yet.")

    indexed_document_count = sum(
        count_indexed_document_chunks(str(document["id"]))
        for document in documents
    )
    if indexed_document_count:
        st.divider()
        st.subheader("Search assessment evidence")
        st.write(
            "Ask a question to retrieve the most relevant source chunks from "
            "this assessment."
        )
        search_query = st.text_input(
            "Search question",
            placeholder="What problems slow down customer support?",
        )

        if st.button("Search evidence", disabled=not search_query.strip()):
            try:
                search_results = search_assessment(
                    search_query,
                    selected_assessment_id,
                )
            except Exception as error:
                st.error(f"Could not search the assessment: {error}")
            else:
                if not search_results:
                    st.info("No relevant chunks were found.")
                for result_number, result in enumerate(search_results, start=1):
                    metadata = result["metadata"]
                    similarity_percent = float(result["similarity"]) * 100
                    with st.container(border=True):
                        st.markdown(
                            f"**Result {result_number} · "
                            f"{similarity_percent:.1f}% similarity**"
                        )
                        st.caption(
                            f"{metadata['filename']} · "
                            f"Chunk {int(metadata['chunk_index']) + 1}"
                        )
                        st.write(result["content"])

    st.divider()
    st.subheader("Prepare assessment analysis")
    readiness = check_assessment_readiness(selected_assessment_id)

    if not readiness.ready:
        for reason in readiness.reasons:
            st.info(reason)
    else:
        st.success("The documents are prepared for assessment analysis.")
        st.caption(
            "Previewing evidence runs four semantic searches and uses the OpenAI "
            "embeddings API."
        )
        evidence_state_key = f"evidence-pack-{selected_assessment_id}"
        result_state_key = f"opportunity-result-{selected_assessment_id}"

        if st.button("Preview assessment evidence"):
            try:
                with st.spinner("Preparing source evidence..."):
                    evidence_pack = build_evidence_pack(selected_assessment_id)
            except Exception:
                LOGGER.exception(
                    "evidence_pack_preview_failed assessment_id=%s",
                    selected_assessment_id,
                )
                st.error(
                    "We couldn't prepare the evidence preview. Your documents are "
                    "safe. Check the app logs for technical details and try again."
                )
            else:
                st.session_state[evidence_state_key] = evidence_pack.model_dump(
                    mode="json"
                )
                st.session_state.pop(result_state_key, None)

        stored_evidence_pack = st.session_state.get(evidence_state_key)
        if stored_evidence_pack:
            evidence_pack = EvidencePack.model_validate(stored_evidence_pack)
            st.markdown(f"#### Evidence preview · {len(evidence_pack.items)} sources")

            for item in evidence_pack.items:
                dimension_labels = ", ".join(
                    dimension.value.replace("_", " ").title()
                    for dimension in item.dimensions
                )
                with st.container(border=True):
                    st.markdown(
                        f"**{item.citation_id} · {item.filename} · "
                        f"Chunk {item.chunk_index + 1}**"
                    )
                    st.caption(
                        f"Supports: {dimension_labels} · Retrieval similarity: "
                        f"{item.similarity * 100:.1f}% (not confidence)"
                    )
                    st.write(item.content)

            st.markdown("#### Run assessment")
            st.write(
                "The AI will analyze only the evidence shown above. Every suggested "
                "opportunity must cite at least one of those sources."
            )
            if st.button("Run and save assessment", type="primary"):
                selected_assessment = assessment_by_id[selected_assessment_id]
                try:
                    with st.spinner("Analyzing evidence for AI opportunities..."):
                        completed_assessment = run_assessment(
                            evidence_pack=evidence_pack,
                            assessment_name=str(selected_assessment["name"]),
                            assessment_description=str(
                                selected_assessment["description"] or ""
                            ),
                        )
                except Exception:
                    LOGGER.exception(
                        "assessment_run_ui_failed assessment_id=%s",
                        selected_assessment_id,
                    )
                    st.error(
                        "We couldn't complete the assessment. Your "
                        "documents and evidence are safe. Check the app logs for "
                        "technical details, then try again."
                    )
                else:
                    st.session_state[result_state_key] = (
                        completed_assessment.model_dump(mode="json")
                    )
                    st.session_state[
                        f"preferred-report-{selected_assessment_id}"
                    ] = completed_assessment.run_id

            stored_result = st.session_state.get(result_state_key)
            if stored_result and "run_id" not in stored_result:
                st.session_state.pop(result_state_key, None)
                stored_result = None
                st.info(
                    "Scoring and saved reports were just added. Run the assessment "
                    "again to create the ranked version."
                )
            if stored_result:
                completed_assessment = CompletedAssessment.model_validate(
                    stored_result
                )
                if completed_assessment.run_id == displayed_report_run_id:
                    st.session_state.pop(result_state_key, None)
                else:
                    st.success("Assessment completed and saved.")
                    render_assessment_report(completed_assessment)
