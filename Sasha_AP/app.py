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

import math
import anthropic
import streamlit as st
from datetime import date

from agent import (
    AGENTS, TOOLS, execute_tool,
    LEVEL_NAMES, LEVEL_ICONS, DIFFICULTY_NAMES, MODEL,
    load_performance, load_weak_topics, days_remaining,
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
    page_title="AP Tutor — Sasha",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Base ── */
    .block-container { padding-top: 0.75rem !important; }
    header[data-testid="stHeader"] { height: 0 !important; min-height: 0 !important; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 0.75rem !important; }

    /* Touch-friendly buttons on all devices */
    .stButton > button {
        min-height: 44px;
        touch-action: manipulation;  /* no double-tap zoom */
    }

    /* Tabs: horizontal scroll so they never wrap/overflow on small screens */
    [data-testid="stTabs"] [role="tablist"] {
        overflow-x: auto;
        white-space: nowrap;
        -webkit-overflow-scrolling: touch;
    }

    /* ── Tablet (≤ 900px) ── */
    @media screen and (max-width: 900px) {
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
        /* Allow Streamlit columns to wrap */
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 6px !important;
        }
        /* 2 per row on tablet — quick actions become 2×2, formula cols stay 2 */
        [data-testid="column"] {
            min-width: calc(50% - 6px) !important;
            flex: 1 1 calc(50% - 6px) !important;
        }
    }

    /* ── Mobile (≤ 600px) ── */
    @media screen and (max-width: 600px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            max-width: 100vw !important;
        }
        /* 3 per row: works for 3-col and 5-col (calculator) grids;
           quick actions become 2×2 via min-content / growth */
        [data-testid="column"] {
            min-width: calc(33% - 6px) !important;
            flex: 1 1 calc(33% - 6px) !important;
        }
        /* Bigger tap targets on phone */
        .stButton > button {
            min-height: 52px !important;
            font-size: 1rem !important;
        }
        /* Prevent iOS auto-zoom when focusing inputs (triggers at < 16px) */
        input, textarea,
        [data-testid="stChatInput"] textarea,
        [data-testid="stTextInput"] input {
            font-size: 16px !important;
        }
        /* Scale headings down */
        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.1rem !important; }
        [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
        /* Sidebar narrower on phone */
        section[data-testid="stSidebar"] { min-width: 240px !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session State Init ─────────────────────────────────────────────────────────

if "active_agent" not in st.session_state:
    st.session_state.active_agent = "physics"

if "injected_message" not in st.session_state:
    st.session_state.injected_message = None

# Per-agent chat + API history
for _ak in AGENTS:
    if f"api_messages_{_ak}" not in st.session_state:
        st.session_state[f"api_messages_{_ak}"] = []
    if f"chat_history_{_ak}" not in st.session_state:
        st.session_state[f"chat_history_{_ak}"] = []

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📚 Sasha's Tutor")

    # ── Subject switcher ───────────────────────────────────────────────────────
    st.subheader("Subject")
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        if st.button("⚛️ Physics 1", use_container_width=True,
                     type="primary" if st.session_state.active_agent == "physics" else "secondary"):
            st.session_state.active_agent = "physics"
            st.rerun()
    with s_col2:
        if st.button("∫ Calculus AB", use_container_width=True,
                     type="primary" if st.session_state.active_agent == "calculus" else "secondary"):
            st.session_state.active_agent = "calculus"
            st.rerun()

    st.divider()

    # Active config drives the rest of the sidebar
    cfg       = AGENTS[st.session_state.active_agent]
    days_left = days_remaining(cfg)
    exam_str  = cfg.exam_date.strftime("%B %d, %Y")

    # Exam countdown
    if days_left > 0:
        st.metric("Days Until Exam", days_left, delta=exam_str)
    elif days_left == 0:
        st.metric("Exam Day!", "TODAY 🌟")
    else:
        st.metric("Exam", "Completed")

    st.divider()

    # Unit progress dashboard
    st.subheader("Unit Progress")
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
        short   = unit.replace("& ", "").replace("'s", "s")
        st.markdown(
            f"<div style='margin-bottom:4px'>"
            f"<span style='font-size:0.78em;color:#ccc'>{short} <span style='color:#888'>({weight}%)</span></span><br>"
            f"<span style='font-family:monospace;color:{color}'>{bar}</span> "
            f"<span style='font-size:0.75em;color:#aaa'>{caption}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Daily practice progress
    st.divider()
    st.subheader("Today's Practice")
    q_done = get_today_questions(cfg)
    st.progress(min(q_done / MIN_QUESTIONS, 1.0))
    if q_done >= MIN_QUESTIONS:
        st.success(f"✅ {q_done}/{MIN_QUESTIONS} questions — great work today!")
    else:
        st.warning(f"⚠️ {q_done}/{MIN_QUESTIONS} questions answered today")

    # Weak topics expander
    topics = load_weak_topics(cfg)
    if topics:
        st.divider()
        with st.expander(f"⚠️ Weak Topics ({len(topics)})"):
            for t in topics:
                st.markdown(f"• **{t['topic']}** — {t['note']}")

# ── Formula Sheet Data ─────────────────────────────────────────────────────────

PHYSICS_FORMULA_SHEET = {
    "Unit 1: Kinematics": {
        "icon": "📐",
        "color": "#4e9af1",
        "formulas": [
            ("Velocity", "v = v₀ + at"),
            ("Displacement", "x = v₀t + ½at²"),
            ("Velocity²", "v² = v₀² + 2ax"),
            ("Avg velocity", "x = ½(v + v₀)t"),
            ("Projectile x", "x = v₀ₓ · t"),
            ("Projectile y", "y = v₀ᵧt − ½gt²"),
            ("Free fall (g)", "g = 9.8 m/s²  ↓"),
        ],
        "tips": "Sign convention matters! Pick a positive direction and stick with it.",
    },
    "Unit 2: Force and Translational Dynamics": {
        "icon": "⚙️",
        "color": "#e05c5c",
        "formulas": [
            ("Newton's 2nd", "F_net = ma"),
            ("Weight", "W = mg"),
            ("Kinetic friction", "f_k = μ_k N"),
            ("Static friction", "f_s ≤ μ_s N"),
            ("Centripetal acc.", "a_c = v²/r"),
            ("Centripetal force", "F_c = mv²/r"),
            ("Universal gravity", "F_g = Gm₁m₂/r²"),
        ],
        "tips": "Draw a free-body diagram first. Every force needs a source object.",
    },
    "Unit 3: Work, Energy, and Power": {
        "icon": "⚡",
        "color": "#f0a500",
        "formulas": [
            ("Work", "W = Fd·cosθ"),
            ("Kinetic energy", "KE = ½mv²"),
            ("Gravitational PE", "PE_g = mgh"),
            ("Spring PE", "PE_s = ½kx²"),
            ("Work-energy thm.", "W_net = ΔKE"),
            ("Conservation", "KE₁ + PE₁ = KE₂ + PE₂"),
            ("Power", "P = W/t = Fv"),
        ],
        "tips": "Energy is conserved only when no non-conservative forces (friction) do work.",
    },
    "Unit 4: Linear Momentum": {
        "icon": "🏃",
        "color": "#2ecc71",
        "formulas": [
            ("Momentum", "p = mv"),
            ("Impulse", "J = FΔt = Δp"),
            ("Conservation", "p₁ᵢ + p₂ᵢ = p₁f + p₂f"),
            ("Perfectly inelastic", "(m₁+m₂)v' = m₁v₁ + m₂v₂"),
            ("Elastic (KE conserved)", "KE_total is conserved"),
            ("Center of mass", "x_cm = (m₁x₁ + m₂x₂)/(m₁+m₂)"),
        ],
        "tips": "Momentum is always conserved in collisions. KE is only conserved in elastic collisions.",
    },
    "Unit 5: Torque and Rotational Dynamics": {
        "icon": "🔄",
        "color": "#9b59b6",
        "formulas": [
            ("Torque", "τ = rF·sinθ"),
            ("Newton's 2nd (rot.)", "τ_net = Iα"),
            ("Point mass inertia", "I = mr²"),
            ("Rod (center pivot)", "I = 1/12 mL²"),
            ("Rod (end pivot)", "I = 1/3 mL²"),
            ("Solid disk/cylinder", "I = ½mr²"),
            ("Arc-linear link", "a = αr,  v = ωr"),
        ],
        "tips": "Torque direction: counterclockwise = positive. The pivot point choice is yours!",
    },
    "Unit 6: Energy and Momentum of Rotating Systems": {
        "icon": "🌀",
        "color": "#1abc9c",
        "formulas": [
            ("Rotational KE", "KE_rot = ½Iω²"),
            ("Rolling total KE", "KE = ½mv² + ½Iω²"),
            ("Angular momentum", "L = Iω"),
            ("Angular impulse", "τ·Δt = ΔL"),
            ("Conservation of L", "L_i = L_f  (when τ_net = 0)"),
            ("Angular velocity", "ω = 2πf = 2π/T"),
        ],
        "tips": "When a spinning skater pulls in arms, I decreases → ω increases (L conserved).",
    },
    "Unit 7: Oscillations": {
        "icon": "〰️",
        "color": "#e67e22",
        "formulas": [
            ("Hooke's Law", "F = −kx"),
            ("Spring PE", "PE = ½kx²"),
            ("Spring period", "T = 2π√(m/k)"),
            ("Pendulum period", "T = 2π√(L/g)"),
            ("Frequency", "f = 1/T"),
            ("Angular freq.", "ω = 2πf = √(k/m)"),
            ("Position", "x(t) = A·cos(ωt)"),
            ("Max speed", "v_max = Aω  (at x = 0)"),
        ],
        "tips": "At equilibrium: max speed, zero PE. At amplitude: zero speed, max PE.",
    },
    "Unit 8: Fluids": {
        "icon": "💧",
        "color": "#00b4d8",
        "formulas": [
            ("Density", "ρ = m/V"),
            ("Pressure", "P = F/A"),
            ("Fluid pressure", "P = P₀ + ρgh"),
            ("Buoyant force", "F_b = ρ_fluid · V_disp · g"),
            ("Continuity", "A₁v₁ = A₂v₂"),
            ("Bernoulli's eq.", "P + ½ρv² + ρgh = const"),
        ],
        "tips": "Object floats when F_b ≥ weight. Faster flow → lower pressure (Bernoulli).",
    },
}

CALCULUS_FORMULA_SHEET = {
    "Unit 1: Limits and Continuity": {
        "icon": "🎯",
        "color": "#4e9af1",
        "formulas": [
            ("Limit definition", "lim_{x→a} f(x) = L"),
            ("Continuity", "lim_{x→a} f(x) = f(a)"),
            ("L'Hôpital's Rule", "0/0 or ∞/∞ → lim f/g = lim f'/g'"),
            ("Squeeze Theorem", "g(x) ≤ f(x) ≤ h(x), g→L, h→L ⟹ f→L"),
            ("sin limit", "lim_{x→0} sin(x)/x = 1"),
            ("IVT", "f cont. on [a,b] → takes every value between f(a), f(b)"),
        ],
        "tips": "Check left and right limits separately — if they differ, the limit doesn't exist.",
    },
    "Unit 2: Differentiation — Basic Rules": {
        "icon": "📏",
        "color": "#e05c5c",
        "formulas": [
            ("Definition", "f'(x) = lim_{h→0} [f(x+h)−f(x)] / h"),
            ("Power Rule", "d/dx[xⁿ] = nxⁿ⁻¹"),
            ("Constant", "d/dx[c] = 0"),
            ("sin / cos", "(sin x)' = cos x,  (cos x)' = −sin x"),
            ("tan / sec", "(tan x)' = sec²x,  (sec x)' = sec x tan x"),
            ("eˣ / ln x", "(eˣ)' = eˣ,  (ln x)' = 1/x"),
            ("aˣ", "(aˣ)' = aˣ ln a"),
        ],
        "tips": "Memorise the trig derivatives cold — they show up everywhere on the exam.",
    },
    "Unit 3: Differentiation — Chain, Product, Quotient": {
        "icon": "🔗",
        "color": "#f0a500",
        "formulas": [
            ("Product Rule", "(fg)' = f'g + fg'"),
            ("Quotient Rule", "(f/g)' = (f'g − fg') / g²"),
            ("Chain Rule", "(f∘g)' = f'(g(x)) · g'(x)"),
            ("Implicit diff.", "differentiate both sides w.r.t. x, solve for dy/dx"),
            ("arcsin", "(arcsin x)' = 1/√(1−x²)"),
            ("arctan", "(arctan x)' = 1/(1+x²)"),
            ("Inverse fn.", "d/dx[f⁻¹(x)] = 1 / f'(f⁻¹(x))"),
        ],
        "tips": "Chain rule: work from outside in. Always multiply by the derivative of the inside.",
    },
    "Unit 4: Contextual Applications": {
        "icon": "🚗",
        "color": "#2ecc71",
        "formulas": [
            ("Related rates", "differentiate equation w.r.t. t; substitute known values"),
            ("Linear approx.", "L(x) = f(a) + f'(a)(x − a)"),
            ("Position → vel.", "v(t) = s'(t)"),
            ("Vel. → accel.", "a(t) = v'(t) = s''(t)"),
            ("Avg rate of change", "[f(b) − f(a)] / (b − a)"),
            ("Inst. rate of change", "f'(x)  (the derivative)"),
        ],
        "tips": "Related rates: draw a diagram, label variables, write an equation, then differentiate.",
    },
    "Unit 5: Analytical Applications": {
        "icon": "📊",
        "color": "#9b59b6",
        "formulas": [
            ("Mean Value Thm.", "f'(c) = [f(b)−f(a)] / (b−a)  for some c ∈ (a,b)"),
            ("Rolle's Theorem", "f(a)=f(b) ⟹ f'(c)=0 for some c"),
            ("Critical points", "f'(x) = 0  or  f'(x) undefined"),
            ("1st deriv. test", "f' changes + → − : local max;  − → + : local min"),
            ("2nd deriv. test", "f''(c) > 0 : local min;  f''(c) < 0 : local max"),
            ("Concavity", "f'' > 0 : concave up;  f'' < 0 : concave down"),
            ("Inflection point", "f'' changes sign"),
        ],
        "tips": "EVT: continuous on [a,b] → absolute max/min exist. Always check endpoints!",
    },
    "Unit 6: Integration": {
        "icon": "∫",
        "color": "#1abc9c",
        "formulas": [
            ("FTC Part 1", "d/dx[∫ₐˣ f(t)dt] = f(x)"),
            ("FTC Part 2", "∫ₐᵇ f(x)dx = F(b) − F(a)"),
            ("Power Rule", "∫xⁿ dx = xⁿ⁺¹/(n+1) + C  (n ≠ −1)"),
            ("∫eˣ / ∫(1/x)", "∫eˣ dx = eˣ + C;  ∫(1/x) dx = ln|x| + C"),
            ("∫trig", "∫sin x dx = −cos x + C;  ∫cos x dx = sin x + C"),
            ("u-substitution", "∫f(g(x))g'(x)dx = ∫f(u)du"),
            ("Int. by parts", "∫u dv = uv − ∫v du"),
        ],
        "tips": "u-sub: pick u = inside function, check that du appears (or can be arranged) in the integral.",
    },
    "Unit 7: Differential Equations": {
        "icon": "🌱",
        "color": "#e67e22",
        "formulas": [
            ("Separable DE", "dy/dx = g(x)h(y)  →  ∫dy/h(y) = ∫g(x)dx"),
            ("Exponential growth", "dy/dt = ky  →  y = Ce^(kt)"),
            ("Doubling time", "t = ln2 / k"),
            ("Half-life", "t = ln2 / |k|"),
            ("Slope field", "plot dy/dx value as a short segment at each (x,y)"),
            ("Euler's method", "y_{n+1} = y_n + f(x_n, y_n)·Δx"),
        ],
        "tips": "Separable: get all y's on one side and all x's on the other before integrating.",
    },
    "Unit 8: Applications of Integration": {
        "icon": "📐",
        "color": "#00b4d8",
        "formulas": [
            ("Area between curves", "∫ₐᵇ [f(x) − g(x)] dx  (f on top)"),
            ("Average value", "(1/(b−a)) · ∫ₐᵇ f(x) dx"),
            ("Net change", "∫ₐᵇ f'(x) dx = f(b) − f(a)"),
            ("Displacement", "∫ₐᵇ v(t) dt"),
            ("Total distance", "∫ₐᵇ |v(t)| dt"),
            ("Accum. from rate", "Amount = initial + ∫ rate dt"),
        ],
        "tips": "Distance ≠ displacement! Split the integral where v(t) = 0 to handle absolute value.",
    },
}

FORMULA_SHEETS = {
    "physics":  PHYSICS_FORMULA_SHEET,
    "calculus": CALCULUS_FORMULA_SHEET,
}

# ── Main Area ──────────────────────────────────────────────────────────────────

st.title(f"{cfg.icon} {cfg.display_name} Tutor")
st.caption(f"Hi Sasha! You have **{days_left} days** until your {cfg.display_name} exam on {exam_str}. Let's get to work! 💪")

# Quick actions — always visible above the tabs
qa1, qa2, qa3, qa4 = st.columns(4)
with qa1:
    if st.button("📅 Schedule", use_container_width=True):
        st.session_state.injected_message = "What's my recommended study schedule?"
        st.rerun()
with qa2:
    if st.button("⚠️ Weak Topics", use_container_width=True):
        st.session_state.injected_message = "Show me my weak topics."
        st.rerun()
with qa3:
    if st.button("📊 Report", use_container_width=True):
        st.session_state.injected_message = "Give me my full progress report."
        st.rerun()
with qa4:
    if st.button("🧪 Diagnose", use_container_width=True):
        st.session_state.injected_message = "Run a full diagnostic and tell me what to study first."
        st.rerun()

tab_chat, tab_formulas, tab_calc = st.tabs(["💬 Chat", "📐 Formula Sheet", "🔢 Calculator"])

# ── Formula Sheet Tab ──────────────────────────────────────────────────────────

with tab_formulas:
    active_sheet = FORMULA_SHEETS[st.session_state.active_agent]
    st.subheader(f"{cfg.display_name} — Formula Reference")
    st.caption("All the formulas you need, organized by unit. Keep this tab open while you practice!")

    # Build all unit cards as a single CSS-grid block — fully responsive:
    # desktop → 2 cols, tablet → 1-2 cols, mobile → 1 col (auto-fit)
    cards_html = ""
    for unit_name, unit_data in active_sheet.items():
        color = unit_data["color"]
        icon  = unit_data["icon"]
        tip   = unit_data["tips"]
        rows  = "".join(
            f"<tr>"
            f"<td style='color:#aaa;font-size:0.8em;padding:3px 10px 3px 0;"
            f"white-space:nowrap;vertical-align:top'>{lbl}</td>"
            f"<td style='font-family:monospace;font-size:0.88em;padding:3px 0;"
            f"word-break:break-word'>{fml}</td>"
            f"</tr>"
            for lbl, fml in unit_data["formulas"]
        )
        cards_html += (
            f"<div style='background:#0e1117;border:1px solid #1e1e2e;"
            f"border-radius:10px;padding:14px 16px;'>"
            f"<div style='border-left:4px solid {color};padding:4px 10px;margin-bottom:8px'>"
            f"<span style='font-size:1em;font-weight:700;color:{color}'>{icon} {unit_name}</span>"
            f"</div>"
            f"<table style='width:100%;border-collapse:collapse'>{rows}</table>"
            f"<div style='font-size:0.78em;color:#888;background:#12121f;"
            f"border-radius:5px;padding:6px 9px;margin-top:8px'>💡 {tip}</div>"
            f"</div>"
        )

    st.markdown(
        f"<div style='display:grid;"
        f"grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));"
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

    # ── Safe eval context ──────────────────────────────────────────────────────
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

    # ── Layout — centred container that shrinks gracefully on mobile ───────────
    # Use CSS max-width so on desktop it stays narrow; on mobile it fills the screen
    st.markdown(
        "<div style='max-width:480px;margin:0 auto'>",
        unsafe_allow_html=True,
    )
    st.subheader("Scientific Calculator")

    # Degree / Radian toggle
    deg_col, _ = st.columns([1, 3])
    with deg_col:
        st.session_state.calc_deg = st.toggle(
            "Degrees", value=st.session_state.calc_deg,
            help="Toggle between degrees and radians for trig functions"
        )

    # Display
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

    # Button grid: [label shown, value appended]
    ROWS = [
        [("sin(","sin("), ("cos(","cos("), ("tan(","tan("), ("log(","log("), ("ln(","ln(")],
        [("√(","√("),    ("xʸ","^"),       ("(",  "("),     (")",  ")"),     ("π", "π")],
        [("C", "C"),     ("⌫","⌫"),         ("e",  "e"),    ("%",  "%"),     ("1/(","1/(")],
        [("7","7"),      ("8","8"),          ("9","9"),       ("÷","/")],
        [("4","4"),      ("5","5"),          ("6","6"),       ("×","*")],
        [("1","1"),      ("2","2"),          ("3","3"),       ("−","-")],
        [("0","0"),      (".","."  ),        ("=","="),       ("+","+")],
    ]

    HIGHLIGHT = {"=": "#4e9af1", "C": "#e05c5c"}

    for r_idx, row in enumerate(ROWS):
        cols = st.columns(len(row))
        for c_idx, (label, val) in enumerate(row):
            bg = HIGHLIGHT.get(val, "#262730")
            with cols[c_idx]:
                st.markdown(
                    f"<style>#calc_btn_{r_idx}_{c_idx} button{{"
                    f"background-color:{bg}!important;"
                    f"font-size:1.05em!important;font-weight:600!important}}</style>",
                    unsafe_allow_html=True,
                )
                if st.button(label, key=f"calc_btn_{r_idx}_{c_idx}", use_container_width=True):
                    _calc_press(val)
                    st.rerun()

    st.caption("Tip: ^ for power · log = log₁₀ · ln = natural log · trig in degrees by default")

    st.markdown("</div>", unsafe_allow_html=True)

# ── Chat Tab ───────────────────────────────────────────────────────────────────

with tab_chat:
    agent_key   = st.session_state.active_agent
    chat_key    = f"chat_history_{agent_key}"
    api_key_ss  = f"api_messages_{agent_key}"

    # Welcome message on first load (per subject)
    if not st.session_state[chat_key]:
        if agent_key == "physics":
            starter = "*'Test me on Energy'* or *'Give me a hard FRQ on Momentum'* or *'What should I study today?'*"
        else:
            starter = "*'Quiz me on derivatives'* or *'Explain the chain rule'* or *'Give me an FRQ on integrals'*"
        welcome = (
            f"Hi Sasha! 👋 I'm your {cfg.display_name} tutor. You have **{days_left} days** until your exam on **{exam_str}**.\n\n"
            "Here's what we can do together:\n"
            "- **Diagnose** your understanding of any unit\n"
            "- **Quiz** you with MCQ and FRQ questions at your exact level\n"
            "- **Track** your progress and adjust difficulty automatically\n"
            "- **Plan** your study schedule based on what needs the most work\n\n"
            f"Try saying: {starter}\n\n"
            "_Tip: click the **📐 Formula Sheet** tab anytime to look up a formula while you practice!_"
        )
        st.session_state[chat_key].append(("assistant", welcome))

    # Render chat history for this subject
    for role, text in st.session_state[chat_key]:
        with st.chat_message(role, avatar="🎓" if role == "assistant" else "👩‍🎓"):
            st.markdown(text)

    # ── Message Handling ───────────────────────────────────────────────────────

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
        client = anthropic.Anthropic(api_key=api_key)

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
                        "text": c.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    tools=TOOLS,
                    messages=st.session_state[apk],
                ) as stream:
                    for event in stream:
                        if event.type == "content_block_delta":
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

    # Handle injected message (from quick-action buttons)
    if st.session_state.injected_message:
        msg = st.session_state.injected_message
        st.session_state.injected_message = None
        run_agent(msg)

    # Handle typed input
    placeholder_text = (
        "Ask me anything, or say 'test me on Energy'…"
        if agent_key == "physics"
        else "Ask me anything, or say 'quiz me on derivatives'…"
    )
    if prompt := st.chat_input(placeholder_text):
        run_agent(prompt)
