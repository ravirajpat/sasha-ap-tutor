#!/usr/bin/env python3
"""
AP Physics 1 Tutor — Streamlit Web UI for Sasha
Run with: streamlit run app.py
"""

import os
import sys

# Set working directory so JSON files (performance.json, weak_topics.json) land here
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anthropic
import streamlit as st
from datetime import date

from agent import (
    SYSTEM_PROMPT, TOOLS, execute_tool,
    EXAM_DATE, UNITS, UNIT_WEIGHTS, LEVEL_NAMES, LEVEL_ICONS, DIFFICULTY_NAMES, MODEL,
    load_performance, load_weak_topics, days_remaining,
    tool_get_performance_report, tool_get_weak_topics, tool_get_study_schedule,
    get_today_questions, MIN_QUESTIONS,
)

# ── Bridge Streamlit secrets → env vars (for Supabase) ────────────────────────
for _key in ["SUPABASE_URL", "SUPABASE_KEY"]:
    if _key not in os.environ:
        try:
            os.environ[_key] = st.secrets[_key]
        except Exception:
            pass

# ── Page Config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AP Physics 1 Tutor",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session State Init ─────────────────────────────────────────────────────────

if "api_messages" not in st.session_state:
    st.session_state.api_messages = []   # full history sent to API

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # (role, text) pairs for display

if "injected_message" not in st.session_state:
    st.session_state.injected_message = None

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚛️ Sasha's Tutor")

    # Exam countdown
    days_left = days_remaining()
    exam_str = EXAM_DATE.strftime("%B %d, %Y")
    if days_left > 0:
        st.metric("Days Until Exam", days_left, delta=f"May 6 AP Physics 1")
    elif days_left == 0:
        st.metric("Exam Day!", "TODAY 🌟")
    else:
        st.metric("Exam", "Completed")

    st.divider()

    # Unit progress dashboard
    st.subheader("Unit Progress")
    data = load_performance()

    LEVEL_COLORS = {
        0: "#888888",
        1: "#e74c3c",
        2: "#e67e22",
        3: "#f1c40f",
        4: "#2ecc71",
        5: "#00b4d8",
    }

    for unit in UNITS:
        u = data["units"].get(unit, {})
        level = u.get("level", 0)
        total = u.get("total", 0)
        correct = u.get("correct", 0)
        weight = UNIT_WEIGHTS.get(unit, 0)
        color = LEVEL_COLORS[level]
        bar = LEVEL_ICONS.get(level, "○○○○○")
        label = LEVEL_NAMES.get(level, "Untested") if level > 0 else "Untested"

        if total > 0:
            acc = int((correct / total) * 100)
            caption = f"{acc}% · {label}"
        else:
            caption = "Not yet tested"

        short_name = unit.replace("& ", "").replace("'s", "s")
        st.markdown(
            f"<div style='margin-bottom:4px'>"
            f"<span style='font-size:0.78em;color:#ccc'>{short_name} <span style='color:#888'>({weight}%)</span></span><br>"
            f"<span style='font-family:monospace;color:{color}'>{bar}</span> "
            f"<span style='font-size:0.75em;color:#aaa'>{caption}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Quick action buttons
    st.subheader("Quick Actions")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📅 Schedule", use_container_width=True):
            st.session_state.injected_message = "What's my recommended study schedule?"
            st.rerun()
    with col2:
        if st.button("⚠️ Weak Topics", use_container_width=True):
            st.session_state.injected_message = "Show me my weak topics."
            st.rerun()

    col3, col4 = st.columns(2)
    with col3:
        if st.button("📊 Report", use_container_width=True):
            st.session_state.injected_message = "Give me my full progress report."
            st.rerun()
    with col4:
        if st.button("🧪 Diagnose", use_container_width=True):
            st.session_state.injected_message = "Run a full diagnostic and tell me what to study first."
            st.rerun()

    # Daily practice progress
    st.divider()
    st.subheader("Today's Practice")
    q_done = get_today_questions()
    st.progress(min(q_done / MIN_QUESTIONS, 1.0))
    if q_done >= MIN_QUESTIONS:
        st.success(f"✅ {q_done}/{MIN_QUESTIONS} questions — great work today!")
    else:
        st.warning(f"⚠️ {q_done}/{MIN_QUESTIONS} questions answered today")

    # Weak topics expander
    topics = load_weak_topics()
    if topics:
        st.divider()
        with st.expander(f"⚠️ Weak Topics ({len(topics)})"):
            for t in topics:
                st.markdown(f"• **{t['topic']}** — {t['note']}")

# ── Main Chat Area ─────────────────────────────────────────────────────────────

st.title("AP Physics 1 Tutor")
st.caption(f"Hi Sasha! You have **{days_left} days** until your exam on {exam_str}. Let's get to work! 💪")

# Welcome message on first load
if not st.session_state.chat_history:
    welcome = (
        f"Hi Sasha! 👋 I'm your AP Physics 1 tutor. You have **{days_left} days** until your exam on **{exam_str}**.\n\n"
        "Here's what we can do together:\n"
        "- **Diagnose** your understanding of any unit\n"
        "- **Quiz** you with MCQ and FRQ questions at your exact level\n"
        "- **Track** your progress and adjust difficulty automatically\n"
        "- **Plan** your study schedule based on what needs the most work\n\n"
        "Try saying: *'Test me on Energy'* or *'Give me a hard FRQ on Momentum'* or *'What should I study today?'*"
    )
    st.session_state.chat_history.append(("assistant", welcome))

# Render chat history
for role, text in st.session_state.chat_history:
    with st.chat_message(role, avatar="🎓" if role == "assistant" else "👩‍🎓"):
        st.markdown(text)

# ── Message Handling ───────────────────────────────────────────────────────────

def run_agent(user_text: str):
    """Run the full agentic loop for a user message, streaming the response."""

    # Show user message
    with st.chat_message("user", avatar="👩‍🎓"):
        st.markdown(user_text)
    st.session_state.chat_history.append(("user", user_text))

    # Add to API history
    st.session_state.api_messages.append({"role": "user", "content": user_text})

    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY is not set. Go to Manage app → Settings → Secrets and add it.")
        st.stop()
    client = anthropic.Anthropic(api_key=api_key)

    # Agentic loop
    while True:
        full_text = ""
        assistant_content = []

        with st.chat_message("assistant", avatar="🎓"):
            placeholder = st.empty()

            with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=TOOLS,
                messages=st.session_state.api_messages,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            full_text += event.delta.text
                            placeholder.markdown(full_text + "▌")

                final_msg = stream.get_final_message()

            # Remove streaming cursor
            if full_text:
                placeholder.markdown(full_text)
            else:
                placeholder.empty()

            # Collect assistant content blocks for API history
            for block in final_msg.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
                elif block.type == "thinking":
                    assistant_content.append({
                        "type": "thinking",
                        "thinking": block.thinking,
                        "signature": block.signature,
                    })

            # Execute tools if needed
            if final_msg.stop_reason == "tool_use":
                tool_results = []
                for block in final_msg.content:
                    if block.type == "tool_use":
                        tool_label = block.name.replace("_", " ").title()
                        with st.status(f"Using tool: {tool_label}…", expanded=False) as status:
                            result = execute_tool(block.name, block.input)
                            status.update(label=f"✓ {tool_label}", state="complete")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

        st.session_state.api_messages.append({"role": "assistant", "content": assistant_content})

        if final_msg.stop_reason != "tool_use":
            # Save final text to display history
            if full_text:
                st.session_state.chat_history.append(("assistant", full_text))
            break

        # Feed tool results back for next iteration
        st.session_state.api_messages.append({"role": "user", "content": tool_results})


# Handle injected message (from sidebar buttons)
if st.session_state.injected_message:
    msg = st.session_state.injected_message
    st.session_state.injected_message = None
    run_agent(msg)

# Handle typed input
if prompt := st.chat_input("Ask me anything, or say 'test me on Energy'…"):
    run_agent(prompt)
