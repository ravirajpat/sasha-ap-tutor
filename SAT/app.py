#!/usr/bin/env python3
"""
SAT Tutor — Streamlit Web UI for Sasha
Run with: streamlit run app.py
"""

import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import math
import re
import time
import anthropic
import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime

from agent import (
    AGENTS, ALL_TOOLS, execute_tool,
    LEVEL_NAMES, LEVEL_ICONS, MODEL,
    load_performance, load_weak_topics, days_remaining,
    get_today_questions, get_daily_topic, MIN_QUESTIONS,
    load_topic_history, save_topic_result, analyze_topic_performance, predict_sat_score,
)
from practice_test import (
    MODULE_CONFIGS, generate_full_test, save_test, load_test,
    list_saved_tests, score_test,
)
from topic_test import TOPIC_CATALOG, generate_topic_test

# ── Bridge Streamlit secrets → env vars ───────────────────────────────────────
for _key in ["SUPABASE_URL", "SUPABASE_KEY",
             "GMAIL_USER", "GMAIL_APP_PASSWORD", "SASHA_EMAIL"]:
    if _key not in os.environ:
        try:
            os.environ[_key] = st.secrets[_key]
        except Exception:
            pass

@st.cache_resource
def _get_anthropic_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)

# ── Page Config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SAT Tutor — Sasha",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS — College Board design system ───────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,400;0,600;0,700;0,800;1,400&display=swap');

    /* ════════════════════════════════════════════════
       College Board Design System
       Primary Navy  #00539B   Bright Blue  #0077C8
       Red           #C8102E   Text         #1A1A1A
       Gray          #6D6D6D   Border       #D1D1D1
       Light BG      #F5F5F5   White        #FFFFFF
    ════════════════════════════════════════════════ */

    /* ── Force Open Sans on every element ── */
    *, *::before, *::after,
    html, body, .stApp, .stMarkdown,
    [class*="st-"], [class*="css-"],
    button, input, textarea, select, option,
    h1, h2, h3, h4, h5, h6, p, span, div, li, a, label {
        font-family: 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }

    /* ── White page background ── */
    html, body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    .main, .block-container { background: #FFFFFF !important; }
    /* ── Streamlit chrome cleanup ── */
    [data-testid="stDecoration"]        { display: none !important; }
    /* Native header stays visible so sidebar toggle works — styled navy to blend with our custom header */
    [data-testid="stHeader"]            { background: #00539B !important;
                                          height: 56px !important;
                                          min-height: 56px !important;
                                          padding: 0 !important;
                                          z-index: 990 !important; }
    /* Hide deploy/share toolbar actions inside the header */
    [data-testid="stToolbarActions"]    { display: none !important; }
    [data-testid="stToolbar"]           { display: none !important; }
    .stDeployButton                     { display: none !important; }
    #MainMenu                           { display: none !important; }
    footer                              { display: none !important; }

    /* Sidebar toggle — white icon on navy, always above our fixed overlay */
    [data-testid="collapsedControl"],
    button[data-testid="baseButton-headerNoPadding"] {
        background: transparent !important;
        color: #FFFFFF !important;
        border-radius: 0 4px 4px 0 !important;
        z-index: 10000 !important;
        position: relative !important;
    }
    [data-testid="collapsedControl"] svg,
    button[data-testid="baseButton-headerNoPadding"] svg {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }

    /* ── Main content — padding-top clears fixed two-tier header (56 + 50px) ── */
    .block-container { padding-top: 106px !important; max-width: 100% !important;
                       padding-left: 1.5rem !important; padding-right: 1.5rem !important; }
    /* Tighten gap below the tab bar */
    [data-testid="stTabsContent"] { padding-top: 8px !important; }

    /* ── Base text ── */
    body, .stMarkdown, [data-testid="stMarkdownContainer"] { color: #1A1A1A !important; }
    p, li { color: #1A1A1A !important; line-height: 1.6 !important; }
    /* Scope link color to main content only — custom header <a> tags use inline colors */
    [data-testid="stMain"] a, .stMarkdown a { color: #0077C8 !important; }
    [data-testid="stMain"] a:hover, .stMarkdown a:hover { color: #00539B !important; text-decoration: underline !important; }

    /* ── Headings — CB Navy, Open Sans Bold ── */
    h1, h2, h3,
    [data-testid="stHeading"] h1,
    [data-testid="stHeading"] h2,
    [data-testid="stHeading"] h3 {
        color: #00539B !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em !important;
    }
    /* Main content subheaders only — NOT sidebar */
    [data-testid="stMain"] [data-testid="stSubheader"],
    [data-testid="stMain"] [data-testid="stSubheader"] * {
        color: #00539B !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        padding-bottom: 6px !important;
        border-bottom: 2px solid #D1D1D1 !important;
        margin-bottom: 12px !important;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] * { color: #6D6D6D !important; font-size: 0.82rem !important; }

    /* ════════════════════════════════════════════════
       SIDEBAR — College Board Navy
    ════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {
        background: #00539B !important;
        border-right: none !important;
        box-shadow: 2px 0 8px rgba(0,0,0,0.12) !important;
    }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
    section[data-testid="stSidebar"] *:not(button):not([data-testid="baseButton-primary"]):not([data-testid="baseButton-secondary"]) {
        color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSubheader"],
    section[data-testid="stSidebar"] [data-testid="stSubheader"] * {
        color: #BFD9F0 !important;
        border-bottom: 1px solid rgba(255,255,255,0.15) !important;
        padding-bottom: 4px !important;
        margin-bottom: 8px !important;
        font-size: 0.68rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12em !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #FFFFFF !important; font-size: 2rem !important; font-weight: 800 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricDelta"] { color: #BFD9F0 !important; }
    section[data-testid="stSidebar"] [data-testid="stMetricLabel"] { color: #BFD9F0 !important; }
    section[data-testid="stSidebar"] [data-testid="stProgress"] > div {
        background: rgba(255,255,255,0.25) !important; border-radius: 4px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stProgress"] > div > div {
        background: #FFFFFF !important; border-radius: 4px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 6px !important;
    }
    section[data-testid="stSidebar"] hr,
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] hr { border-color: rgba(255,255,255,0.2) !important; }
    section[data-testid="stSidebar"] [data-testid="stAlertContainer"] {
        background: rgba(255,255,255,0.12) !important;
        border-left-color: rgba(255,255,255,0.6) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * { color: #BFD9F0 !important; }

    /* Sidebar buttons */
    section[data-testid="stSidebar"] button {
        font-family: 'Open Sans', sans-serif !important;
        font-weight: 700 !important;
        border-radius: 4px !important;
        min-height: 40px !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.01em !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
        background: #FFFFFF !important;
        color: #00539B !important;
        border: 2px solid #FFFFFF !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] p {
        color: #00539B !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:hover {
        background: #E8F1F9 !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {
        background: transparent !important;
        border: 2px solid rgba(255,255,255,0.5) !important;
        color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] p {
        color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:hover {
        background: rgba(255,255,255,0.15) !important;
        border-color: #FFFFFF !important;
    }

    /* ════════════════════════════════════════════════
       BUTTONS — College Board Style
       Targets every possible Streamlit button selector
       to guarantee color override over emotion-cache.
    ════════════════════════════════════════════════ */

    /* Base reset for ALL Streamlit buttons */
    button[data-testid],
    button[kind] {
        font-family: 'Open Sans', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 0.01em !important;
        border-radius: 4px !important;
        cursor: pointer !important;
        transition: background 0.15s, border-color 0.15s !important;
    }

    /* ── PRIMARY button: CB blue, WHITE text ── */
    button[data-testid="baseButton-primary"],
    button[kind="primary"] {
        background-color: #0077C8 !important;
        border: 2px solid #0077C8 !important;
        color: #FFFFFF !important;
        min-height: 44px !important;
        font-size: 0.9rem !important;
        box-shadow: 0 2px 6px rgba(0,83,155,0.25) !important;
    }
    /* Force white on every child element inside primary buttons */
    button[data-testid="baseButton-primary"] *,
    button[kind="primary"] * {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
    }
    button[data-testid="baseButton-primary"]:hover,
    button[kind="primary"]:hover {
        background-color: #005fa3 !important;
        border-color: #005fa3 !important;
        box-shadow: 0 3px 10px rgba(0,83,155,0.35) !important;
    }

    /* ── SECONDARY button: white bg, CB navy text+border ── */
    button[data-testid="baseButton-secondary"],
    button[kind="secondary"] {
        background-color: #FFFFFF !important;
        border: 2px solid #0077C8 !important;
        color: #00539B !important;
        min-height: 40px !important;
        font-size: 0.85rem !important;
    }
    button[data-testid="baseButton-secondary"] *,
    button[kind="secondary"] * {
        color: #00539B !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
    }
    button[data-testid="baseButton-secondary"]:hover,
    button[kind="secondary"]:hover {
        background-color: #E8F1F9 !important;
        border-color: #00539B !important;
    }
    button[data-testid="baseButton-secondary"]:hover *,
    button[kind="secondary"]:hover * {
        color: #00539B !important;
    }

    /* Sidebar primary = white bg + navy text (inverted) */
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"],
    section[data-testid="stSidebar"] button[kind="primary"] {
        background-color: #FFFFFF !important;
        border-color: #FFFFFF !important;
        color: #00539B !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] *,
    section[data-testid="stSidebar"] button[kind="primary"] * {
        color: #00539B !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"],
    section[data-testid="stSidebar"] button[kind="secondary"] {
        background-color: transparent !important;
        border-color: rgba(255,255,255,0.55) !important;
        color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] *,
    section[data-testid="stSidebar"] button[kind="secondary"] * {
        color: #FFFFFF !important;
    }

    /* ════════════════════════════════════════════════
       TABS — CB navigation underline style
    ════════════════════════════════════════════════ */
    [data-testid="stTabs"] [role="tablist"] {
        overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch;
        background: #FFFFFF !important;
        border-bottom: 2px solid #D1D1D1 !important;
        gap: 0 !important;
        padding: 0 !important;
    }
    [data-testid="stTabs"] [role="tab"] {
        color: #6D6D6D !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 10px 18px !important;
        border-radius: 0 !important;
        border-bottom: 3px solid transparent !important;
        margin-bottom: -2px !important;
        letter-spacing: 0.01em !important;
        transition: color 0.15s, border-color 0.15s !important;
    }
    [data-testid="stTabs"] [role="tab"] p { color: inherit !important; font-size: inherit !important; font-weight: inherit !important; }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        color: #00539B !important;
        border-bottom: 3px solid #00539B !important;
        background: transparent !important;
        font-weight: 700 !important;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] p { color: #00539B !important; font-weight: 700 !important; }
    [data-testid="stTabs"] [role="tab"]:hover {
        color: #0077C8 !important;
        background: #F0F7FF !important;
        border-bottom-color: #BFD9F0 !important;
    }

    /* ════════════════════════════════════════════════
       FORM ELEMENTS — CB clean inputs
    ════════════════════════════════════════════════ */
    /* Labels above inputs */
    [data-testid="stTextInput"] label,
    [data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label,
    [data-testid="stRadio"] label,
    [data-testid="stSlider"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stToggle"] label {
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        color: #1A1A1A !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
    }

    /* Text inputs */
    input[type="text"], input[type="number"],
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        border: 1.5px solid #D1D1D1 !important;
        border-radius: 4px !important;
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        padding: 8px 12px !important;
        font-size: 0.9rem !important;
    }
    input:focus, textarea:focus {
        border-color: #0077C8 !important;
        box-shadow: 0 0 0 3px rgba(0,119,200,0.15) !important;
        outline: none !important;
    }

    /* Textarea / chat */
    [data-testid="stChatInput"] textarea, textarea {
        border: 1.5px solid #D1D1D1 !important;
        border-radius: 4px !important;
        background: #FFFFFF !important;
        color: #1A1A1A !important;
        font-size: 0.9rem !important;
    }
    [data-testid="stChatInput"] textarea:focus { border-color: #0077C8 !important; box-shadow: 0 0 0 3px rgba(0,119,200,0.15) !important; }

    /* Selectbox */
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
        border: 1.5px solid #D1D1D1 !important;
        border-radius: 4px !important;
        background: #FFFFFF !important;
        color: #1A1A1A !important;
    }

    /* Radio options */
    [data-testid="stRadio"] > div { gap: 6px !important; }
    [data-testid="stRadio"] label { font-size: 0.9rem !important; font-weight: 400 !important; text-transform: none !important; letter-spacing: 0 !important; color: #1A1A1A !important; }
    [data-testid="stRadio"] [data-baseweb="radio"] input[type="radio"]:checked + div { background: #0077C8 !important; border-color: #0077C8 !important; }

    /* Slider */
    [data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] { background: #0077C8 !important; border-color: #0077C8 !important; }
    [data-testid="stSlider"] [data-baseweb="slider"] div[data-testid*="track"] > div:first-child { background: #0077C8 !important; }

    /* Toggle */
    [data-testid="stToggle"] input:checked + div { background: #0077C8 !important; }

    /* ════════════════════════════════════════════════
       METRICS & PROGRESS
    ════════════════════════════════════════════════ */
    [data-testid="stMetricValue"] { color: #00539B !important; font-weight: 800 !important; font-size: 1.8rem !important; }
    [data-testid="stMetricLabel"] { color: #6D6D6D !important; font-size: 0.78rem !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; }
    [data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

    [data-testid="stProgress"] > div {
        background: #E8F1F9 !important;
        border-radius: 6px !important;
        height: 8px !important;
    }
    [data-testid="stProgress"] > div > div {
        background: #0077C8 !important;
        border-radius: 6px !important;
        height: 8px !important;
    }

    /* ════════════════════════════════════════════════
       CARDS & CONTAINERS
    ════════════════════════════════════════════════ */
    /* Expanders as cards */
    [data-testid="stExpander"] {
        border: 1px solid #D1D1D1 !important;
        border-radius: 6px !important;
        background: #FFFFFF !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
        overflow: hidden !important;
    }
    [data-testid="stExpander"] summary {
        font-weight: 600 !important;
        color: #1A1A1A !important;
        padding: 12px 16px !important;
        background: #FAFAFA !important;
        border-bottom: 1px solid #E8E8E8 !important;
    }
    [data-testid="stExpander"] summary:hover { background: #F0F7FF !important; }

    /* Chat messages */
    [data-testid="stChatMessage"] {
        background: #F5F5F5 !important;
        border-radius: 8px !important;
        border: 1px solid #E8E8E8 !important;
        margin-bottom: 8px !important;
    }
    /* Assistant message: slight blue tint */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background: #F0F7FF !important;
        border-color: #D0E8F8 !important;
    }

    /* ════════════════════════════════════════════════
       ALERT BANNERS
    ════════════════════════════════════════════════ */
    [data-testid="stAlertContainer"] {
        border-radius: 6px !important;
        border: none !important;
        border-left: 4px solid !important;
        font-size: 0.88rem !important;
    }
    [data-testid="stAlertContainer"][data-baseweb="notification"] {
        background: #E8F1F9 !important;
        border-left-color: #0077C8 !important;
    }
    [data-testid="stAlertContainer"][kind="warning"] {
        background: #FFF8E6 !important;
        border-left-color: #F5A623 !important;
    }
    [data-testid="stAlertContainer"][kind="error"] {
        background: #FDE8EA !important;
        border-left-color: #C8102E !important;
    }
    [data-testid="stAlertContainer"][kind="success"] {
        background: #E6F4EA !important;
        border-left-color: #2D8C4E !important;
    }

    /* ════════════════════════════════════════════════
       MISC
    ════════════════════════════════════════════════ */
    hr { border: none !important; border-top: 1px solid #D1D1D1 !important; margin: 16px 0 !important; }

    /* Quick-action links */
    a[href*="?action="] { transition: color 0.15s; }
    a[href*="?action="]:hover { text-decoration: underline !important; }

    /* Focus rings — CB blue */
    button:focus-visible, a:focus-visible, input:focus-visible, [role="tab"]:focus-visible {
        outline: 2px solid #0077C8 !important;
        outline-offset: 2px !important;
    }

    /* Status widget */
    [data-testid="stStatusWidget"] { border-radius: 6px !important; font-size: 0.85rem !important; }

    /* Download button */
    [data-testid="stDownloadButton"] button {
        background: #0077C8 !important;
        border: 2px solid #0077C8 !important;
        color: #FFFFFF !important;
        border-radius: 4px !important;
        font-weight: 700 !important;
    }
    [data-testid="stDownloadButton"] button p { color: #FFFFFF !important; }
    [data-testid="stDownloadButton"] button:hover { background: #00539B !important; border-color: #00539B !important; }

    /* Code blocks */
    [data-testid="stCode"], .stCode { border-radius: 6px !important; }

    /* ── Skip link ── */
    .skip-link {
        position: absolute; left: -9999px; top: 0.5rem; z-index: 9999;
        background: #00539B; color: #fff !important;
        padding: 0.4rem 0.9rem; border-radius: 4px;
        font-size: 0.85rem; text-decoration: none;
    }
    .skip-link:focus { left: 1rem; }

    /* ── Mobile ── */
    @media screen and (max-width: 600px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            max-width: 100vw !important;
        }
        button[data-testid="baseButton-secondary"] {
            font-size: 0.7rem !important; padding: 2px 5px !important;
        }
        [data-testid="stTabsContent"] button[data-testid="baseButton-secondary"],
        [data-testid="stTabsContent"] button[data-testid="baseButton-primary"] {
            min-height: 44px !important; font-size: 1rem !important;
        }
        input, textarea,
        [data-testid="stChatInput"] textarea,
        [data-testid="stTextInput"] input { font-size: 16px !important; }
        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.1rem !important; }
        [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
        section[data-testid="stSidebar"] { min-width: 240px !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session State Init ─────────────────────────────────────────────────────────

if "active_agent" not in st.session_state:
    st.session_state.active_agent = "math"

if "injected_message" not in st.session_state:
    st.session_state.injected_message = None

for _ak in AGENTS:
    if f"api_messages_{_ak}" not in st.session_state:
        st.session_state[f"api_messages_{_ak}"] = []
    if f"chat_history_{_ak}" not in st.session_state:
        st.session_state[f"chat_history_{_ak}"] = []

# Topic-test state
_TT_DEFAULTS = {
    "tt_phase":        "lobby",   # lobby | generating | taking | reviewing
    "tt_subject":      "math",
    "tt_topic":        None,
    "tt_num_q":        10,
    "tt_difficulty":   "mixed",   # mixed | easy | medium | hard
    "tt_questions":    [],
    "tt_answers":      {},        # {q_idx: str}
    "tt_result_saved": False,     # guards double-save on rerun
    "tt_start_time":   None,      # unix timestamp when taking phase started
    "tt_time_expired": False,     # set True when timer ran out
}

# Seconds per question matching Digital SAT pace
_TT_SECS_PER_Q = {"math": 95, "reading_writing": 71}
for _k, _v in _TT_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Full-test state
_FT_DEFAULTS = {
    "ft_phase":          "lobby",   # lobby|generating|instructions|testing|reviewing|break|score_report
    "ft_test":           {},
    "ft_module_idx":     0,
    "ft_q_idx":          0,
    "ft_answers":        {},        # {mod_idx: {q_idx: str}}
    "ft_flagged":        {},        # {mod_idx: {q_idx: True}}
    "ft_eliminated":     {},        # {mod_idx: {q_idx: [letters]}}
    "ft_module_end_ts":  0.0,       # Unix timestamp when module time expires
    "ft_score_report":   {},
    "ft_gen_log":        [],
}
for _k, _v in _FT_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Resolve active config once — shared by sidebar and main area
cfg       = AGENTS[st.session_state.active_agent]
days_left = days_remaining(cfg)
exam_str  = cfg.exam_date.strftime("%B %d, %Y")
q_done    = get_today_questions(cfg)

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        "<div style='background:#00539B;padding:10px 0 6px'>"
        "<div style='font-size:1.25rem;font-weight:800;color:#FFFFFF;letter-spacing:-0.01em'>🎯 Sasha's SAT Tutor</div>"
        "<div style='font-size:0.7rem;color:#BFD9F0;margin-top:2px;text-transform:uppercase;letter-spacing:0.08em'>College Board Prep</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.12em;color:rgba(191,217,240,0.9);margin:4px 0 6px;"
        "padding-bottom:4px;border-bottom:1px solid rgba(255,255,255,0.15)'>Section</p>",
        unsafe_allow_html=True,
    )
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        if st.button("📐 Math", use_container_width=True,
                     type="primary" if st.session_state.active_agent == "math" else "secondary"):
            st.session_state.active_agent = "math"
            st.rerun()
    with s_col2:
        if st.button("📖 Reading & Writing", use_container_width=True,
                     type="primary" if st.session_state.active_agent == "reading_writing" else "secondary"):
            st.session_state.active_agent = "reading_writing"
            st.rerun()

    st.divider()

    if days_left > 0:
        st.metric("Days Until SAT", days_left, delta=exam_str)
    elif days_left == 0:
        st.metric("SAT Exam Day!", "TODAY 🌟")
    else:
        st.metric("SAT", "Completed")

    st.divider()

    st.markdown(
        "<p style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.12em;color:rgba(191,217,240,0.9);margin:4px 0 6px;"
        "padding-bottom:4px;border-bottom:1px solid rgba(255,255,255,0.15)'>Domain Progress</p>",
        unsafe_allow_html=True,
    )
    data = load_performance(cfg)

    LEVEL_COLORS = {
        0: "#BFD9F0", 1: "#C8102E", 2: "#E8851A",
        3: "#F5A623", 4: "#2D8C4E", 5: "#0077C8",
    }

    for unit in cfg.units:
        u       = data["units"].get(unit, {})
        level   = u.get("level", 0)
        total   = u.get("total", 0)
        correct = u.get("correct", 0)
        weight  = cfg.unit_weights.get(unit, 0)
        color   = LEVEL_COLORS[level]
        bar     = LEVEL_ICONS.get(level, "○○○○○")
        lbl     = LEVEL_NAMES.get(level, "Untested") if level > 0 else "Untested"
        caption = f"{int((correct/total)*100)}% · {lbl}" if total > 0 else "Not yet tested"
        st.markdown(
            f"<div style='margin-bottom:4px'>"
            f"<span style='font-size:0.78em;color:#BFD9F0'>{unit} <span style='color:#9DC8E8'>({weight}%)</span></span><br>"
            f"<span style='font-family:monospace;color:{color}'>{bar}</span> "
            f"<span style='font-size:0.75em;color:#D0E8F8'>{caption}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(
        "<p style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.12em;color:rgba(191,217,240,0.9);margin:4px 0 6px;"
        "padding-bottom:4px;border-bottom:1px solid rgba(255,255,255,0.15)'>Today's Practice</p>",
        unsafe_allow_html=True,
    )
    st.progress(min(q_done / MIN_QUESTIONS, 1.0))
    if q_done >= MIN_QUESTIONS:
        st.success(f"✅ {q_done}/{MIN_QUESTIONS} questions — great work today!")
    else:
        st.warning(f"⚠️ {q_done}/{MIN_QUESTIONS} questions answered today")

    topics = load_weak_topics(cfg)
    if topics:
        st.divider()
        with st.expander(f"⚠️ Weak Topics ({len(topics)})"):
            for t in topics:
                st.markdown(f"• **{t['topic']}** — {t['note']}")

# ── Formula / Strategy Sheet Data ─────────────────────────────────────────────

MATH_FORMULA_SHEET = {
    "Algebra": {
        "icon": "➕",
        "color": "#0ea5e9",
        "formulas": [
            ("Slope-intercept", "y = mx + b"),
            ("Point-slope", "y − y₁ = m(x − x₁)"),
            ("Standard form", "ax + by = c"),
            ("Slope", "m = (y₂−y₁) / (x₂−x₁)"),
            ("Midpoint", "((x₁+x₂)/2, (y₁+y₂)/2)"),
            ("Distance", "d = √((x₂−x₁)² + (y₂−y₁)²)"),
            ("Systems: substitution", "Solve one eq. for a var, substitute into the other"),
            ("Systems: elimination", "Add/subtract equations to eliminate a variable"),
        ],
        "tips": "For systems, check if they ask for x, y, or x+y — sometimes you don't need to solve fully.",
    },
    "Advanced Math": {
        "icon": "∑",
        "color": "#8b5cf6",
        "formulas": [
            ("Quadratic formula", "x = (−b ± √(b²−4ac)) / 2a"),
            ("Vertex form", "y = a(x−h)² + k  (vertex at (h, k))"),
            ("Standard quadratic", "y = ax² + bx + c  (vertex at x = −b/2a)"),
            ("Discriminant", "b²−4ac  (>0 → 2 roots, =0 → 1 root, <0 → no real roots)"),
            ("Factored form", "y = a(x − r₁)(x − r₂)  (roots at r₁, r₂)"),
            ("Exponential growth", "y = a · bˣ  (b > 1 grows, 0 < b < 1 decays)"),
            ("Rational exponent", "x^(m/n) = (ⁿ√x)^m"),
            ("Absolute value", "|x| = a  →  x = a  or  x = −a"),
        ],
        "tips": "For quadratics: factoring is fastest when it works. Use the formula when coefficients are ugly.",
    },
    "Problem Solving & Data Analysis": {
        "icon": "📊",
        "color": "#10b981",
        "formulas": [
            ("Percent", "Part / Whole × 100%"),
            ("Percent change", "(New − Old) / Old × 100%"),
            ("Percent of a percent", "Multiply as decimals: 20% of 30% = 0.20 × 0.30"),
            ("Simple interest", "A = P(1 + rt)"),
            ("Compound interest", "A = P(1 + r/n)^(nt)"),
            ("Unit conversion", "Multiply by fractions that cancel units"),
            ("Mean", "Sum of values / number of values"),
            ("Median", "Middle value when sorted"),
            ("Probability", "P = favorable outcomes / total outcomes"),
        ],
        "tips": "For data questions: read axis labels carefully. Correlation ≠ causation. Watch for outliers.",
    },
    "Geometry & Trigonometry": {
        "icon": "📐",
        "color": "#f59e0b",
        "formulas": [
            ("Circle area", "A = πr²"),
            ("Circle circumference", "C = 2πr"),
            ("Triangle area", "A = ½bh"),
            ("Rectangle area", "A = lw"),
            ("Pythagorean theorem", "a² + b² = c²"),
            ("30-60-90 triangle", "Sides: 1 : √3 : 2"),
            ("45-45-90 triangle", "Sides: 1 : 1 : √2"),
            ("Sphere volume", "V = ⁴⁄₃πr³"),
            ("Cylinder volume", "V = πr²h"),
            ("Cone volume", "V = ⅓πr²h"),
            ("Arc length (radians)", "s = rθ"),
            ("SOH-CAH-TOA", "sin = opp/hyp,  cos = adj/hyp,  tan = opp/adj"),
            ("Pythagorean identity", "sin²θ + cos²θ = 1"),
        ],
        "tips": "The SAT provides area/volume formulas in the test! Memorize Pythagorean theorem and trig ratios.",
    },
}

RW_STRATEGY_SHEET = {
    "Information & Ideas": {
        "icon": "💡",
        "color": "#0ea5e9",
        "formulas": [
            ("Central idea", "What is the passage MAINLY about? Avoid too broad or too narrow."),
            ("Supporting details", "Which detail directly supports the claim? Stay in the text."),
            ("Inferences", "What can be LOGICALLY concluded? Don't over-infer."),
            ("Command of evidence (text)", "Which quote BEST supports the given claim?"),
            ("Command of evidence (data)", "What does the graph/table actually show?"),
        ],
        "tips": "Wrong answers go beyond the text or contradict it. The correct answer is always supported.",
    },
    "Craft & Structure": {
        "icon": "🔍",
        "color": "#8b5cf6",
        "formulas": [
            ("Words in context", "Cover choices, predict meaning from context, then match."),
            ("Text structure", "What purpose does this part serve? (introduces, contrasts, supports…)"),
            ("Author's purpose", "Why did the author write this? What is the overall message?"),
            ("Cross-text connections", "Do passages agree, disagree, or address different aspects?"),
        ],
        "tips": "For Words in Context: the common definition is often the WRONG answer. Context is everything.",
    },
    "Expression of Ideas": {
        "icon": "✍️",
        "color": "#10b981",
        "formulas": [
            ("Rhetorical synthesis", "Which sentence best accomplishes the stated writing goal?"),
            ("Transitions — addition", "furthermore, moreover, in addition, also"),
            ("Transitions — contrast", "however, nevertheless, in contrast, on the other hand"),
            ("Transitions — result", "therefore, consequently, thus, as a result, hence"),
            ("Transitions — example", "for example, for instance, specifically, namely"),
            ("Transitions — sequence", "first, then, finally, subsequently, meanwhile"),
        ],
        "tips": "Identify the RELATIONSHIP between ideas before looking at transition choices. Don't guess.",
    },
    "Standard English Conventions": {
        "icon": "📝",
        "color": "#f59e0b",
        "formulas": [
            ("Run-on fix", "Period / semicolon / comma + coordinating conjunction (FANBOYS)"),
            ("Fragment fix", "Add a subject or verb; make it an independent clause"),
            ("Subject-verb agreement", "Find the true subject — ignore prepositional phrases"),
            ("Pronoun agreement", "Pronoun must match its antecedent in number and gender"),
            ("Verb tense", "Be consistent with the time frame established in the passage"),
            ("Modifier placement", "Modifying phrase must be next to what it modifies"),
            ("Comma rules", "After intro phrase; in a list; around non-essential clause"),
            ("Semicolon", "Joins two INDEPENDENT clauses (no conjunction needed)"),
            ("Colon", "Introduces a list or explanation; must have indie clause before it"),
            ("Apostrophe", "it's = it is;  its = possession;  never use it's for possession"),
        ],
        "tips": "For grammar: always read the FULL sentence. Identify subject + verb first, then check agreement.",
    },
}

FORMULA_SHEETS = {
    "math":           MATH_FORMULA_SHEET,
    "reading_writing": RW_STRATEGY_SHEET,
}

# ── Main Area ──────────────────────────────────────────────────────────────────

_ACTION_MAP = {
    "schedule": "What's my recommended study schedule?",
    "weak":     "Show me my weak topics.",
    "report":   "Give me my full progress report.",
    "diagnose": "Run a full diagnostic and tell me what to study first.",
    "practice": "Make a practice test for the topic I should study most urgently. Generate the printable PDFs.",
}
_action = st.query_params.get("action", "")
if _action in _ACTION_MAP:
    st.query_params.clear()
    st.session_state.injected_message = _ACTION_MAP[_action]
    st.rerun()

_daily_quiz    = st.query_params.get("daily_quiz", "")
_subject_param = st.query_params.get("subject", "")
if _daily_quiz == "true" and _subject_param in AGENTS:
    st.query_params.clear()
    if st.session_state.active_agent != _subject_param:
        st.session_state.active_agent = _subject_param
    _quiz_cfg   = AGENTS[_subject_param]
    _quiz_topic = get_daily_topic(_quiz_cfg)
    st.session_state.injected_message = (
        f"Give me today's daily practice set on **{_quiz_topic}**: "
        f"exactly 5 MCQ questions at moderate difficulty "
        f"(SAT-style, with short passages for Reading & Writing questions). "
        f"Format each MCQ with (A)–(D) options and wait for my answer before revealing the solution."
    )
    st.rerun()

_concepts      = st.query_params.get("concepts", "")
_concept_subj  = st.query_params.get("subject", "")
_concept_topic = st.query_params.get("topic", "")
if _concepts == "true" and _concept_subj in AGENTS:
    st.query_params.clear()
    if st.session_state.active_agent != _concept_subj:
        st.session_state.active_agent = _concept_subj
    _topic_label = _concept_topic or get_daily_topic(AGENTS[_concept_subj])
    st.session_state.injected_message = (
        f"Give me a structured concept summary for **{_topic_label}** — I have a quiz on this today. "
        f"Cover: (1) the 4–5 core concepts I must know, (2) all essential formulas or rules with a one-line "
        f"explanation of when to use each, and (3) the top 3 mistakes students make on the SAT "
        f"for this topic. Keep it concise — I want to read it in under 5 minutes."
    )
    st.rerun()

st.markdown('<a class="skip-link" href="#main-content">Skip to chat</a>', unsafe_allow_html=True)

_goal_icon = "✅" if q_done >= MIN_QUESTIONS else "📝"
_SECTION_COLOR = {"math": "#0077C8", "reading_writing": "#2D8C4E"}
_sec_color  = _SECTION_COLOR.get(st.session_state.active_agent, "#0077C8")
_goal_pct   = min(int(q_done / MIN_QUESTIONS * 100), 100)
_days_color = "#C8102E" if days_left <= 14 else "#FFFFFF"

# Handle topic-test subject toggle (Math / Reading & Writing in-tab switcher)
_tt_switch = st.query_params.get("tt_subject", "")
if _tt_switch in AGENTS:
    st.query_params.clear()
    st.session_state.tt_subject = _tt_switch
    st.session_state.tt_topic   = None
    st.rerun()

# Handle section switch from the tier-2 header switcher
_switch = st.query_params.get("switch_section", "")
if _switch in AGENTS and _switch != st.session_state.active_agent:
    st.query_params.clear()
    st.session_state.active_agent = _switch
    st.rerun()

# Active/inactive colors for section switcher pills
_is_math  = st.session_state.active_agent == "math"
math_bg   = "#0077C8" if _is_math  else "#FFFFFF"
math_txt  = "#FFFFFF"  if _is_math  else "#0077C8"
rw_bg     = "#0077C8" if not _is_math else "#FFFFFF"
rw_txt    = "#FFFFFF"  if not _is_math else "#0077C8"

# ══════════════════════════════════════════════════════════════════════════════
# Custom two-tier header  (Streamlit's own toolbar is hidden via CSS above)
# Tier 1 — Brand bar (dark navy, 56px): logo + countdown + "Practice Test" CTA
# Tier 2 — Quick-action bar (white, 44px): large readable nav links
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    f"""
    <!-- ░░ TIER 1 — Brand bar (fixed, overlays native navy stHeader) ░░ -->
    <div style='
        position:fixed;
        top:0;
        left:0;
        right:0;
        background:#00539B;
        padding:0 24px;
        display:flex;
        flex-direction:row;
        align-items:center;
        justify-content:flex-start;
        height:56px;
        gap:0;
        z-index:995;
        box-sizing:border-box;
        pointer-events:none;
    '>
      <!-- Logo + section name -->
      <div style='display:flex;align-items:center;gap:10px;flex:1'>
        <span style='font-size:1.25rem;font-weight:800;color:#FFFFFF;
                     letter-spacing:-0.02em;line-height:1'>
          {cfg.icon}&nbsp;{cfg.display_name} Tutor
        </span>
        <span style='background:rgba(255,255,255,0.2);color:#FFFFFF;
                     font-size:0.6rem;font-weight:700;text-transform:uppercase;
                     letter-spacing:0.12em;padding:3px 8px;border-radius:2px'>
          SAT&nbsp;PREP
        </span>
      </div>

      <!-- Stats pills -->
      <div style='display:flex;align-items:center;gap:8px;flex-shrink:0;margin-left:20px'>
        <span style='background:rgba(255,255,255,0.15);color:#FFFFFF;font-size:0.78rem;
                     font-weight:600;padding:5px 12px;border-radius:20px;white-space:nowrap'>
          ⏳ {days_left}d to exam
        </span>
        <span style='background:rgba(255,255,255,0.15);color:#FFFFFF;font-size:0.78rem;
                     font-weight:600;padding:5px 12px;border-radius:20px;white-space:nowrap'>
          {_goal_icon} {q_done}/{MIN_QUESTIONS} today
        </span>
      </div>

    </div>

    <!-- ░░ TIER 2 — Section switcher + quick actions (fixed below tier-1) ░░ -->
    <div style='
        position:fixed;
        top:56px;
        left:0;
        right:0;
        background:#FFFFFF;
        border-top:3px solid #C8102E;
        border-bottom:2px solid #D1D1D1;
        padding:0 24px;
        display:flex;
        align-items:center;
        height:50px;
        gap:8px;
        flex-wrap:nowrap;
        z-index:998;
        box-sizing:border-box;
    '>
      <!-- Section switcher — always visible, primary navigation -->
      <div style='display:flex;align-items:center;gap:0;border:2px solid #0077C8;
                  border-radius:5px;overflow:hidden;flex-shrink:0;margin-right:12px'>
        <a href='?switch_section=math'
           style='display:inline-flex;align-items:center;gap:6px;
                  background:{math_bg} !important;color:{math_txt} !important;
                  font-size:0.85rem;font-weight:700;
                  padding:8px 16px;text-decoration:none !important;white-space:nowrap;
                  border-right:1px solid #0077C8;line-height:1.2;
                  font-family:Open Sans,sans-serif'>
          &#x1F4D0; Math
        </a>
        <a href='?switch_section=reading_writing'
           style='display:inline-flex;align-items:center;gap:6px;
                  background:{rw_bg} !important;color:{rw_txt} !important;
                  font-size:0.85rem;font-weight:700;
                  padding:8px 16px;text-decoration:none !important;white-space:nowrap;
                  line-height:1.2;font-family:Open Sans,sans-serif'>
          &#x1F4D6; Reading &amp; Writing
        </a>
      </div>

      <!-- Divider -->
      <span style='width:1px;height:24px;background:#D1D1D1;display:inline-block;margin:0 4px;flex-shrink:0'></span>

      <!-- Quick actions — wrapped in a centered flex row so buttons never stretch -->
      <div style='display:flex;align-items:center;gap:8px;margin-left:auto'>
        <a href='?action=schedule'
           style='display:inline-flex;align-items:center;gap:5px;
                  color:#00539B !important;text-decoration:none !important;font-size:0.82rem;font-weight:600;
                  padding:7px 13px;border-radius:4px;border:1px solid #C2D9EF;
                  background:#F5F5F5;white-space:nowrap;line-height:1.2;font-family:Open Sans,sans-serif'
           onmouseover="this.style.background='#E8F1F9';this.style.borderColor='#0077C8'"
           onmouseout="this.style.background='#F5F5F5';this.style.borderColor='#C2D9EF'">
          &#x1F4C5; Schedule
        </a>
        <a href='?action=weak'
           style='display:inline-flex;align-items:center;gap:5px;
                  color:#00539B !important;text-decoration:none !important;font-size:0.82rem;font-weight:600;
                  padding:7px 13px;border-radius:4px;border:1px solid #C2D9EF;
                  background:#F5F5F5;white-space:nowrap;line-height:1.2;font-family:Open Sans,sans-serif'
           onmouseover="this.style.background='#E8F1F9';this.style.borderColor='#0077C8'"
           onmouseout="this.style.background='#F5F5F5';this.style.borderColor='#C2D9EF'">
          &#x26A0;&#xFE0F; Weak Topics
        </a>
        <a href='?action=report'
           style='display:inline-flex;align-items:center;gap:5px;
                  color:#00539B !important;text-decoration:none !important;font-size:0.82rem;font-weight:600;
                  padding:7px 13px;border-radius:4px;border:1px solid #C2D9EF;
                  background:#F5F5F5;white-space:nowrap;line-height:1.2;font-family:Open Sans,sans-serif'
           onmouseover="this.style.background='#E8F1F9';this.style.borderColor='#0077C8'"
           onmouseout="this.style.background='#F5F5F5';this.style.borderColor='#C2D9EF'">
          &#x1F4CA; Report
        </a>
        <a href='?action=diagnose'
           style='display:inline-flex;align-items:center;gap:5px;
                  color:#00539B !important;text-decoration:none !important;font-size:0.82rem;font-weight:600;
                  padding:7px 13px;border-radius:4px;border:1px solid #C2D9EF;
                  background:#F5F5F5;white-space:nowrap;line-height:1.2;font-family:Open Sans,sans-serif'
           onmouseover="this.style.background='#E8F1F9';this.style.borderColor='#0077C8'"
           onmouseout="this.style.background='#F5F5F5';this.style.borderColor='#C2D9EF'">
          &#x1F9EA; Diagnose
        </a>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

_sheet_label = "📐 Formula Sheet" if st.session_state.active_agent == "math" else "📋 Strategy Sheet"
tab_chat, tab_formulas, tab_calc, tab_tests, tab_topic = st.tabs(
    ["💬 Chat", _sheet_label, "🔢 Calculator", "📝 Full Tests", "📚 Topic Tests"]
)

# ── Formula / Strategy Sheet Tab ──────────────────────────────────────────────

with tab_formulas:
    active_sheet = FORMULA_SHEETS[st.session_state.active_agent]
    if st.session_state.active_agent == "math":
        _sheet_title = "SAT Math — Formula Reference"
        _sheet_sub   = "Key formulas organized by domain. The SAT provides area/volume formulas on the actual test — everything else must be memorized."
    else:
        _sheet_title = "SAT Reading & Writing — Strategy Reference"
        _sheet_sub   = "Core strategies and grammar rules for every question type. Keep this open while you practice!"
    st.markdown(
        f"<div style='margin:16px 0 20px'>"
        f"<h2 style='color:#00539B;font-size:1.35rem;font-weight:800;margin:0 0 4px;"
        f"font-family:\"Open Sans\",sans-serif'>{_sheet_title}</h2>"
        f"<p style='color:#6D6D6D;font-size:0.85rem;margin:0;font-family:\"Open Sans\",sans-serif'>{_sheet_sub}</p>"
        f"<div style='height:3px;background:linear-gradient(90deg,#00539B,#0077C8);border-radius:2px;margin-top:10px'></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    cards_html = ""
    for unit_name, unit_data in active_sheet.items():
        color = unit_data["color"]
        icon  = unit_data["icon"]
        tip   = unit_data["tips"]
        rows  = "".join(
            f"<tr>"
            f"<td style='color:#6D6D6D;font-size:0.8em;padding:3px 10px 3px 0;"
            f"white-space:nowrap;vertical-align:top'>{lbl}</td>"
            f"<td style='font-family:monospace;font-size:0.85em;padding:3px 0;"
            f"color:#1A1A1A;word-break:break-word'>{fml}</td>"
            f"</tr>"
            for lbl, fml in unit_data["formulas"]
        )
        cards_html += (
            f"<div role='region' aria-label='{unit_name}' "
            f"style='background:#FFFFFF;border:1px solid #D1D1D1;"
            f"border-radius:8px;padding:14px 16px;"
            f"box-shadow:0 1px 4px rgba(0,0,0,0.06);'>"
            f"<div style='border-left:4px solid {color};padding:4px 10px;margin-bottom:8px'>"
            f"<span role='heading' aria-level='3' "
            f"style='font-size:1em;font-weight:700;color:{color}'>{icon} {unit_name}</span>"
            f"</div>"
            f"<table style='width:100%;border-collapse:collapse' role='table'>{rows}</table>"
            f"<div role='note' style='font-size:0.78em;color:#6D6D6D;background:#F5F5F5;"
            f"border-radius:5px;padding:6px 9px;margin-top:8px;border-left:3px solid {color}'>💡 {tip}</div>"
            f"</div>"
        )

    st.markdown(
        f"<div style='display:grid;"
        f"grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));"
        f"gap:1rem;margin-top:0.25rem'>{cards_html}</div>",
        unsafe_allow_html=True,
    )

# ── Calculator Tab ────────────────────────────────────────────────────────────

with tab_calc:
    # Pure HTML/JS calculator — uniform 5-column grid, all buttons same size
    components.html("""
<!DOCTYPE html>
<html>
<head>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #fff; padding: 0; }

  .calc-wrap { max-width: 500px; }

  /* Header */
  .calc-title {
    font-size: 1.2rem; font-weight: 800; color: #00539B; margin-bottom: 4px;
  }
  .calc-sub { font-size: 0.8rem; color: #6D6D6D; margin-bottom: 14px; }

  /* Deg toggle */
  .deg-row {
    display: flex; align-items: center; gap: 10px; margin-bottom: 12px;
    font-size: 0.82rem; font-weight: 600; color: #1A1A1A;
  }
  .toggle-wrap { position: relative; display: inline-block; width: 40px; height: 22px; }
  .toggle-wrap input { opacity: 0; width: 0; height: 0; }
  .slider-track {
    position: absolute; cursor: pointer; inset: 0;
    background: #D1D1D1; border-radius: 22px; transition: .2s;
  }
  .slider-track:before {
    content: ""; position: absolute; height: 16px; width: 16px;
    left: 3px; bottom: 3px; background: #fff;
    border-radius: 50%; transition: .2s;
  }
  input:checked + .slider-track { background: #0077C8; }
  input:checked + .slider-track:before { transform: translateX(18px); }

  /* Display */
  .display {
    background: #F5F5F5; border: 2px solid #D1D1D1; border-radius: 8px;
    padding: 12px 16px; margin-bottom: 10px; min-height: 72px;
  }
  .display-expr {
    font-family: 'Courier New', monospace; font-size: 0.85rem;
    color: #6D6D6D; min-height: 1.3em; word-break: break-all;
  }
  .display-result {
    font-family: 'Courier New', monospace; font-size: 1.7rem;
    font-weight: 800; color: #00539B; min-height: 1.2em; margin-top: 2px;
  }
  .display-result.error { color: #C8102E; }

  /* Button grid — 5 equal columns, all buttons same height */
  .btn-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 6px;
  }
  .btn {
    height: 48px;
    display: flex; align-items: center; justify-content: center;
    font-family: inherit; font-size: 0.88rem; font-weight: 700;
    border-radius: 4px; border: 2px solid #0077C8;
    background: #FFFFFF; color: #0077C8;
    cursor: pointer; user-select: none;
    transition: background 0.12s, border-color 0.12s, transform 0.05s;
    white-space: nowrap;
  }
  .btn:hover    { background: #E8F1F9; border-color: #00539B; color: #00539B; }
  .btn:active   { transform: scale(0.95); }

  .btn.fn       { background: #F0F7FF; }          /* function keys: trig, sqrt… */
  .btn.fn:hover { background: #D8ECFC; }
  .btn.op       { background: #FAFAFA; color: #00539B; } /* operators +−×÷ */
  .btn.op:hover { background: #E8F1F9; }
  .btn.clear    { border-color: #C8102E; color: #C8102E; background: #fff; }
  .btn.clear:hover { background: #FDE8EA; }
  .btn.del      { border-color: #6D6D6D; color: #6D6D6D; }
  .btn.del:hover { background: #F5F5F5; }
  .btn.equals   { background: #0077C8; color: #FFFFFF; border-color: #0077C8; }
  .btn.equals:hover { background: #005fa3; border-color: #005fa3; }

  .tip { font-size: 0.74rem; color: #6D6D6D; margin-top: 10px; line-height: 1.5; }
</style>
</head>
<body>
<div class="calc-wrap">

  <div class="calc-title">Scientific Calculator</div>
  <div class="calc-sub">Available for all SAT Math questions (Desmos is built into the digital SAT)</div>

  <div class="deg-row">
    <label class="toggle-wrap">
      <input type="checkbox" id="degToggle" checked onchange="updateDeg()">
      <span class="slider-track"></span>
    </label>
    <span id="degLabel">Degrees</span>
  </div>

  <div class="display">
    <div class="display-expr" id="expr">0</div>
    <div class="display-result" id="result"></div>
  </div>

  <div class="btn-grid">
    <!-- Row 1: trig -->
    <button class="btn fn" onclick="press('sin(')">sin(</button>
    <button class="btn fn" onclick="press('cos(')">cos(</button>
    <button class="btn fn" onclick="press('tan(')">tan(</button>
    <button class="btn fn" onclick="press('log(')">log(</button>
    <button class="btn fn" onclick="press('ln(')">ln(</button>
    <!-- Row 2: functions -->
    <button class="btn fn" onclick="press('sqrt(')">√(</button>
    <button class="btn fn" onclick="press('^')">xʸ</button>
    <button class="btn fn" onclick="press('(')"> ( </button>
    <button class="btn fn" onclick="press(')')"> ) </button>
    <button class="btn fn" onclick="press('π')">π</button>
    <!-- Row 3: misc -->
    <button class="btn clear" onclick="clearAll()">C</button>
    <button class="btn del"   onclick="backspace()">⌫</button>
    <button class="btn fn"    onclick="press('e')">e</button>
    <button class="btn fn"    onclick="press('%')">%</button>
    <button class="btn fn"    onclick="press('1/(')">1/(</button>
    <!-- Row 4: 7 8 9 ÷ √ -->
    <button class="btn" onclick="press('7')">7</button>
    <button class="btn" onclick="press('8')">8</button>
    <button class="btn" onclick="press('9')">9</button>
    <button class="btn op" onclick="press('/')">÷</button>
    <button class="btn fn" onclick="press('sqrt(')">√</button>
    <!-- Row 5: 4 5 6 × ^ -->
    <button class="btn" onclick="press('4')">4</button>
    <button class="btn" onclick="press('5')">5</button>
    <button class="btn" onclick="press('6')">6</button>
    <button class="btn op" onclick="press('*')">×</button>
    <button class="btn fn" onclick="press('^')">xʸ</button>
    <!-- Row 6: 1 2 3 − abs -->
    <button class="btn" onclick="press('1')">1</button>
    <button class="btn" onclick="press('2')">2</button>
    <button class="btn" onclick="press('3')">3</button>
    <button class="btn op" onclick="press('-')">−</button>
    <button class="btn fn" onclick="press('abs(')">|x|</button>
    <!-- Row 7: 0 . = + -->
    <button class="btn" onclick="press('0')">0</button>
    <button class="btn" onclick="press('.')">.</button>
    <button class="btn equals" onclick="calculate()">=</button>
    <button class="btn op" onclick="press('+')">+</button>
    <button class="btn del" onclick="clearAll()">AC</button>
  </div>

  <div class="tip">
    ^ for power &nbsp;·&nbsp; log = log₁₀ &nbsp;·&nbsp; ln = natural log
    &nbsp;·&nbsp; trig uses degrees by default
  </div>
</div>

<script>
let expr = '';
let degMode = true;

function updateDeg() {
  degMode = document.getElementById('degToggle').checked;
  document.getElementById('degLabel').textContent = degMode ? 'Degrees' : 'Radians';
}

function setExpr(v) {
  expr = v;
  document.getElementById('expr').textContent = expr || '0';
}

function press(val) { setExpr(expr + val); }

function clearAll() {
  setExpr('');
  const r = document.getElementById('result');
  r.textContent = '';
  r.className = 'display-result';
}

function backspace() {
  setExpr(expr.slice(0, -1));
  document.getElementById('result').textContent = '';
}

function calculate() {
  const r = document.getElementById('result');
  try {
    let e = expr
      .replace(/π/g, 'Math.PI')
      .replace(/\^/g, '**')
      .replace(/sqrt\(/g, 'Math.sqrt(')
      .replace(/log\(/g, 'Math.log10(')
      .replace(/ln\(/g, 'Math.log(')
      .replace(/abs\(/g, 'Math.abs(');

    if (degMode) {
      e = e
        .replace(/sin\(/g, '__sin(')
        .replace(/cos\(/g, '__cos(')
        .replace(/tan\(/g, '__tan(');
    } else {
      e = e
        .replace(/sin\(/g, 'Math.sin(')
        .replace(/cos\(/g, 'Math.cos(')
        .replace(/tan\(/g, 'Math.tan(');
    }

    function __sin(x) { return Math.sin(x * Math.PI / 180); }
    function __cos(x) { return Math.cos(x * Math.PI / 180); }
    function __tan(x) { return Math.tan(x * Math.PI / 180); }

    // eslint-disable-next-line no-eval
    let raw = eval(e);
    let out = (Number.isFinite(raw) && Math.abs(raw - Math.round(raw)) < 1e-10)
              ? Math.round(raw).toString()
              : parseFloat(raw.toFixed(8)).toString();
    r.className = 'display-result';
    r.textContent = '= ' + out;
  } catch(_) {
    r.className = 'display-result error';
    r.textContent = 'Error';
  }
}

document.addEventListener('keydown', e => {
  const k = e.key;
  if ('0123456789.+-*/%()'.includes(k)) press(k);
  else if (k === 'Enter' || k === '=') calculate();
  else if (k === 'Backspace') backspace();
  else if (k === 'Escape') clearAll();
});
</script>
</body>
</html>
""", height=560, scrolling=False)

# ── Chat Tab ───────────────────────────────────────────────────────────────────

with tab_chat:
    st.markdown('<div id="main-content"></div>', unsafe_allow_html=True)
    agent_key  = st.session_state.active_agent
    chat_key   = f"chat_history_{agent_key}"
    api_key_ss = f"api_messages_{agent_key}"

    if not st.session_state[chat_key]:
        if agent_key == "math":
            starter = "*'Quiz me on Algebra'* or *'Make a practice test for Geometry'* or *'What should I study today?'*"
            extra   = "_Tip: click **📐 Formula Sheet** anytime to look up a formula. The SAT provides area/volume formulas on the actual test!_"
        else:
            starter = "*'Quiz me on grammar'* or *'Explain Words in Context questions'* or *'Give me 5 practice questions'*"
            extra   = "_Tip: click **📋 Strategy Sheet** to review key strategies for each question type. Strategy beats memorization on R&W!_"

        welcome = (
            f"Hi Sasha! 👋 I'm your {cfg.display_name} tutor. You have **{days_left} days** until your SAT on **{exam_str}**.\n\n"
            "Here's what we can do together:\n"
            "- **Diagnose** your strengths and weaknesses across all domains\n"
            "- **Quiz** you with real SAT-style questions at your exact level\n"
            "- **Track** your progress and automatically adjust difficulty\n"
            "- **Plan** your study schedule based on what needs the most attention\n"
            "- **Generate** a printable practice test PDF + answer key for any topic\n\n"
            f"Try saying: {starter}\n\n{extra}"
        )
        st.session_state[chat_key].append(("assistant", welcome))

    for role, text in st.session_state[chat_key]:
        with st.chat_message(role, avatar="🎓" if role == "assistant" else "👩‍🎓"):
            st.markdown(text)

    def _render_pdf_downloads(tool_result: str) -> None:
        tm = re.search(r'Test:\s+(\S.+\.pdf)', tool_result)
        km = re.search(r'Answer Key:\s+(\S.+\.pdf)', tool_result)
        if not (tm and km):
            return
        col1, col2 = st.columns(2)
        test_path = tm.group(1).strip()
        key_path  = km.group(1).strip()
        with col1:
            if os.path.exists(test_path):
                st.download_button("📄 Download Practice Test", open(test_path, "rb").read(),
                                   file_name=os.path.basename(test_path), mime="application/pdf",
                                   use_container_width=True)
        with col2:
            if os.path.exists(key_path):
                st.download_button("🔑 Download Answer Key", open(key_path, "rb").read(),
                                   file_name=os.path.basename(key_path), mime="application/pdf",
                                   use_container_width=True)

    def run_agent(user_text: str):
        ak  = st.session_state.active_agent
        c   = AGENTS[ak]
        chk = f"chat_history_{ak}"
        apk = f"api_messages_{ak}"

        with st.chat_message("user", avatar="👩‍🎓"):
            st.markdown(user_text)
        st.session_state[chk].append(("user", user_text))
        st.session_state[apk].append({"role": "user", "content": user_text})

        try:
            api_key = st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("ANTHROPIC_API_KEY is not set. Go to Manage app → Settings → Secrets and add it.")
            st.stop()
        client = _get_anthropic_client(api_key)

        while True:
            full_text = ""
            assistant_content = []

            with st.chat_message("assistant", avatar="🎓"):
                placeholder = st.empty()

                with client.messages.stream(
                    model=MODEL,
                    max_tokens=8192,
                    thinking={"type": "adaptive"},
                    system=[{
                        "type": "text",
                        "text": c.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    tools=ALL_TOOLS,
                    messages=st.session_state[apk],
                ) as stream:
                    for event in stream:
                        if event.type == "content_block_start":
                            if hasattr(event, "content_block") and event.content_block.type == "tool_use":
                                placeholder.markdown(
                                    (full_text + "\n\n" if full_text else "") +
                                    "⏳ *Composing questions — this takes about 30 seconds…*"
                                )
                        elif event.type == "content_block_delta":
                            if event.delta.type == "text_delta":
                                full_text += event.delta.text
                                placeholder.markdown(full_text + "▌")
                    final_msg = stream.get_final_message()

                if full_text:
                    placeholder.markdown(full_text)
                else:
                    placeholder.empty()

                for block in final_msg.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use", "id": block.id,
                            "name": block.name, "input": block.input,
                        })
                    elif block.type == "thinking":
                        assistant_content.append({
                            "type": "thinking",
                            "thinking": block.thinking,
                            "signature": block.signature,
                        })

                if final_msg.stop_reason == "tool_use":
                    tool_results = []
                    for block in final_msg.content:
                        if block.type == "tool_use":
                            tool_label = block.name.replace("_", " ").title()
                            with st.status(f"Using tool: {tool_label}…", expanded=False) as status:
                                result = execute_tool(block.name, block.input, c)
                                status.update(label=f"✓ {tool_label}", state="complete")
                            if block.name == "generate_practice_test":
                                _render_pdf_downloads(result)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

            st.session_state[apk].append({"role": "assistant", "content": assistant_content})

            if final_msg.stop_reason != "tool_use":
                if full_text:
                    st.session_state[chk].append(("assistant", full_text))
                break

            st.session_state[apk].append({"role": "user", "content": tool_results})

    if st.session_state.injected_message:
        msg = st.session_state.injected_message
        st.session_state.injected_message = None
        run_agent(msg)

    placeholder_text = (
        "Ask me anything, or say 'quiz me on Algebra'…"
        if agent_key == "math"
        else "Ask me anything, or say 'practice grammar questions'…"
    )
    if prompt := st.chat_input(placeholder_text):
        run_agent(prompt)

# ── Full Tests Tab ─────────────────────────────────────────────────────────────

with tab_tests:

    # Inject Bluebook-style CSS only when actively testing
    _in_test_mode = st.session_state.ft_phase in ("testing", "reviewing")
    if _in_test_mode:
        st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        .block-container { padding-top: 0 !important; max-width: 100% !important; }
        </style>
        """, unsafe_allow_html=True)

    # ── Helper: get or resolve API key ────────────────────────────────────────
    def _resolve_api_key() -> str:
        try:
            return st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            return os.environ.get("ANTHROPIC_API_KEY", "")

    # ── Helper: countdown timer HTML component ─────────────────────────────────
    def _render_timer(end_ts: float, module_display: str, q_current: int, q_total: int):
        remaining = max(0, int(end_ts - time.time()))
        color = "#ef4444" if remaining < 60 else ("#f59e0b" if remaining < 300 else "#FFFFFF")
        components.html(f"""
        <div style="background:#00539B;color:#fff;display:flex;align-items:center;
                    justify-content:space-between;padding:10px 24px;
                    font-family:'Open Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                    border-radius:0 0 8px 8px;margin-bottom:4px">
          <span style="font-size:0.95rem;font-weight:600">{module_display}</span>
          <span id="tmr" style="font-size:1.4rem;font-weight:700;font-family:monospace;
                                color:{color}">--:--</span>
          <span style="font-size:0.85rem;opacity:0.85">Question {q_current} of {q_total}</span>
        </div>
        <script>
          var endTs = {end_ts};
          function tick() {{
            var rem = Math.max(0, Math.round(endTs - Date.now()/1000));
            var m = Math.floor(rem/60), s = rem%60;
            var el = document.getElementById('tmr');
            if (!el) return;
            el.textContent = String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
            el.style.color = rem < 60 ? '#ef4444' : rem < 300 ? '#fbbf24' : '#ffffff';
            if (rem > 0) setTimeout(tick, 1000);
            else el.textContent = '00:00 — Time Up';
          }}
          tick();
        </script>
        """, height=64)

    # ── Helper: question navigation grid ──────────────────────────────────────
    def _render_nav_grid(questions: list, answers: dict, flagged: dict, current_q: int):
        cells = ""
        for i, _ in enumerate(questions):
            answered = i in answers and answers[i]
            is_flag  = flagged.get(i, False)
            is_cur   = i == current_q
            if is_cur:
                bg, border, txt = "#00539B", "#00539B", "#fff"
            elif answered and is_flag:
                bg, border, txt = "#fef3c7", "#f59e0b", "#92400e"
            elif answered:
                bg, border, txt = "#dbeafe", "#3b82f6", "#00539B"
            elif is_flag:
                bg, border, txt = "#fff", "#f59e0b", "#92400e"
            else:
                bg, border, txt = "#fff", "#d1d5db", "#374151"
            cells += (
                f"<div style='width:34px;height:34px;border-radius:50%;border:2px solid {border};"
                f"background:{bg};color:{txt};display:flex;align-items:center;justify-content:center;"
                f"font-size:0.75rem;font-weight:600'>{i+1}"
                + ("🚩" if is_flag else "") + "</div>"
            )
        st.markdown(
            f"<div style='display:flex;flex-wrap:wrap;gap:6px;padding:10px 0'>{cells}</div>",
            unsafe_allow_html=True,
        )

    # ── Helper: render one question ────────────────────────────────────────────
    def _render_question(q: dict, mod_idx: int, q_idx: int):
        ss     = st.session_state
        mod_a  = ss.ft_answers.setdefault(mod_idx, {})
        mod_f  = ss.ft_flagged.setdefault(mod_idx, {})
        mod_e  = ss.ft_eliminated.setdefault(mod_idx, {})
        elim   = mod_e.get(q_idx, [])

        # Passage
        passage = q.get("passage", "").strip()
        if passage:
            st.markdown(
                f"<div style='background:#f0f4f9;border-left:4px solid #00539B;"
                f"padding:14px 18px;border-radius:0 8px 8px 0;margin-bottom:16px;"
                f"font-size:0.95rem;line-height:1.65;color:#1a1a2e'>{passage}</div>",
                unsafe_allow_html=True,
            )

        # Question stem
        st.markdown(
            f"<div style='font-size:1rem;font-weight:600;margin-bottom:14px;"
            f"color:#111827;line-height:1.5'>{q['question']}</div>",
            unsafe_allow_html=True,
        )

        if q.get("type") == "spr":
            # Grid-in / student-produced response
            st.caption("Enter your answer (numbers only — no units needed):")
            current_val = mod_a.get(q_idx, "")
            new_val = st.text_input(
                "Your answer", value=current_val,
                key=f"spr_{mod_idx}_{q_idx}",
                label_visibility="collapsed",
                placeholder="Enter numeric answer…",
            )
            if new_val != current_val:
                mod_a[q_idx] = new_val
                st.rerun()
        else:
            # MCQ choices
            choices = q.get("choices", [])
            labels  = []
            for ch in choices:
                letter = ch[0] if ch else "?"
                label  = ("~~" + ch + "~~") if letter in elim else ch
                labels.append(label)

            current = mod_a.get(q_idx)
            idx_map  = {ch[0]: i for i, ch in enumerate(choices) if ch}
            cur_idx  = idx_map.get(current[0] if current else None)

            selected = st.radio(
                "Choose your answer:",
                options=choices,
                index=cur_idx,
                key=f"mcq_{mod_idx}_{q_idx}",
                label_visibility="collapsed",
                format_func=lambda c: ("🚫 " if c[0] in elim else "") + c,
            )
            if selected:
                mod_a[q_idx] = selected[0]

        st.divider()

        # Flag + Eliminate controls
        flag_col, elim_col = st.columns([1, 3])
        with flag_col:
            is_flagged = mod_f.get(q_idx, False)
            if st.button(
                "🚩 Unflag" if is_flagged else "🚩 Flag for Review",
                key=f"flag_{mod_idx}_{q_idx}",
                use_container_width=True,
            ):
                mod_f[q_idx] = not is_flagged
                st.rerun()
        with elim_col:
            if q.get("type") == "mcq":
                choices = q.get("choices", [])
                letters = [c[0] for c in choices if c]
                new_elim = st.multiselect(
                    "Cross out (eliminate):",
                    options=letters,
                    default=elim,
                    key=f"elim_{mod_idx}_{q_idx}",
                )
                if set(new_elim) != set(elim):
                    mod_e[q_idx] = new_elim
                    st.rerun()

    # ── Phase: lobby ──────────────────────────────────────────────────────────
    if st.session_state.ft_phase == "lobby":
        st.markdown(
            "<div style='margin:16px 0 20px'>"
            "<h2 style='color:#00539B;font-size:1.35rem;font-weight:800;margin:0 0 4px;"
            "font-family:\"Open Sans\",sans-serif'>📝 Full-Length SAT Practice Tests</h2>"
            "<p style='color:#6D6D6D;font-size:0.85rem;margin:0;font-family:\"Open Sans\",sans-serif'>"
            "Four-module adaptive test — R&amp;W Module 1 → R&amp;W Module 2 → Math Module 1 → Math Module 2. "
            "Each module is timed. Questions are AI-generated in the style of the Digital SAT (Bluebook).</p>"
            "<div style='height:3px;background:linear-gradient(90deg,#00539B,#0077C8);border-radius:2px;margin-top:10px'></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.info(
            "**Before you start:** Generation takes ~3–5 minutes (Claude writes 98 questions). "
            "Once saved, you can retake or review any test from the list below.",
            icon="ℹ️",
        )

        if st.button("🚀 Generate New Full-Length Test", type="primary", use_container_width=True):
            api_key = _resolve_api_key()
            if not api_key:
                st.error("ANTHROPIC_API_KEY not set.")
            else:
                st.session_state.ft_phase    = "generating"
                st.session_state.ft_gen_log  = []
                st.rerun()

        saved = list_saved_tests()
        if saved:
            st.divider()
            st.markdown(
                "<div style='margin:16px 0 12px;padding-bottom:8px;"
                "border-bottom:2px solid #D1D1D1'>"
                "<span style='color:#00539B;font-size:1rem;font-weight:700;"
                "font-family:\"Open Sans\",sans-serif'>Saved Tests</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            for t in saved:
                created = t["created_at"][:16].replace("T", " ") if t.get("created_at") else "?"
                col_info, col_start, col_review = st.columns([3, 1, 1])
                with col_info:
                    st.markdown(f"**{t['id']}** · {created}")
                with col_start:
                    if st.button("▶ Take", key=f"take_{t['id']}", use_container_width=True):
                        test_data = load_test(t["id"])
                        st.session_state.ft_test       = test_data
                        st.session_state.ft_module_idx = 0
                        st.session_state.ft_q_idx      = 0
                        st.session_state.ft_answers    = {}
                        st.session_state.ft_flagged    = {}
                        st.session_state.ft_eliminated = {}
                        st.session_state.ft_phase      = "instructions"
                        st.rerun()
                with col_review:
                    if st.session_state.ft_score_report and st.session_state.ft_test.get("id") == t["id"]:
                        if st.button("📊 Results", key=f"res_{t['id']}", use_container_width=True):
                            st.session_state.ft_phase = "score_report"
                            st.rerun()

    # ── Phase: generating ─────────────────────────────────────────────────────
    elif st.session_state.ft_phase == "generating":
        st.subheader("Generating your full-length SAT practice test…")
        st.caption("Claude is writing 98 questions across 4 modules in small batches. This takes about 3–5 minutes.")

        api_key = _resolve_api_key()
        client  = _get_anthropic_client(api_key)

        log_container = st.empty()
        progress_bar  = st.progress(0)

        # Total batches across all 4 modules (ceil(27/10)*2 + ceil(22/10)*2 = 3*2 + 3*2 = 12)
        _TOTAL_BATCHES = sum(
            math.ceil(mc["num_questions"] / 10) for mc in MODULE_CONFIGS
        )
        gen_log: list[str] = []

        def on_status(msg: str):
            gen_log.append(msg)
            log_container.markdown("\n\n".join(gen_log))
            done = sum(1 for m in gen_log if m.startswith("✅"))
            progress_bar.progress(min(done / _TOTAL_BATCHES, 1.0))

        try:
            test_data = generate_full_test(client, on_status=on_status)
            save_test(test_data)
            st.session_state.ft_test       = test_data
            st.session_state.ft_module_idx = 0
            st.session_state.ft_q_idx      = 0
            st.session_state.ft_answers    = {}
            st.session_state.ft_flagged    = {}
            st.session_state.ft_eliminated = {}
            st.session_state.ft_phase      = "instructions"
            st.rerun()
        except Exception as e:
            import traceback
            st.error(f"Generation failed: {e}")
            st.code(traceback.format_exc(), language="text")
            if st.button("← Back to Lobby"):
                st.session_state.ft_phase = "lobby"
                st.rerun()

    # ── Phase: instructions ───────────────────────────────────────────────────
    elif st.session_state.ft_phase == "instructions":
        mod_idx = st.session_state.ft_module_idx
        module  = st.session_state.ft_test["modules"][mod_idx]
        cfg     = MODULE_CONFIGS[mod_idx]

        st.markdown(
            f"<div style='background:#00539B;color:#fff;border-radius:8px;"
            f"padding:28px 32px;margin-bottom:24px'>"
            f"<div style='font-size:0.8rem;opacity:0.75;text-transform:uppercase;"
            f"letter-spacing:0.08em;margin-bottom:4px'>Section {mod_idx + 1} of 4</div>"
            f"<h2 style='margin:0 0 8px;font-size:1.5rem'>{module['display']}</h2>"
            f"<div style='font-size:1rem;opacity:0.9'>"
            f"⏱ {cfg['time_minutes']} minutes &nbsp;·&nbsp; "
            f"{len(module['questions'])} questions</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        section = module["section"]
        if section == "reading_writing":
            st.markdown("""
**Reading & Writing directions:**
- Each question is based on a short passage. Read it carefully before answering.
- Choose the single best answer (A, B, C, or D).
- You can flag questions to revisit before submitting.
- You can eliminate answer choices using the cross-out tool.
            """)
        else:
            st.markdown("""
**Math directions:**
- Most questions are multiple choice (A–D). Some are student-produced response (grid-in) — enter a number.
- A calculator (Desmos) is available. Use the **🔢 Calculator** tab for complex calculations.
- You can flag questions and cross out choices.
- For grid-in answers: enter a decimal or integer (e.g. 3.5 or 7). Do not include units.
            """)

        st.markdown("---")
        col_back, col_start = st.columns([1, 2])
        with col_back:
            if st.button("← Back to Lobby", use_container_width=True):
                st.session_state.ft_phase = "lobby"
                st.rerun()
        with col_start:
            if st.button(f"Begin Module →", type="primary", use_container_width=True):
                end_ts = time.time() + cfg["time_minutes"] * 60
                st.session_state.ft_module_end_ts = end_ts
                st.session_state.ft_q_idx         = 0
                st.session_state.ft_phase         = "testing"
                st.rerun()

    # ── Phase: testing ────────────────────────────────────────────────────────
    elif st.session_state.ft_phase == "testing":
        mod_idx   = st.session_state.ft_module_idx
        module    = st.session_state.ft_test["modules"][mod_idx]
        questions = module["questions"]
        q_idx     = st.session_state.ft_q_idx
        q         = questions[q_idx]
        mod_a     = st.session_state.ft_answers.get(mod_idx, {})
        mod_f     = st.session_state.ft_flagged.get(mod_idx, {})
        end_ts    = st.session_state.ft_module_end_ts

        # Timer
        _render_timer(end_ts, module["display"], q_idx + 1, len(questions))

        # Time-up check (enforced on each interaction)
        if time.time() > end_ts:
            st.warning("⏰ Time is up for this module. Your answers have been saved.")
            if st.button("Go to Review & Submit →", type="primary"):
                st.session_state.ft_phase = "reviewing"
                st.rerun()
        else:
            # Navigation grid
            _render_nav_grid(questions, mod_a, mod_f, q_idx)

            answered_count = sum(1 for i in range(len(questions)) if mod_a.get(i))
            flagged_count  = sum(1 for i in range(len(questions)) if mod_f.get(i))
            st.caption(
                f"✅ {answered_count}/{len(questions)} answered  "
                f"{'· 🚩 ' + str(flagged_count) + ' flagged' if flagged_count else ''}"
            )
            st.divider()

            # Question
            _render_question(q, mod_idx, q_idx)

            # Bottom navigation
            nav_l, nav_jump, nav_r, nav_review = st.columns([1, 2, 1, 2])
            with nav_l:
                if q_idx > 0 and st.button("⬅ Previous", use_container_width=True):
                    st.session_state.ft_q_idx = q_idx - 1
                    st.rerun()
            with nav_jump:
                jump = st.number_input(
                    "Go to Q#", min_value=1, max_value=len(questions),
                    value=q_idx + 1, step=1, key="q_jump",
                    label_visibility="collapsed",
                )
                if jump - 1 != q_idx:
                    st.session_state.ft_q_idx = jump - 1
                    st.rerun()
            with nav_r:
                if q_idx < len(questions) - 1:
                    if st.button("Next ➡", type="primary", use_container_width=True):
                        st.session_state.ft_q_idx = q_idx + 1
                        st.rerun()
            with nav_review:
                if st.button("📋 Review & Submit", use_container_width=True):
                    st.session_state.ft_phase = "reviewing"
                    st.rerun()

    # ── Phase: reviewing ──────────────────────────────────────────────────────
    elif st.session_state.ft_phase == "reviewing":
        mod_idx   = st.session_state.ft_module_idx
        module    = st.session_state.ft_test["modules"][mod_idx]
        questions = module["questions"]
        mod_a     = st.session_state.ft_answers.get(mod_idx, {})
        mod_f     = st.session_state.ft_flagged.get(mod_idx, {})

        st.subheader(f"Review — {module['display']}")

        answered  = [i for i in range(len(questions)) if mod_a.get(i)]
        unanswered = [i for i in range(len(questions)) if not mod_a.get(i)]
        flagged   = [i for i in range(len(questions)) if mod_f.get(i)]

        col_s, col_u, col_f = st.columns(3)
        col_s.metric("Answered", len(answered))
        col_u.metric("Unanswered", len(unanswered), delta=f"−{len(unanswered)}" if unanswered else None,
                     delta_color="inverse")
        col_f.metric("Flagged", len(flagged))

        if unanswered:
            st.warning(f"⚠️ {len(unanswered)} question(s) unanswered: {[i+1 for i in unanswered]}")
        if flagged:
            st.info(f"🚩 Flagged for review: Q{[i+1 for i in flagged]}")

        st.divider()

        # Question status grid (click to go back)
        st.caption("Click a question number to return to it:")
        cols = st.columns(9)
        for i in range(len(questions)):
            ans = mod_a.get(i, "")
            flg = mod_f.get(i, False)
            label = f"{'🚩' if flg else ''}{i+1}"
            btn_type = "primary" if ans else "secondary"
            with cols[i % 9]:
                if st.button(label, key=f"rev_jump_{i}", type=btn_type, use_container_width=True):
                    st.session_state.ft_q_idx = i
                    st.session_state.ft_phase = "testing"
                    st.rerun()

        st.divider()

        back_col, submit_col = st.columns([1, 2])
        with back_col:
            if st.button("← Back to Test", use_container_width=True):
                st.session_state.ft_phase = "testing"
                st.rerun()
        with submit_col:
            n_modules = len(st.session_state.ft_test["modules"])
            is_last   = mod_idx >= n_modules - 1
            btn_label = "✅ Submit Test & See Results" if is_last else "✅ Submit Module & Continue →"
            if st.button(btn_label, type="primary", use_container_width=True):
                if is_last:
                    report = score_test(st.session_state.ft_test, st.session_state.ft_answers)
                    st.session_state.ft_score_report = report
                    st.session_state.ft_phase        = "score_report"
                else:
                    st.session_state.ft_module_idx += 1
                    st.session_state.ft_q_idx       = 0
                    st.session_state.ft_phase       = "break"
                st.rerun()

    # ── Phase: break ──────────────────────────────────────────────────────────
    elif st.session_state.ft_phase == "break":
        mod_idx     = st.session_state.ft_module_idx
        next_module = st.session_state.ft_test["modules"][mod_idx]
        prev_module = st.session_state.ft_test["modules"][mod_idx - 1]
        cfg         = MODULE_CONFIGS[mod_idx]

        # Show a section break between R&W and Math (after module index 1)
        is_section_break = (mod_idx == 2)

        st.markdown(
            f"<div style='text-align:center;padding:40px 20px'>"
            f"<div style='font-size:3rem'>{'☕' if is_section_break else '✅'}</div>"
            f"<h2 style='margin:16px 0 8px'>"
            f"{'Section Break — 10 minutes' if is_section_break else 'Module Complete!'}"
            f"</h2>"
            f"<p style='color:#6b7280;font-size:1rem'>"
            f"You've completed: <strong>{prev_module['display']}</strong><br>"
            f"Up next: <strong>{next_module['display']}</strong> "
            f"({cfg['time_minutes']} min · {len(next_module['questions'])} questions)"
            f"</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if is_section_break:
            st.info("Take a 10-minute break. Stretch, get water. Come back when you're ready.", icon="☕")

        if st.button(f"Start {next_module['display']} →", type="primary", use_container_width=True):
            end_ts = time.time() + cfg["time_minutes"] * 60
            st.session_state.ft_module_end_ts = end_ts
            st.session_state.ft_phase         = "instructions"
            st.rerun()

    # ── Phase: score_report ───────────────────────────────────────────────────
    elif st.session_state.ft_phase == "score_report":
        report = st.session_state.ft_score_report
        if not report:
            st.warning("No score report found.")
            if st.button("← Back to Lobby"):
                st.session_state.ft_phase = "lobby"
                st.rerun()
        else:
            total = report["total_scaled"]
            rw_s  = report["rw_scaled"]
            math_s = report["math_scaled"]

            # Score banner
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#00539B,#0077C8);"
                f"color:#fff;border-radius:8px;padding:32px;text-align:center;margin-bottom:24px'>"
                f"<div style='font-size:0.85rem;opacity:0.8;text-transform:uppercase;"
                f"letter-spacing:0.1em;margin-bottom:8px'>Estimated SAT Score</div>"
                f"<div style='font-size:4rem;font-weight:800;line-height:1'>{total}</div>"
                f"<div style='font-size:0.9rem;opacity:0.7;margin-top:4px'>out of 1600</div>"
                f"<div style='display:flex;justify-content:center;gap:48px;margin-top:20px'>"
                f"<div><div style='font-size:1.8rem;font-weight:700'>{rw_s}</div>"
                f"<div style='font-size:0.8rem;opacity:0.75'>Reading & Writing</div></div>"
                f"<div style='border-left:1px solid rgba(255,255,255,0.3)'></div>"
                f"<div><div style='font-size:1.8rem;font-weight:700'>{math_s}</div>"
                f"<div style='font-size:0.8rem;opacity:0.75'>Math</div></div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.caption("⚠️ Scores are estimates based on approximate College Board scaling tables.")

            # Domain breakdown
            st.markdown(
                "<div style='margin:16px 0 12px;padding-bottom:8px;"
                "border-bottom:2px solid #D1D1D1'>"
                "<span style='color:#00539B;font-size:1.1rem;font-weight:700;"
                "font-family:\"Open Sans\",sans-serif'>Domain Breakdown</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            domain_scores = report.get("domain_scores", {})
            cols = st.columns(2)
            for i, (domain, ds) in enumerate(sorted(domain_scores.items())):
                correct = ds["correct"]
                total_d = ds["total"]
                pct     = int(correct / total_d * 100) if total_d else 0
                bar_col = "#22c55e" if pct >= 70 else "#f59e0b" if pct >= 50 else "#ef4444"
                with cols[i % 2]:
                    st.markdown(
                        f"<div style='background:#f8fafc;border-radius:8px;padding:12px 16px;margin-bottom:10px'>"
                        f"<div style='font-weight:600;font-size:0.9rem;margin-bottom:6px'>{domain}</div>"
                        f"<div style='background:#e5e7eb;border-radius:4px;height:8px;margin-bottom:6px'>"
                        f"<div style='background:{bar_col};width:{pct}%;height:8px;border-radius:4px'></div></div>"
                        f"<div style='font-size:0.8rem;color:#6b7280'>{correct}/{total_d} correct · {pct}%</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            # Answer review
            st.divider()
            st.markdown(
                "<div style='margin:16px 0 12px;padding-bottom:8px;"
                "border-bottom:2px solid #D1D1D1'>"
                "<span style='color:#00539B;font-size:1.1rem;font-weight:700;"
                "font-family:\"Open Sans\",sans-serif'>Question-by-Question Review</span>"
                "</div>",
                unsafe_allow_html=True,
            )

            results = report.get("question_results", [])
            last_module = None
            for r in results:
                if r["module"] != last_module:
                    st.markdown(f"**{r['module']}**")
                    last_module = r["module"]

                icon   = "✅" if r["is_correct"] else "❌"
                given  = r["given"] or "—"
                correct = r["correct"]

                with st.expander(
                    f"{icon} Q{r['number']} · {r['domain']} · "
                    f"Your answer: **{given}** · Correct: **{correct}**"
                ):
                    if r.get("passage"):
                        st.markdown(
                            f"<div style='background:#f0f4f9;border-left:3px solid #00539B;"
                            f"padding:10px 14px;border-radius:0 6px 6px 0;margin-bottom:10px;"
                            f"font-size:0.88rem;color:#374151'>{r['passage']}</div>",
                            unsafe_allow_html=True,
                        )
                    st.markdown(f"**{r['question']}**")
                    if r.get("choices"):
                        for ch in r["choices"]:
                            if ch[0] == correct:
                                mark = " ✅"
                            elif given != "—" and ch[0] == given[0]:
                                mark = " ❌"
                            else:
                                mark = ""
                            st.markdown(f"{'→ ' if ch[0] == correct else '&nbsp;&nbsp; '}{ch}{mark}")
                    st.markdown(f"**Explanation:** {r['explanation']}")

            st.divider()
            if st.button("← Back to Lobby", use_container_width=True):
                st.session_state.ft_phase = "lobby"
                st.rerun()

# ── Topic Tests Tab ────────────────────────────────────────────────────────────

with tab_topic:
    _tt = st.session_state

    # ── Helper: resolve API key (reuse from full tests) ────────────────────────
    def _tt_api_key() -> str:
        try:
            return st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            return os.environ.get("ANTHROPIC_API_KEY", "")

    # ── Phase: lobby ──────────────────────────────────────────────────────────
    if _tt.tt_phase == "lobby":
        # ── Page title ────────────────────────────────────────────────────────
        st.markdown(
            "<div style='padding:20px 0 4px'>"
            "<h2 style='color:#00539B;font-size:1.4rem;font-weight:800;margin:0 0 4px;"
            "font-family:\"Open Sans\",sans-serif;letter-spacing:-0.01em'>Topic Tests</h2>"
            "<p style='color:#6D6D6D;font-size:0.875rem;margin:0;line-height:1.5'>"
            "Pick a topic, set difficulty, and get a focused mini-test with instant Khan Academy review links.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<hr style='border:none;border-top:2px solid #D1D1D1;margin:0 0 20px'>", unsafe_allow_html=True)

        # ── Two-column layout: controls left, preview card right ──────────────
        ctrl_col, card_col = st.columns([1, 1], gap="large")

        with ctrl_col:
            _tt_is_math = _tt.tt_subject == "math"
            # Active = solid blue fill; inactive = light grey with grey text
            _math_bg  = "#0077C8" if _tt_is_math  else "#F0F0F0"
            _math_txt = "#FFFFFF"  if _tt_is_math  else "#888888"
            _rw_bg    = "#0077C8" if not _tt_is_math else "#F0F0F0"
            _rw_txt   = "#FFFFFF"  if not _tt_is_math else "#888888"
            st.markdown(
                "<label style='font-size:0.72rem;font-weight:700;text-transform:uppercase;"
                "letter-spacing:0.08em;color:#6D6D6D;display:block;margin-bottom:6px'>Section</label>",
                unsafe_allow_html=True,
            )
            _subj_col_math, _subj_col_rw = st.columns(2, gap="small")
            with _subj_col_math:
                if st.button("📐 Math", use_container_width=True,
                             type="primary" if _tt_is_math else "secondary",
                             key="tt_subj_math"):
                    st.session_state.tt_subject = "math"
                    st.session_state.tt_topic = None
            with _subj_col_rw:
                if st.button("📖 Reading & Writing", use_container_width=True,
                             type="primary" if not _tt_is_math else "secondary",
                             key="tt_subj_rw"):
                    st.session_state.tt_subject = "reading_writing"
                    st.session_state.tt_topic = None

            topics_for_subj = TOPIC_CATALOG[_tt.tt_subject]

            # Build ordered domain list preserving catalog order
            _seen_domains = []
            for _t in topics_for_subj:
                if _t["domain"] not in _seen_domains:
                    _seen_domains.append(_t["domain"])
            _domains = _seen_domains

            # Default domain from previously chosen topic
            _default_domain_idx = 0
            if _tt.tt_topic and _tt.tt_topic.get("domain") in _domains:
                _default_domain_idx = _domains.index(_tt.tt_topic["domain"])

            chosen_domain = st.selectbox(
                "Domain",
                options=_domains,
                index=_default_domain_idx,
                key="tt_domain_select",
            )

            # Filter topics to selected domain
            _domain_topics = [t for t in topics_for_subj if t["domain"] == chosen_domain]
            _topic_labels  = [t["label"] for t in _domain_topics]
            _default_topic_idx = 0
            if _tt.tt_topic and _tt.tt_topic.get("label") in _topic_labels:
                _default_topic_idx = _topic_labels.index(_tt.tt_topic["label"])

            chosen_label = st.selectbox(
                "Topic",
                options=_topic_labels,
                index=_default_topic_idx,
                key="tt_topic_select",
            )
            chosen_topic = next(t for t in _domain_topics if t["label"] == chosen_label)

            d_col, n_col = st.columns(2)
            _DIFF_OPTIONS = ["mixed", "easy", "medium", "hard"]
            _DIFF_LABELS  = {"mixed": "Mixed", "easy": "Easy", "medium": "Medium", "hard": "Hard"}
            with d_col:
                diff_choice = st.selectbox(
                    "Difficulty",
                    options=_DIFF_OPTIONS,
                    index=_DIFF_OPTIONS.index(_tt.tt_difficulty),
                    format_func=lambda d: _DIFF_LABELS[d],
                    key="tt_diff_select",
                )
            with n_col:
                num_q = st.select_slider(
                    "Questions",
                    options=[5, 8, 10, 15, 20],
                    value=_tt.tt_num_q,
                    key="tt_num_q_slider",
                )

            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            # Generate button — full-width, prominent
            _btn_label = f"Generate {num_q}-Question Test →"
            if st.button(_btn_label, type="primary", use_container_width=True, key="tt_gen_btn"):
                pass  # handled below

        # ── Right: Topic preview card ─────────────────────────────────────────
        with card_col:
            _diff_badge_color = {
                "mixed": "#6366f1", "easy": "#2D8C4E",
                "medium": "#C8830E", "hard": "#C8102E",
            }
            _dc = _diff_badge_color.get(diff_choice, "#6366f1")
            st.markdown(
                f"<div style='background:#F0F7FF;border:1px solid #C2D9EF;border-radius:10px;"
                f"padding:22px 24px;margin-top:28px;height:100%'>"

                # Domain badge
                f"<div style='font-size:0.68rem;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:0.1em;color:#0077C8;margin-bottom:10px'>"
                f"{chosen_topic['domain']}</div>"

                # Topic title
                f"<div style='font-size:1.15rem;font-weight:800;color:#00539B;"
                f"line-height:1.25;margin-bottom:10px'>{chosen_topic['label']}</div>"

                # Difficulty + count badges
                f"<div style='display:flex;gap:8px;margin-bottom:14px'>"
                f"<span style='font-size:0.72rem;font-weight:700;padding:3px 10px;"
                f"border-radius:12px;background:{_dc}14;color:{_dc};"
                f"border:1px solid {_dc}44'>{_DIFF_LABELS[diff_choice]}</span>"
                f"<span style='font-size:0.72rem;font-weight:700;padding:3px 10px;"
                f"border-radius:12px;background:#00539B14;color:#00539B;"
                f"border:1px solid #00539B44'>{num_q} questions</span>"
                f"</div>"

                # Subtopics
                f"<p style='font-size:0.82rem;color:#374151;line-height:1.55;margin-bottom:14px'>"
                f"{chosen_topic['subtopics']}</p>"

                # KA link
                f"<a href='{chosen_topic['ka_url']}' target='_blank' "
                f"style='display:inline-flex;align-items:center;gap:6px;font-size:0.8rem;"
                f"font-weight:600;color:#0077C8;text-decoration:none;"
                f"border:1px solid #C2D9EF;padding:6px 12px;border-radius:6px;"
                f"background:#FFFFFF'>"
                f"📖 Review on Khan Academy ↗</a>"

                f"</div>",
                unsafe_allow_html=True,
            )

        # ── Generate logic (triggered by button above) ────────────────────────
        if st.session_state.get("tt_gen_btn"):
            if not _tt_api_key():
                st.error("ANTHROPIC_API_KEY not set.")
            else:
                _tt.tt_topic        = chosen_topic
                _tt.tt_num_q        = num_q
                _tt.tt_difficulty   = diff_choice
                _tt.tt_questions    = []
                _tt.tt_answers      = {}
                _tt.tt_result_saved = False
                _tt.tt_phase        = "generating"
                st.rerun()

        # ── Performance Dashboard ──────────────────────────────────────────────
        st.divider()
        st.markdown(
            "<div style='margin:16px 0 20px'>"
            "<h2 style='color:#00539B;font-size:1.2rem;font-weight:800;margin:0 0 4px;"
            "font-family:\"Open Sans\",sans-serif'>Performance Dashboard</h2>"
            "<div style='height:3px;background:linear-gradient(90deg,#00539B,#0077C8);border-radius:2px;margin-top:8px'></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        math_hist = load_topic_history("math")
        rw_hist   = load_topic_history("reading_writing")
        all_hist  = math_hist + rw_hist

        if not all_hist:
            st.info("No topic tests completed yet. Generate your first test above!")
        else:
            # Score prediction
            pred = predict_sat_score(math_hist, rw_hist)
            if pred:
                p_cols = st.columns(len(pred))
                labels = {"math_scaled": "Math", "rw_scaled": "Reading & Writing", "total": "Predicted Total"}
                colors = {"math_scaled": "#0077C8", "rw_scaled": "#2D8C4E", "total": "#00539B"}
                for col, (key, val) in zip(p_cols, pred.items()):
                    with col:
                        st.markdown(
                            f"<div style='background:#FFFFFF;border:2px solid {colors[key]};"
                            f"border-radius:8px;padding:14px;text-align:center;"
                            f"box-shadow:0 2px 6px rgba(0,0,0,0.08)'>"
                            f"<div style='font-size:0.75rem;color:#6D6D6D;text-transform:uppercase;"
                            f"letter-spacing:0.07em;font-weight:600'>{labels[key]}</div>"
                            f"<div style='font-size:2.2rem;font-weight:800;color:{colors[key]}'>{val}</div>"
                            f"<div style='font-size:0.72rem;color:#6D6D6D'>estimated</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                st.caption("Score estimate based on weighted domain performance across topic tests.")
                st.markdown("")

            # Weak topics
            math_analysis = analyze_topic_performance("math")
            rw_analysis   = analyze_topic_performance("reading_writing")
            weak_math = math_analysis["weak_topics"]
            weak_rw   = rw_analysis["weak_topics"]

            if weak_math or weak_rw:
                st.markdown("**Areas needing attention** (below 70%)")
                w_cols = st.columns(2)
                with w_cols[0]:
                    st.caption("Math")
                    if weak_math:
                        for t in weak_math:
                            s = math_analysis["topic_stats"][t]
                            pct_color = "#ef4444" if s["pct"] < 50 else "#f59e0b"
                            st.markdown(
                                f"<span style='color:{pct_color};font-weight:600'>{s['pct']}%</span>"
                                f" &nbsp; {t}",
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("None — great work!")
                with w_cols[1]:
                    st.caption("Reading & Writing")
                    if weak_rw:
                        for t in weak_rw:
                            s = rw_analysis["topic_stats"][t]
                            pct_color = "#ef4444" if s["pct"] < 50 else "#f59e0b"
                            st.markdown(
                                f"<span style='color:{pct_color};font-weight:600'>{s['pct']}%</span>"
                                f" &nbsp; {t}",
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("None — great work!")
                st.markdown("")

            # Topic history table
            with st.expander("All topic test results", expanded=False):
                for subj_label, hist, analysis in [
                    ("Math", math_hist, math_analysis),
                    ("Reading & Writing", rw_hist, rw_analysis),
                ]:
                    if not hist:
                        continue
                    st.markdown(f"**{subj_label}**")
                    rows = []
                    for r in reversed(hist):
                        taken = r["taken_at"][:10]
                        pct   = r["pct"]
                        flag  = " ⚠️" if pct < 70 else (" ✅" if pct >= 85 else "")
                        rows.append(f"| {taken} | {r['topic']} | {r['domain']} | {r['correct']}/{r['total']} | {pct}%{flag} |")
                    st.markdown(
                        "| Date | Topic | Domain | Score | % |\n"
                        "|------|-------|--------|-------|---|\n" +
                        "\n".join(rows)
                    )

    # ── Phase: generating ─────────────────────────────────────────────────────
    elif _tt.tt_phase == "generating":
        topic = _tt.tt_topic
        st.subheader(f"Generating: {topic['label']}")

        status_box  = st.empty()
        progress_bar = st.progress(0)

        def _tt_status(msg: str):
            status_box.markdown(msg)
            progress_bar.progress(0.5)

        try:
            api_key = _tt_api_key()
            client  = _get_anthropic_client(api_key)
            questions = generate_topic_test(
                client,
                subject=_tt.tt_subject,
                topic=topic,
                num_questions=_tt.tt_num_q,
                difficulty=_tt.tt_difficulty,
                on_status=_tt_status,
            )
            progress_bar.progress(1.0)
            if not questions:
                st.error("No questions were generated. Please try again.")
                if st.button("← Back"):
                    _tt.tt_phase = "lobby"
                    st.rerun()
            else:
                _tt.tt_questions    = questions
                _tt.tt_answers      = {}
                _tt.tt_start_time   = time.time()
                _tt.tt_time_expired = False
                _tt.tt_phase        = "taking"
                st.rerun()
        except Exception as e:
            import traceback
            st.error(f"Generation failed: {e}")
            st.code(traceback.format_exc(), language="text")
            if st.button("← Back to Topic Lobby"):
                _tt.tt_phase = "lobby"
                st.rerun()

    # ── Phase: taking ─────────────────────────────────────────────────────────
    elif _tt.tt_phase == "taking":
        topic     = _tt.tt_topic
        questions = _tt.tt_questions

        # ── Timer setup ───────────────────────────────────────────────────────
        _secs_per_q  = _TT_SECS_PER_Q.get(_tt.tt_subject, 90)
        _time_limit  = len(questions) * _secs_per_q
        _start       = _tt.get("tt_start_time") or time.time()
        if _tt.get("tt_start_time") is None:
            _tt.tt_start_time = _start
        _elapsed     = time.time() - _start
        _remaining   = max(0.0, _time_limit - _elapsed)

        # Auto-submit if time is up (triggered by JS page reload)
        if _elapsed >= _time_limit and not _tt.get("tt_time_expired"):
            _tt.tt_time_expired = True
            _tt.tt_phase        = "reviewing"
            st.rerun()

        _tt_diff      = _tt.get("tt_difficulty", "mixed")
        _diff_colors  = {"mixed": "#6366f1", "easy": "#22c55e", "medium": "#f59e0b", "hard": "#ef4444"}
        _diff_dc      = _diff_colors.get(_tt_diff, "#6366f1")

        _timer_mins = int(_remaining // 60)
        _timer_secs = int(_remaining % 60)
        _low_time   = _remaining < 120   # last 2 minutes
        _timer_color = "#ef4444" if _remaining < 60 else "#f59e0b" if _low_time else "#22c55e"

        st.markdown(
            f"<div style='background:#00539B;color:#fff;border-radius:8px;"
            f"padding:16px 20px;margin-bottom:16px'>"
            f"<div style='display:flex;justify-content:space-between;align-items:flex-start'>"
            f"<div>"
            f"<div style='font-size:0.75rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.08em'>Topic Test</div>"
            f"<div style='display:flex;align-items:center;gap:10px;margin-top:2px'>"
            f"<span style='font-size:1.25rem;font-weight:700'>{topic['label']}</span>"
            f"<span style='font-size:0.72em;font-weight:600;padding:2px 8px;border-radius:20px;"
            f"background:{_diff_dc}33;color:{_diff_dc};border:1px solid {_diff_dc}55'>"
            f"{_tt_diff.capitalize()}</span>"
            f"</div>"
            f"<div style='font-size:0.85rem;opacity:0.8;margin-top:4px'>"
            f"{len(questions)} questions · calculator allowed</div>"
            f"<div style='margin-top:8px;font-size:0.82rem'>"
            f"📖 Review while you work: "
            f"<a href='{topic['ka_url']}' target='_blank' "
            f"style='color:#BFD9F0;text-decoration:underline'>{topic['ka_label']}</a>"
            f"</div>"
            f"</div>"
            f"<div style='text-align:right;flex-shrink:0;margin-left:16px'>"
            f"<div style='font-size:0.7rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px'>Time Remaining</div>"
            f"<div id='tt-timer' style='font-size:2rem;font-weight:800;color:{_timer_color};"
            f"font-variant-numeric:tabular-nums;letter-spacing:0.02em'>"
            f"{_timer_mins:02d}:{_timer_secs:02d}</div>"
            f"</div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # JS countdown — ticks from server-computed remaining; reloads page at 0
        components.html(
            f"""<script>
            (function() {{
              let rem = {int(_remaining)};
              const el = window.parent.document.getElementById('tt-timer');
              if (!el) return;
              const tick = () => {{
                if (rem <= 0) {{
                  el.textContent = '00:00';
                  el.style.color = '#ef4444';
                  window.parent.location.reload();
                  return;
                }}
                const m = Math.floor(rem / 60);
                const s = rem % 60;
                el.textContent = String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
                el.style.color = rem < 60 ? '#ef4444' : rem < 120 ? '#f59e0b' : '#22c55e';
                rem--;
                setTimeout(tick, 1000);
              }};
              tick();
            }})();
            </script>""",
            height=0,
        )

        if _low_time:
            st.warning(f"⏰ {'Less than 1 minute' if _remaining < 60 else 'Under 2 minutes'} remaining!")

        answered = sum(1 for i in range(len(questions)) if _tt.tt_answers.get(i))
        st.caption(f"✅ {answered}/{len(questions)} answered")
        st.divider()

        for q_idx, q in enumerate(questions):
            q_num    = q.get("number", q_idx + 1)
            q_type   = q.get("type", "mcq")
            passage  = q.get("passage", "").strip()
            question = q.get("question", "")
            choices  = q.get("choices", [])
            diff     = q.get("difficulty", "")
            diff_color = {"easy": "#22c55e", "medium": "#f59e0b", "hard": "#ef4444"}.get(diff, "#888")

            st.markdown(
                f"<div style='display:flex;align-items:baseline;gap:8px;margin-bottom:6px'>"
                f"<span style='font-weight:700;font-size:1rem'>Q{q_num}.</span>"
                f"<span style='font-size:0.75em;color:{diff_color};font-weight:600'>{diff.upper()}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            if passage:
                st.markdown(
                    f"<div style='background:#f0f4f9;border-left:4px solid #00539B;"
                    f"padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:10px;"
                    f"font-size:0.9rem;line-height:1.6;color:#1a1a2e'>{passage}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown(
                f"<div style='font-size:0.95rem;font-weight:600;margin-bottom:10px'>{question}</div>",
                unsafe_allow_html=True,
            )

            if q_type == "spr":
                st.caption("Grid-in — enter a number:")
                current_val = _tt.tt_answers.get(q_idx, "")
                new_val = st.text_input(
                    f"Answer Q{q_num}",
                    value=current_val,
                    key=f"tt_spr_{q_idx}",
                    label_visibility="collapsed",
                    placeholder="Enter numeric answer…",
                )
                if new_val != current_val:
                    _tt.tt_answers[q_idx] = new_val
            else:
                current = _tt.tt_answers.get(q_idx)
                idx_map = {ch[0]: i for i, ch in enumerate(choices) if ch}
                cur_idx = idx_map.get(current[0] if current else None)

                selected = st.radio(
                    f"Answer Q{q_num}",
                    options=choices,
                    index=cur_idx,
                    key=f"tt_mcq_{q_idx}",
                    label_visibility="collapsed",
                )
                if selected:
                    _tt.tt_answers[q_idx] = selected[0]

            st.divider()

        col_back, col_submit = st.columns([1, 2])
        with col_back:
            if st.button("← Back to Lobby", use_container_width=True):
                _tt.tt_phase = "lobby"
                st.rerun()
        with col_submit:
            answered_final = sum(1 for i in range(len(questions)) if _tt.tt_answers.get(i))
            unanswered = len(questions) - answered_final
            warn = f" ({unanswered} unanswered)" if unanswered else ""
            if st.button(f"✅ Submit & See Results{warn}", type="primary", use_container_width=True):
                _tt.tt_phase = "reviewing"
                st.rerun()

    # ── Phase: reviewing ─────────────────────────────────────────────────────
    elif _tt.tt_phase == "reviewing":
        topic     = _tt.tt_topic
        questions = _tt.tt_questions
        answers   = _tt.tt_answers

        # Score
        correct_count = 0
        results = []
        for q_idx, q in enumerate(questions):
            given   = answers.get(q_idx, "").strip().upper()
            correct = q.get("correct_answer", "").strip().upper()
            if q.get("type") == "spr":
                try:
                    is_correct = abs(float(given) - float(correct)) < 0.01
                except ValueError:
                    is_correct = given == correct
            else:
                is_correct = bool(given) and bool(correct) and given[0] == correct[0]
            if is_correct:
                correct_count += 1
            results.append({**q, "given": answers.get(q_idx, ""), "is_correct": is_correct})

        pct = int(correct_count / len(questions) * 100) if questions else 0
        score_color = "#22c55e" if pct >= 75 else "#f59e0b" if pct >= 50 else "#ef4444"

        # Persist result once per test
        if not _tt.get("tt_result_saved", False) and questions:
            save_topic_result(
                _tt.tt_subject,
                topic["label"],
                topic.get("domain", ""),
                correct_count,
                len(questions),
            )
            _tt.tt_result_saved = True

        _rev_diff     = _tt.get("tt_difficulty", "mixed")
        _rev_dc       = {"mixed": "#6366f1", "easy": "#22c55e", "medium": "#f59e0b", "hard": "#ef4444"}.get(_rev_diff, "#6366f1")
        _timed_out    = _tt.get("tt_time_expired", False)
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#00539B,#0077C8);"
            f"color:#fff;border-radius:8px;padding:24px 28px;text-align:center;margin-bottom:20px'>"
            f"<div style='font-size:0.8rem;opacity:0.75;text-transform:uppercase;"
            f"letter-spacing:0.1em;margin-bottom:6px'>"
            f"{'⏰ Time\'s Up — Auto-submitted' if _timed_out else 'Topic Test Results'}</div>"
            f"<div style='display:inline-flex;align-items:center;gap:10px;margin-bottom:8px'>"
            f"<span style='font-size:1.2rem;font-weight:700'>{topic['label']}</span>"
            f"<span style='font-size:0.7em;font-weight:600;padding:2px 8px;border-radius:20px;"
            f"background:{_rev_dc}44;color:{_rev_dc};border:1px solid {_rev_dc}66'>"
            f"{_rev_diff.capitalize()}</span>"
            f"</div>"
            f"<div style='font-size:3.5rem;font-weight:800;color:{score_color};line-height:1'>"
            f"{correct_count}/{len(questions)}</div>"
            f"<div style='font-size:1rem;opacity:0.85;margin-top:4px'>{pct}% correct</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # KA review link banner
        st.markdown(
            f"<div style='background:#E8F1F9;border:1px solid #0077C8;border-radius:6px;"
            f"padding:12px 16px;margin-bottom:16px;font-size:0.88rem'>"
            f"📖 <strong style='color:#00539B'>Review this topic:</strong> "
            f"<a href='{topic['ka_url']}' target='_blank' style='color:#0077C8;font-weight:600'>"
            f"{topic['ka_label']}</a>"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.subheader("Question Review")

        for q_idx, r in enumerate(results):
            q_num   = r.get("number", q_idx + 1)
            given   = r.get("given") or "—"
            correct = r.get("correct_answer", "")
            icon    = "✅" if r["is_correct"] else "❌"
            diff    = r.get("difficulty", "")

            with st.expander(
                f"{icon} Q{q_num} · {diff} · "
                f"Your answer: **{given}** · Correct: **{correct}**",
                expanded=not r["is_correct"],
            ):
                if r.get("passage"):
                    st.markdown(
                        f"<div style='background:#f0f4f9;border-left:3px solid #00539B;"
                        f"padding:10px 14px;border-radius:0 6px 6px 0;margin-bottom:10px;"
                        f"font-size:0.88rem;color:#374151'>{r['passage']}</div>",
                        unsafe_allow_html=True,
                    )
                st.markdown(f"**{r['question']}**")

                if r.get("choices"):
                    for ch in r["choices"]:
                        letter = ch[0] if ch else "?"
                        if letter == correct[0] if correct else False:
                            marker = " ✅"
                        elif given != "—" and letter == (given[0] if given else ""):
                            marker = " ❌"
                        else:
                            marker = ""
                        arrow = "→ " if (correct and letter == correct[0]) else "   "
                        st.markdown(f"{arrow}{ch}{marker}")

                st.markdown(f"**Explanation:** {r.get('explanation', '')}")

                # Per-question KA link — specific to the concept this question tests
                from topic_test import concept_ka_url
                concept = r.get("concept", "").strip()
                if concept:
                    q_ka_url   = concept_ka_url(concept)
                    q_ka_label = concept
                else:
                    q_ka_url   = topic["ka_url"]
                    q_ka_label = topic["ka_label"]
                st.markdown(
                    f"<div style='margin-top:8px;padding:8px 12px;background:#E8F1F9;"
                    f"border-radius:6px;font-size:0.82em;border-left:3px solid #0077C8'>"
                    f"📖 <strong style='color:#00539B'>Review on Khan Academy:</strong> "
                    f"<a href='{q_ka_url}' target='_blank' style='color:#0077C8;font-weight:600'>"
                    f"{q_ka_label}</a></div>",
                    unsafe_allow_html=True,
                )

        st.divider()
        col_retry, col_new = st.columns(2)
        with col_retry:
            if st.button("🔄 Retry Same Topic", use_container_width=True):
                _tt.tt_questions    = []
                _tt.tt_answers      = {}
                _tt.tt_result_saved = False
                _tt.tt_start_time   = None
                _tt.tt_time_expired = False
                _tt.tt_phase        = "generating"
                st.rerun()
        with col_new:
            if st.button("← Choose New Topic", use_container_width=True):
                _tt.tt_start_time   = None
                _tt.tt_time_expired = False
                _tt.tt_phase        = "lobby"
                st.rerun()
