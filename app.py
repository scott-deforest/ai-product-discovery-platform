"""Streamlit entry point for the AI Product Discovery Platform."""

import logging

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
    list_assessments,
    list_document_chunks,
    list_documents,
    replace_document_chunks,
)
from src.ingestion import (
    extract_and_save_document,
    read_extracted_text,
    save_uploaded_document,
)
from src.models import CompletedAssessment, EvidencePack
from src.vector_store import (
    count_indexed_document_chunks,
    delete_document_vectors,
    index_document_chunks,
    search_assessment,
)


LOGGER = logging.getLogger(__name__)


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
    st.subheader("Upload documents")
    st.write("Choose the assessment these documents should belong to.")

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
                st.markdown("#### Ranked opportunities")
                st.success("Assessment completed and saved.")
                st.info(completed_assessment.executive_summary)
                for opportunity in completed_assessment.opportunities:
                    with st.container(border=True):
                        st.markdown(
                            f"**#{opportunity.rank} · {opportunity.title}**"
                        )
                        st.write(opportunity.summary)
                        st.caption(
                            f"Overall score: {opportunity.composite_score:.2f} / 5 · "
                            "Sources: " + ", ".join(opportunity.citation_ids)
                        )
                        with st.expander("Review recommendation details"):
                            st.markdown(f"**Problem:** {opportunity.problem}")
                            st.markdown(
                                "**Proposed capability:** "
                                f"{opportunity.proposed_capability}"
                            )
                            st.markdown(
                                f"**Expected value:** {opportunity.expected_value}"
                            )
                            st.markdown(
                                "**Safeguards:** "
                                + "; ".join(opportunity.safeguards)
                            )
                            st.markdown(
                                "**What we still need to learn:** "
                                + "; ".join(opportunity.missing_information)
                            )
                            st.markdown("**Component scores**")
                            for label, score_detail in (
                                ("Business value", opportunity.business_value),
                                ("Feasibility", opportunity.feasibility),
                                ("Evidence strength", opportunity.evidence_strength),
                                ("Risk readiness", opportunity.risk_readiness),
                            ):
                                st.write(
                                    f"{label}: {score_detail.score}/5 — "
                                    f"{score_detail.rationale}"
                                )
