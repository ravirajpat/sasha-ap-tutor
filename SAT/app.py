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

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .skip-link {
        position: absolute; left: -9999px; top: 0.5rem; z-index: 9999;
        background: #0ea5e9; color: #fff !important;
        padding: 0.4rem 0.9rem; border-radius: 0.4rem;
        font-size: 0.85rem; text-decoration: none;
    }
    .skip-link:focus { left: 1rem; }

    [data-testid="stDecoration"] { display: none !important; }
    header[data-testid="stHeader"] { background: transparent !important; }
    .block-container { padding-top: 1rem !important; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 0.75rem !important; }

    button[data-testid="baseButton-secondary"] {
        background: transparent !important;
        border: 1px solid rgba(49,51,63,0.5) !important;
        color: rgb(49,51,63) !important;
        font-size: 0.8rem !important;
        font-weight: 400 !important;
        min-height: 30px !important;
        padding: 2px 10px !important;
        border-radius: 0.4rem !important;
        touch-action: manipulation;
    }
    button[data-testid="baseButton-secondary"]:hover {
        background: rgba(49,51,63,0.08) !important;
        border-color: rgba(49,51,63,0.7) !important;
    }
    a[href*="?action="] { transition: opacity 0.15s; }
    a[href*="?action="]:hover { text-decoration: underline !important; opacity: 0.75; }

    button:focus-visible, a:focus-visible {
        outline: 2px solid #0ea5e9 !important;
        outline-offset: 2px !important;
    }
    section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {
        font-size: 0.85rem !important;
        min-height: 38px !important;
        padding: 4px 12px !important;
    }
    button[data-testid="baseButton-primary"] { touch-action: manipulation; }

    [data-testid="stTabs"] [role="tablist"] {
        overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch;
    }

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
    "tt_phase":    "lobby",   # lobby | generating | taking | reviewing
    "tt_subject":  "math",
    "tt_topic":    None,
    "tt_num_q":    10,
    "tt_questions": [],
    "tt_answers":  {},        # {q_idx: str}
}
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
    st.title("🎯 Sasha's SAT Tutor")

    st.subheader("Section")
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

    st.subheader("Domain Progress")
    data = load_performance(cfg)

    LEVEL_COLORS = {
        0: "#888888", 1: "#e74c3c", 2: "#e67e22",
        3: "#f1c40f", 4: "#2ecc71", 5: "#00b4d8",
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
            f"<span style='font-size:0.78em;color:#ccc'>{unit} <span style='color:#888'>({weight}%)</span></span><br>"
            f"<span style='font-family:monospace;color:{color}'>{bar}</span> "
            f"<span style='font-size:0.75em;color:#aaa'>{caption}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("Today's Practice")
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

# Accent color per section
_ACCENT = {"math": "#0ea5e9", "reading_writing": "#10b981"}
_ls_color = _ACCENT.get(st.session_state.active_agent, "#0ea5e9")
_ls = f"color:{_ls_color};text-decoration:none;font-size:0.8rem;white-space:nowrap"

st.markdown(
    f"<div style='display:flex;align-items:center;flex-wrap:wrap;"
    f"gap:0.4rem 1rem;padding:6px 0 4px'>"
    f"<span style='font-size:1.25rem;font-weight:700;line-height:1.2'>"
    f"{cfg.icon} {cfg.display_name} Tutor</span>"
    f"<span style='font-size:0.78rem;color:#888;white-space:nowrap' "
    f"title='Days until SAT'>⏳ {days_left}d left</span>"
    f"<span style='font-size:0.78rem;color:#888;white-space:nowrap' "
    f"title='Questions answered today vs daily goal'>{_goal_icon} {q_done}/{MIN_QUESTIONS} today</span>"
    f"<span style='margin-left:auto;display:flex;align-items:center;"
    f"gap:0.25rem 0.6rem;flex-wrap:wrap'>"
    f"<a href='?action=schedule' style='{_ls}' title='Get a personalised study schedule'>📅 Schedule</a>"
    f"<span style='color:#ccc'>·</span>"
    f"<a href='?action=weak' style='{_ls}' title='See your weak topics'>⚠️ Weak Topics</a>"
    f"<span style='color:#ccc'>·</span>"
    f"<a href='?action=report' style='{_ls}' title='View full progress report'>📊 Report</a>"
    f"<span style='color:#ccc'>·</span>"
    f"<a href='?action=diagnose' style='{_ls}' title='Run a diagnostic'>🧪 Diagnose</a>"
    f"<span style='color:#ccc'>·</span>"
    f"<a href='?action=practice' style='{_ls}' title='Generate a printable practice test PDF'>📄 Practice Test</a>"
    f"</span>"
    f"</div>",
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
        st.subheader("SAT Math — Formula Reference")
        st.caption("Key formulas organized by domain. The SAT provides area/volume formulas — everything else you need to memorize!")
    else:
        st.subheader("SAT Reading & Writing — Strategy Reference")
        st.caption("Core strategies and grammar rules for every question type. Keep this open while you practice!")

    cards_html = ""
    for unit_name, unit_data in active_sheet.items():
        color = unit_data["color"]
        icon  = unit_data["icon"]
        tip   = unit_data["tips"]
        rows  = "".join(
            f"<tr>"
            f"<td style='color:#bbb;font-size:0.8em;padding:3px 10px 3px 0;"
            f"white-space:nowrap;vertical-align:top'>{lbl}</td>"
            f"<td style='font-family:monospace;font-size:0.85em;padding:3px 0;"
            f"color:#f0f0f0;word-break:break-word'>{fml}</td>"
            f"</tr>"
            for lbl, fml in unit_data["formulas"]
        )
        cards_html += (
            f"<div role='region' aria-label='{unit_name}' "
            f"style='background:#0e1117;border:1px solid #2a2a3e;"
            f"border-radius:10px;padding:14px 16px;'>"
            f"<div style='border-left:4px solid {color};padding:4px 10px;margin-bottom:8px'>"
            f"<span role='heading' aria-level='3' "
            f"style='font-size:1em;font-weight:700;color:{color}'>{icon} {unit_name}</span>"
            f"</div>"
            f"<table style='width:100%;border-collapse:collapse' role='table'>{rows}</table>"
            f"<div role='note' style='font-size:0.78em;color:#b0b0b0;background:#12121f;"
            f"border-radius:5px;padding:6px 9px;margin-top:8px'>💡 {tip}</div>"
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
    if "calc_expr" not in st.session_state:
        st.session_state.calc_expr = ""
    if "calc_result" not in st.session_state:
        st.session_state.calc_result = ""
    if "calc_deg" not in st.session_state:
        st.session_state.calc_deg = True

    def _make_ctx(deg_mode: bool) -> dict:
        if deg_mode:
            trig = {
                "sin":  lambda x: math.sin(math.radians(x)),
                "cos":  lambda x: math.cos(math.radians(x)),
                "tan":  lambda x: math.tan(math.radians(x)),
                "asin": lambda x: math.degrees(math.asin(x)),
                "acos": lambda x: math.degrees(math.acos(x)),
                "atan": lambda x: math.degrees(math.atan(x)),
            }
        else:
            trig = {
                "sin": math.sin, "cos": math.cos, "tan": math.tan,
                "asin": math.asin, "acos": math.acos, "atan": math.atan,
            }
        trig.update({
            "sqrt": math.sqrt, "log": math.log10, "ln": math.log,
            "abs": abs, "pi": math.pi, "e": math.e,
            "floor": math.floor, "ceil": math.ceil,
        })
        return trig

    def _calc_press(val: str):
        if val == "C":
            st.session_state.calc_expr = ""
            st.session_state.calc_result = ""
        elif val == "⌫":
            st.session_state.calc_expr = st.session_state.calc_expr[:-1]
            st.session_state.calc_result = ""
        elif val == "=":
            try:
                expr = (
                    st.session_state.calc_expr
                    .replace("^", "**")
                    .replace("π", "pi")
                    .replace("√(", "sqrt(")
                )
                ctx = _make_ctx(st.session_state.calc_deg)
                raw = eval(expr, {"__builtins__": {}}, ctx)  # noqa: S307
                if isinstance(raw, float) and raw.is_integer():
                    st.session_state.calc_result = str(int(raw))
                else:
                    st.session_state.calc_result = f"{raw:.8g}"
            except Exception:
                st.session_state.calc_result = "Error — check expression"
        else:
            st.session_state.calc_expr += val

    st.markdown("<div style='max-width:480px;margin:0 auto'>", unsafe_allow_html=True)
    st.subheader("Scientific Calculator")
    st.caption("Available for all SAT Math questions (Desmos is built into the digital SAT)")

    deg_col, _ = st.columns([1, 3])
    with deg_col:
        st.session_state.calc_deg = st.toggle(
            "Degrees", value=st.session_state.calc_deg,
            help="Toggle between degrees and radians for trig functions"
        )

    expr_display = st.session_state.calc_expr or "0"
    result_display = f"= {st.session_state.calc_result}" if st.session_state.calc_result else ""
    st.markdown(
        f"<div style='background:#0e1117;border:1px solid #333;border-radius:8px;"
        f"padding:12px 16px;margin-bottom:8px;min-height:64px'>"
        f"<div style='color:#888;font-size:0.85em;font-family:monospace;min-height:1.2em'>{expr_display}</div>"
        f"<div style='color:#fff;font-size:1.6em;font-weight:700;font-family:monospace'>{result_display}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    ROWS = [
        [("sin(","sin("), ("cos(","cos("), ("tan(","tan("), ("log(","log("), ("ln(","ln(")],
        [("√(","√("),    ("xʸ","^"),       ("(",  "("),     (")",  ")"),     ("π", "π")],
        [("C", "C"),     ("⌫","⌫"),         ("e",  "e"),    ("%",  "%"),     ("1/(","1/(")],
        [("7","7"),      ("8","8"),          ("9","9"),       ("÷","/")],
        [("4","4"),      ("5","5"),          ("6","6"),       ("×","*")],
        [("1","1"),      ("2","2"),          ("3","3"),       ("−","-")],
        [("0","0"),      (".","."  ),        ("=","="),       ("+","+")],
    ]
    PRIMARY_VALS = {"="}

    for r_idx, row in enumerate(ROWS):
        cols = st.columns(len(row))
        for c_idx, (label, val) in enumerate(row):
            btn_type = "primary" if val in PRIMARY_VALS else "secondary"
            with cols[c_idx]:
                if st.button(label, key=f"calc_btn_{r_idx}_{c_idx}",
                             use_container_width=True, type=btn_type):
                    _calc_press(val)
                    st.rerun()

    st.caption("Tip: ^ for power · log = log₁₀ · ln = natural log · trig in degrees by default")
    st.markdown("</div>", unsafe_allow_html=True)

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
        color = "#ef4444" if remaining < 60 else ("#f59e0b" if remaining < 300 else "#ffffff")
        components.html(f"""
        <div style="background:#1e3a5f;color:#fff;display:flex;align-items:center;
                    justify-content:space-between;padding:10px 24px;
                    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
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
                bg, border, txt = "#1e3a5f", "#1e3a5f", "#fff"
            elif answered and is_flag:
                bg, border, txt = "#fef3c7", "#f59e0b", "#92400e"
            elif answered:
                bg, border, txt = "#dbeafe", "#3b82f6", "#1e3a5f"
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
                f"<div style='background:#f0f4f9;border-left:4px solid #1e3a5f;"
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
        st.subheader("📝 Full-Length SAT Practice Tests")
        st.caption(
            "Four-module adaptive test — R&W Module 1 → R&W Module 2 → Math Module 1 → Math Module 2. "
            "Each module is timed. Questions are AI-generated in the style of the Digital SAT (Bluebook)."
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
            st.subheader("Saved Tests")
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
        st.caption("Claude is writing 98 questions across 4 modules. This takes about 3–5 minutes.")

        api_key = _resolve_api_key()
        client  = _get_anthropic_client(api_key)

        log_container = st.empty()
        progress_bar  = st.progress(0)

        gen_log: list[str] = []

        def on_status(msg: str):
            gen_log.append(msg)
            log_container.markdown("\n\n".join(gen_log))
            done = sum(1 for m in gen_log if m.startswith("✅"))
            progress_bar.progress(done / len(MODULE_CONFIGS))

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
            f"<div style='background:#1e3a5f;color:#fff;border-radius:12px;"
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
                f"<div style='background:linear-gradient(135deg,#1e3a5f,#2563eb);"
                f"color:#fff;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px'>"
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
            st.subheader("Domain Breakdown")
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
            st.subheader("Question-by-Question Review")

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
                            f"<div style='background:#f0f4f9;border-left:3px solid #1e3a5f;"
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
        st.subheader("📚 Topic Tests")
        st.caption(
            "Generate a focused mini-test on any SAT topic. "
            "Every question comes with a Khan Academy review link so you can go deep on anything you miss."
        )

        col_subj, col_topic, col_n = st.columns([1, 2, 1])

        with col_subj:
            subj_choice = st.radio(
                "Section",
                options=["math", "reading_writing"],
                format_func=lambda s: "📐 Math" if s == "math" else "📖 Reading & Writing",
                index=0 if _tt.tt_subject == "math" else 1,
                key="tt_subj_radio",
            )
            if subj_choice != _tt.tt_subject:
                _tt.tt_subject = subj_choice
                _tt.tt_topic   = None
                st.rerun()

        topics_for_subj = TOPIC_CATALOG[_tt.tt_subject]
        topic_labels    = [t["label"] for t in topics_for_subj]
        default_idx     = 0
        if _tt.tt_topic and _tt.tt_topic.get("label") in topic_labels:
            default_idx = topic_labels.index(_tt.tt_topic["label"])

        with col_topic:
            chosen_label = st.selectbox(
                "Topic",
                options=topic_labels,
                index=default_idx,
                key="tt_topic_select",
            )
            chosen_topic = next(t for t in topics_for_subj if t["label"] == chosen_label)

        with col_n:
            num_q = st.select_slider(
                "# of Questions",
                options=[5, 8, 10, 15, 20],
                value=_tt.tt_num_q,
                key="tt_num_q_slider",
            )

        # Show topic info card
        st.markdown(
            f"<div style='background:#0e1117;border:1px solid #2a2a3e;border-radius:10px;"
            f"padding:14px 18px;margin:12px 0'>"
            f"<div style='font-weight:700;font-size:1rem;margin-bottom:4px'>{chosen_topic['label']}</div>"
            f"<div style='font-size:0.82em;color:#aaa;margin-bottom:8px'>"
            f"Domain: {chosen_topic['domain']}</div>"
            f"<div style='font-size:0.82em;color:#ccc'>{chosen_topic['subtopics']}</div>"
            f"<div style='margin-top:10px;font-size:0.8em'>"
            f"📖 Review: <a href='{chosen_topic['ka_url']}' target='_blank' "
            f"style='color:#0ea5e9'>{chosen_topic['ka_label']}</a></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if st.button(
            f"🚀 Generate {num_q}-Question Test: {chosen_label}",
            type="primary",
            use_container_width=True,
        ):
            if not _tt_api_key():
                st.error("ANTHROPIC_API_KEY not set.")
            else:
                _tt.tt_subject  = subj_choice
                _tt.tt_topic    = chosen_topic
                _tt.tt_num_q    = num_q
                _tt.tt_questions = []
                _tt.tt_answers  = {}
                _tt.tt_phase    = "generating"
                st.rerun()

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
                on_status=_tt_status,
            )
            progress_bar.progress(1.0)
            if not questions:
                st.error("No questions were generated. Please try again.")
                if st.button("← Back"):
                    _tt.tt_phase = "lobby"
                    st.rerun()
            else:
                _tt.tt_questions = questions
                _tt.tt_answers   = {}
                _tt.tt_phase     = "taking"
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

        st.markdown(
            f"<div style='background:#1e3a5f;color:#fff;border-radius:10px;"
            f"padding:16px 20px;margin-bottom:16px'>"
            f"<div style='font-size:0.75rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.08em'>Topic Test</div>"
            f"<div style='font-size:1.25rem;font-weight:700;margin-top:2px'>{topic['label']}</div>"
            f"<div style='font-size:0.85rem;opacity:0.8;margin-top:4px'>"
            f"{len(questions)} questions · no timer · calculator allowed</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

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
                    f"<div style='background:#f0f4f9;border-left:4px solid #1e3a5f;"
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

        st.markdown(
            f"<div style='background:linear-gradient(135deg,#1e3a5f,#2563eb);"
            f"color:#fff;border-radius:14px;padding:24px 28px;text-align:center;margin-bottom:20px'>"
            f"<div style='font-size:0.8rem;opacity:0.75;text-transform:uppercase;"
            f"letter-spacing:0.1em;margin-bottom:6px'>Topic Test Results</div>"
            f"<div style='font-size:1.2rem;font-weight:700;margin-bottom:8px'>{topic['label']}</div>"
            f"<div style='font-size:3.5rem;font-weight:800;color:{score_color};line-height:1'>"
            f"{correct_count}/{len(questions)}</div>"
            f"<div style='font-size:1rem;opacity:0.85;margin-top:4px'>{pct}% correct</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # KA review link banner
        st.markdown(
            f"<div style='background:#0e1117;border:1px solid #0ea5e9;border-radius:8px;"
            f"padding:12px 16px;margin-bottom:16px;font-size:0.88rem'>"
            f"📖 <strong>Review this topic:</strong> "
            f"<a href='{topic['ka_url']}' target='_blank' style='color:#0ea5e9'>"
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
                        f"<div style='background:#f0f4f9;border-left:3px solid #1e3a5f;"
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

                # Per-question KA link
                st.markdown(
                    f"<div style='margin-top:8px;padding:8px 12px;background:#0e1117;"
                    f"border-radius:6px;font-size:0.82em'>"
                    f"📖 <strong>Review concept:</strong> "
                    f"<a href='{topic['ka_url']}' target='_blank' style='color:#0ea5e9'>"
                    f"{topic['ka_label']}</a></div>",
                    unsafe_allow_html=True,
                )

        st.divider()
        col_retry, col_new = st.columns(2)
        with col_retry:
            if st.button("🔄 Retry Same Topic", use_container_width=True):
                _tt.tt_questions = []
                _tt.tt_answers   = {}
                _tt.tt_phase     = "generating"
                st.rerun()
        with col_new:
            if st.button("← Choose New Topic", use_container_width=True):
                _tt.tt_phase = "lobby"
                st.rerun()
