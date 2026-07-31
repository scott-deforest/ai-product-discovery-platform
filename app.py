"""Streamlit entry point for the AI Product Discovery Platform."""

import streamlit as st

from src.database import (
    create_assessment,
    get_document_extraction,
    initialize_database,
    list_assessments,
    list_documents,
)
from src.ingestion import (
    extract_and_save_document,
    read_extracted_text,
    save_uploaded_document,
)


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
    else:
        st.info("No documents have been uploaded to this assessment yet.")
