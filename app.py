import streamlit as st
from agent import run_agent_stream

st.set_page_config(page_title="Sector Scout", layout="wide")
st.title("Sector Scout")

question = st.text_input(
    "Enter your research question:",
    value="What are the top compliance risks for Australian financial services firms in 2026?"
)

if st.button("Run Research"):
    # Clear previous results
    st.session_state["steps"] = []
    st.session_state["report"] = ""

    left, right = st.columns([1, 2])

    with left:
        st.subheader("Live Steps")
        steps_container = st.empty()

    with right:
        st.subheader("Final Report")
        report_container = st.empty()

    # Run the agent and update the UI as each step arrives
    for event in run_agent_stream(question):

        if event["type"] == "search":
            st.session_state["steps"].append(f"🔍 {event['query']}")
            # Rebuild the left panel with all steps so far
            steps_container.markdown("\n\n".join(st.session_state["steps"]))

        elif event["type"] == "report":
            st.session_state["report"] = event["content"]
            report_container.markdown(event["content"])