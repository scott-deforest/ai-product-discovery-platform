"""Streamlit entry point for the AI Product Discovery Platform."""

import logging
from datetime import datetime

import streamlit as st

from src.assessment_runner import (
    build_evidence_pack,
    check_assessment_readiness,
    run_assessment,
)
from src.chunking import chunk_text
from src.database import (
    create_assessment,
    get_document_extraction,
    initialize_database,
    list_assessment_runs,
    list_assessments,
    list_document_chunks,
    list_documents,
    load_completed_assessment,
    replace_document_chunks,
)
from src.ingestion import (
    extract_and_save_document,
    read_extracted_text,
    save_uploaded_document,
)
from src.evaluation import evaluate_report_structure
from src.models import CompletedAssessment, EvidencePack
from src.reporting import score_interpretation
from src.vector_store import (
    count_indexed_document_chunks,
    delete_document_vectors,
    index_document_chunks,
    search_assessment,
)


LOGGER = logging.getLogger(__name__)


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
