"""Streamlit entry point for the AI Product Discovery Platform."""

import streamlit as st

from src.database import create_assessment, initialize_database, list_assessments


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
