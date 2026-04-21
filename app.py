import streamlit as st
from agent import run_agent_stream

st.set_page_config(page_title="Sector Scout", layout="wide")
st.title("Sector Scout")

question = st.text_input(
    "Enter your research question:",
    value="What are the top compliance risks for Australian financial services firms in 2026?"
)

def render_steps(steps):
    html_parts = []
    for i, step in enumerate(steps):
        if step["type"] == "breakdown":
            badge = '<span style="background:#1a3a2a;color:#4ade80;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;">Done</span>'
            html_parts.append(f"""
            <div style="border:1px solid #2a2a2a;border-radius:10px;padding:12px 14px;margin-bottom:10px;background:#1a1a1a;">
                {badge}
                <div style="font-weight:600;margin-top:6px;color:#e0e0e0;">1. Break down question</div>
                <div style="font-size:12px;color:#888;margin-top:3px;">{step['text']}</div>
            </div>
            """)
        elif step["type"] == "search_done":
            badge = '<span style="background:#1a3a2a;color:#4ade80;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;">Done</span>'
            num = step["step_num"]
            html_parts.append(f"""
            <div style="border:1px solid #2a2a2a;border-radius:10px;padding:12px 14px;margin-bottom:10px;background:#1a1a1a;">
                {badge}
                <div style="font-weight:600;margin-top:6px;color:#e0e0e0;">{num}. Search: {step['query']}</div>
                <div style="font-size:12px;color:#888;margin-top:3px;">Found {step['result_count']} results via Tavily.</div>
            </div>
            """)
        elif step["type"] == "search_running":
            badge = '<span style="background:#1a2a3a;color:#60a5fa;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;">Running</span>'
            num = step["step_num"]
            html_parts.append(f"""
            <div style="border:1px solid #1e3a5f;border-radius:10px;padding:12px 14px;margin-bottom:10px;background:#111a24;">
                {badge}
                <div style="font-weight:600;margin-top:6px;color:#e0e0e0;">{num}. Search: {step['query']}</div>
                <div style="font-size:12px;color:#888;margin-top:3px;">Searching now...</div>
            </div>
            """)
        elif step["type"] == "synthesise":
            badge = '<span style="background:#2a2a1a;color:#facc15;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;">Running</span>'
            html_parts.append(f"""
            <div style="border:1px solid #3a3a1a;border-radius:10px;padding:12px 14px;margin-bottom:10px;background:#1a1a0f;">
                {badge}
                <div style="font-weight:600;margin-top:6px;color:#e0e0e0;">Synthesise into report</div>
                <div style="font-size:12px;color:#888;margin-top:3px;">Writing final report...</div>
            </div>
            """)
    return "".join(html_parts)


if st.button("Run Research"):
    st.session_state["steps"] = []
    st.session_state["report"] = ""
    search_counter = [0]  # use list so we can mutate inside the loop

    left, right = st.columns([1, 2])

    with left:
        st.subheader("Live Steps")
        steps_container = st.empty()

    with right:
        st.subheader("Final Report")
        report_container = st.empty()

    for event in run_agent_stream(question):

        if event["type"] == "breakdown":
            st.session_state["steps"].append({"type": "breakdown", "text": event["text"]})

        elif event["type"] == "search":
            search_counter[0] += 1
            st.session_state["steps"].append({
                "type": "search_running",
                "query": event["query"],
                "step_num": search_counter[0]
            })

        elif event["type"] == "search_done":
            # Replace the last running step with the done version
            for i in range(len(st.session_state["steps"]) - 1, -1, -1):
                if st.session_state["steps"][i].get("query") == event["query"]:
                    st.session_state["steps"][i] = {
                        "type": "search_done",
                        "query": event["query"],
                        "result_count": event["result_count"],
                        "step_num": st.session_state["steps"][i]["step_num"]
                    }
                    break

        elif event["type"] == "report":
            st.session_state["steps"].append({"type": "synthesise"})
            st.session_state["report"] = event["content"]
            report_container.markdown(event["content"])

        steps_container.html(render_steps(st.session_state["steps"]))