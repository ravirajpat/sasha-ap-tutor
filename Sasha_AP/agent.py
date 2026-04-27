#!/usr/bin/env python3
"""
AP Exam Prep — Multi-Agent: Physics 1 & Calculus AB
"""

import anthropic
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime

# ── Global constants ──────────────────────────────────────────────────────────

MODEL         = "claude-opus-4-7"
MIN_QUESTIONS = int(os.environ.get("MIN_QUESTIONS", "5"))

LEVEL_NAMES = {0: "Untested", 1: "Beginner", 2: "Developing", 3: "Proficient", 4: "Advanced", 5: "Expert"}
LEVEL_ICONS = {0: "○○○○○", 1: "●○○○○", 2: "●●○○○", 3: "●●●○○", 4: "●●●●○", 5: "●●●●●"}
DIFFICULTY_NAMES = {1: "Easy", 2: "Medium", 3: "Hard"}

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"

# ── AgentConfig ───────────────────────────────────────────────────────────────

@dataclass
class AgentConfig:
    key: str                  # "physics" | "calculus"
    display_name: str         # shown in UI
    icon: str                 # emoji
    exam_date: date
    units: list
    unit_weights: dict        # unit_name → int (%)
    system_prompt: str
    performance_file: str
    weak_topics_file: str
    daily_progress_file: str

# ── Shared Tools schema (same for both agents) ────────────────────────────────

TOOLS = [
    {
        "name": "save_weak_topic",
        "description": "Save a topic Sasha is struggling with for later review. Call this proactively whenever she makes an error or seems confused.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The specific topic or concept she's struggling with"},
                "note":  {"type": "string", "description": "Brief note about what was confusing or the mistake she made"},
            },
            "required": ["topic", "note"],
        },
    },
    {
        "name": "get_weak_topics",
        "description": "Retrieve the list of topics Sasha has struggled with in past sessions.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_study_schedule",
        "description": "Get a recommended day-by-day study schedule based on days remaining and weak topics.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "record_practice_answer",
        "description": "Record that Sasha answered a practice question. Call after every MCQ or FRQ answer she submits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "correct": {"type": "boolean", "description": "Whether her answer was correct"},
            },
            "required": ["correct"],
        },
    },
]

# ── System Prompts ─────────────────────────────────────────────────────────────

_PHYSICS_PROMPT = """You are Sasha's personal AP Physics 1 tutor. Sasha is a 15-year-old student with her AP Physics 1 exam on May 6, 2026.

## Your Role
You are a warm, encouraging, and brilliant physics tutor. You explain concepts clearly using real-world analogies. You celebrate wins and help Sasha build confidence. You adapt your teaching to what she's struggling with.

## AP Physics 1 Exam Overview
- **Format**: 40 Multiple Choice (50 min, 50%) + 5 Free Response (100 min, 50%)
- **FRQ types**: Experimental Design, Qualitative/Quantitative Translation, Short Answer (×2), Paragraph Argument
- **Score**: 1-5 scale; colleges typically accept 4 or 5

## AP Physics 1 Content Areas & Approximate Weight

| Unit | Topic | ~Weight |
|------|-------|---------|
| 1 | Kinematics (1D & 2D, projectile motion) | 10% |
| 2 | Forces & Newton's Laws (F=ma, friction, normal force) | 18% |
| 3 | Work, Energy, and Power | 18% |
| 4 | Linear Momentum & Impulse (collisions, conservation) | 10% |
| 5 | Torque & Rotational Motion (moment of inertia, angular momentum) | 12% |
| 6 | Energy and Momentum of Rotating Systems | 5% |
| 7 | Oscillations (springs, pendulums) | 7% |
| 8 | Fluids (pressure, buoyancy, Bernoulli) | 10% |

## Key Formulas Sasha Should Know
- Kinematics: v = v₀ + at, x = v₀t + ½at², v² = v₀² + 2ax
- Forces: F = ma, W = mg, f = μN
- Centripetal: ac = v²/r, Fc = mv²/r
- Gravity: Fg = Gm₁m₂/r²
- Energy: KE = ½mv², PE = mgh, W = Fd·cosθ, P = W/t
- Momentum: p = mv, J = FΔt = Δp
- Springs: F = -kx, PE = ½kx², T = 2π√(m/k)
- Pendulum: T = 2π√(L/g)
- Torque: τ = rF·sinθ, τ_net = Iα, L = Iω
- Fluids: P = P₀ + ρgh, F_b = ρgV, A₁v₁ = A₂v₂

## How You Teach

### When generating practice questions:
Always format MCQs like this:
```
📝 PRACTICE QUESTION
[Question text with all necessary info]

A) [option]
B) [option]
C) [option]
D) [option]

[Wait for Sasha's answer before revealing solution]
```

### When she gets something wrong:
- Never make her feel bad
- Say "Close! Here's the trick..." or "Great attempt — let's look at this together"
- Use the `save_weak_topic` tool to log it for later review

### When she gets something right:
- Celebrate! "Yes! Exactly right 🎉"
- Ask a follow-up to deepen understanding

## Tools You Have
- `save_weak_topic`: Call whenever Sasha struggles. Be proactive — log it without asking.
- `get_weak_topics`: Call when Sasha asks for a review of weak areas.
- `get_study_schedule`: Call when Sasha asks what to study today or this week.
- `record_practice_answer`: Call EVERY TIME Sasha submits an answer. Never skip this.

Always be encouraging. You believe in Sasha completely."""


_CALCULUS_PROMPT = """You are Sasha's personal AP Calculus AB tutor. Sasha is a 15-year-old student with her AP Calculus AB exam on May 11, 2026 at 8:00 AM.

## Your Role
You are a warm, encouraging, and brilliant math tutor. You build intuition first — graphs and real-world meaning before formulas. You celebrate wins and help Sasha build confidence. You adapt to what she's struggling with.

## AP Calculus AB Exam Overview
- **Format**: 45 MCQ (1 hr 45 min, 50%) + 6 FRQ (1 hr 30 min, 50%)
- **MCQ**: Part A — 30 questions, no calculator | Part B — 15 questions, calculator allowed
- **FRQ**: Part A — 2 problems, calculator | Part B — 4 problems, no calculator
- **Score**: 1-5 scale; colleges typically accept 4 or 5

## AP Calculus AB Content Areas & Approximate Weight

| Unit | Topic | ~Weight |
|------|-------|---------|
| 1 | Limits and Continuity | 10% |
| 2 | Differentiation: Definition and Basic Rules | 11% |
| 3 | Differentiation: Composite, Implicit, and Inverse Functions | 11% |
| 4 | Contextual Applications of Differentiation | 12% |
| 5 | Analytical Applications of Differentiation | 17% |
| 6 | Integration and Accumulation of Change | 18% |
| 7 | Differential Equations | 9% |
| 8 | Applications of Integration | 12% |

## Key Formulas & Theorems Sasha Should Know

### Limits
- Definition of limit; one-sided limits
- L'Hôpital's Rule: 0/0 or ∞/∞ → lim f/g = lim f'/g'
- Squeeze Theorem; Continuity: lim_{x→a} f(x) = f(a)

### Derivatives
- Definition: f'(x) = lim_{h→0} [f(x+h) − f(x)] / h
- Power Rule: d/dx[xⁿ] = nxⁿ⁻¹
- Product Rule: (fg)' = f'g + fg'
- Quotient Rule: (f/g)' = (f'g − fg') / g²
- Chain Rule: (f∘g)' = f'(g(x)) · g'(x)
- Trig: (sin x)' = cos x, (cos x)' = −sin x, (tan x)' = sec²x
- Exponential/Log: (eˣ)' = eˣ, (ln x)' = 1/x, (aˣ)' = aˣ ln a
- Inverse trig: (arcsin x)' = 1/√(1−x²), (arctan x)' = 1/(1+x²)

### Integrals
- FTC Part 1: d/dx[∫ₐˣ f(t)dt] = f(x)
- FTC Part 2: ∫ₐᵇ f(x)dx = F(b) − F(a)
- Power Rule: ∫xⁿ dx = xⁿ⁺¹/(n+1) + C (n ≠ −1)
- ∫eˣ dx = eˣ + C, ∫(1/x) dx = ln|x| + C
- ∫sin x dx = −cos x + C, ∫cos x dx = sin x + C
- u-substitution: ∫f(g(x))g'(x)dx = ∫f(u)du
- Integration by parts: ∫u dv = uv − ∫v du

### Key Theorems
- Mean Value Theorem: f'(c) = [f(b)−f(a)] / (b−a) for some c ∈ (a,b)
- Intermediate Value Theorem: continuous on [a,b] → takes every value between f(a) and f(b)
- Extreme Value Theorem: continuous on [a,b] → has absolute max and min
- Rolle's Theorem: f(a)=f(b) → f'(c)=0 for some c

### Applications
- Related rates: differentiate an equation with respect to t
- Optimization: find critical points, use first or second derivative test
- Area between curves: ∫[f(x)−g(x)]dx
- Average value: (1/(b−a)) ∫ₐᵇ f(x)dx
- Differential equations: separable; exponential growth/decay y = Ce^(kt)
- Slope fields: match dy/dx expression to the field visually

## How You Teach

### When generating practice questions:
Always format MCQs like this:
```
📝 PRACTICE QUESTION
[Question text]

A) [option]
B) [option]
C) [option]
D) [option]

[Wait for Sasha's answer before revealing solution]
```

For FRQs, walk through each part after she attempts it.

### When she gets something wrong:
- Never make her feel bad
- Say "Close! Here's the key idea..." or "Great attempt — let me show you the trick"
- Reteach using a graph or simpler example first
- Use `save_weak_topic` to log it

### When she gets something right:
- Celebrate! "Yes! Exactly right 🎉"
- Ask a quick follow-up to solidify understanding

## Tools You Have
- `save_weak_topic`: Call whenever Sasha struggles. Be proactive.
- `get_weak_topics`: Call when she asks for a review of weak areas.
- `get_study_schedule`: Call when she asks what to study today.
- `record_practice_answer`: Call EVERY TIME she submits an answer.

Always be encouraging. Calculus is beautiful, and Sasha can absolutely do this!"""


# ── Agent Configs ─────────────────────────────────────────────────────────────

PHYSICS_CONFIG = AgentConfig(
    key="physics",
    display_name="AP Physics 1",
    icon="⚛️",
    exam_date=date(2026, 5, 6),
    units=[
        "Unit 1: Kinematics",
        "Unit 2: Force and Translational Dynamics",
        "Unit 3: Work, Energy, and Power",
        "Unit 4: Linear Momentum",
        "Unit 5: Torque and Rotational Dynamics",
        "Unit 6: Energy and Momentum of Rotating Systems",
        "Unit 7: Oscillations",
        "Unit 8: Fluids",
    ],
    unit_weights={
        "Unit 1: Kinematics": 10,
        "Unit 2: Force and Translational Dynamics": 18,
        "Unit 3: Work, Energy, and Power": 18,
        "Unit 4: Linear Momentum": 10,
        "Unit 5: Torque and Rotational Dynamics": 12,
        "Unit 6: Energy and Momentum of Rotating Systems": 5,
        "Unit 7: Oscillations": 7,
        "Unit 8: Fluids": 10,
    },
    system_prompt=_PHYSICS_PROMPT,
    performance_file="physics_performance.json",
    weak_topics_file="physics_weak_topics.json",
    daily_progress_file="physics_daily_progress.json",
)

CALCULUS_CONFIG = AgentConfig(
    key="calculus",
    display_name="AP Calculus AB",
    icon="∫",
    exam_date=date(2026, 5, 11),
    units=[
        "Unit 1: Limits and Continuity",
        "Unit 2: Differentiation: Definition and Basic Rules",
        "Unit 3: Differentiation: Composite, Implicit, and Inverse Functions",
        "Unit 4: Contextual Applications of Differentiation",
        "Unit 5: Analytical Applications of Differentiation",
        "Unit 6: Integration and Accumulation of Change",
        "Unit 7: Differential Equations",
        "Unit 8: Applications of Integration",
    ],
    unit_weights={
        "Unit 1: Limits and Continuity": 10,
        "Unit 2: Differentiation: Definition and Basic Rules": 11,
        "Unit 3: Differentiation: Composite, Implicit, and Inverse Functions": 11,
        "Unit 4: Contextual Applications of Differentiation": 12,
        "Unit 5: Analytical Applications of Differentiation": 17,
        "Unit 6: Integration and Accumulation of Change": 18,
        "Unit 7: Differential Equations": 9,
        "Unit 8: Applications of Integration": 12,
    },
    system_prompt=_CALCULUS_PROMPT,
    performance_file="calculus_performance.json",
    weak_topics_file="calculus_weak_topics.json",
    daily_progress_file="calculus_daily_progress.json",
)

AGENTS: dict[str, AgentConfig] = {
    "physics":  PHYSICS_CONFIG,
    "calculus": CALCULUS_CONFIG,
}

# ── Persistence helpers ───────────────────────────────────────────────────────

def load_performance(config: AgentConfig) -> dict:
    if not os.path.exists(config.performance_file):
        return {"units": {}}
    with open(config.performance_file) as f:
        return json.load(f)


def save_performance(config: AgentConfig, data: dict) -> None:
    with open(config.performance_file, "w") as f:
        json.dump(data, f, indent=2)


def load_weak_topics(config: AgentConfig) -> list:
    if not os.path.exists(config.weak_topics_file):
        return []
    with open(config.weak_topics_file) as f:
        return json.load(f)


def save_weak_topics(config: AgentConfig, topics: list) -> None:
    with open(config.weak_topics_file, "w") as f:
        json.dump(topics, f, indent=2)


def _local_get_today(config: AgentConfig) -> int:
    if not os.path.exists(config.daily_progress_file):
        return 0
    with open(config.daily_progress_file) as f:
        data = json.load(f)
    return data.get(date.today().isoformat(), 0)


def _local_increment_today(config: AgentConfig) -> int:
    today = date.today().isoformat()
    data = {}
    if os.path.exists(config.daily_progress_file):
        with open(config.daily_progress_file) as f:
            data = json.load(f)
    data[today] = data.get(today, 0) + 1
    with open(config.daily_progress_file, "w") as f:
        json.dump(data, f, indent=2)
    return data[today]

# ── Supabase ──────────────────────────────────────────────────────────────────

_supabase = None

def get_supabase():
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if url and key:
            try:
                from supabase import create_client
                _supabase = create_client(url, key)
            except Exception:
                pass
    return _supabase


def get_today_questions(config: AgentConfig) -> int:
    sb = get_supabase()
    if sb:
        try:
            result = (
                sb.table("daily_progress")
                .select("questions_answered")
                .eq("date", date.today().isoformat())
                .eq("subject", config.key)
                .execute()
            )
            return result.data[0]["questions_answered"] if result.data else 0
        except Exception:
            pass
    return _local_get_today(config)

# ── Tool implementations ──────────────────────────────────────────────────────

def tool_get_performance_report(config: AgentConfig) -> str:
    data = load_performance(config)
    if not data.get("units"):
        return "No performance data yet — start practicing to build your report!"
    lines = [f"Performance Report — {config.display_name}:"]
    for unit in config.units:
        u = data["units"].get(unit, {})
        level   = u.get("level", 0)
        total   = u.get("total", 0)
        correct = u.get("correct", 0)
        if total > 0:
            acc = int((correct / total) * 100)
            lines.append(f"• {unit}: Level {level} ({LEVEL_NAMES[level]}) — {acc}% ({correct}/{total})")
        else:
            lines.append(f"• {unit}: Not yet tested")
    return "\n".join(lines)


def tool_save_weak_topic(config: AgentConfig, topic: str, note: str) -> str:
    topics = load_weak_topics(config)
    if not any(t["topic"].lower() == topic.lower() for t in topics):
        topics.append({"topic": topic, "note": note, "logged_at": datetime.now().isoformat()})
        save_weak_topics(config, topics)
        return f"✓ Logged '{topic}' as a topic to review."
    return f"'{topic}' is already in the review list."


def tool_get_weak_topics(config: AgentConfig) -> str:
    topics = load_weak_topics(config)
    if not topics:
        return "No weak topics logged yet — great start!"
    lines = [f"• {t['topic']}: {t['note']}" for t in topics]
    return f"Topics to review ({config.display_name}):\n" + "\n".join(lines)


def tool_get_study_schedule(config: AgentConfig) -> str:
    today     = date.today()
    days_left = (config.exam_date - today).days
    weak      = [t["topic"] for t in load_weak_topics(config)]

    if days_left <= 0:
        return f"The {config.display_name} exam is today or has passed — good luck, Sasha! 🌟"

    lines = [f"📅 {config.display_name} Exam: {config.exam_date.strftime('%B %d, %Y')} ({days_left} days away)\n"]
    priority = sorted(config.unit_weights.items(), key=lambda x: x[1], reverse=True)

    if days_left >= len(priority):
        lines.append("Recommended focus areas:")
        for i, (unit, w) in enumerate(priority):
            flag = " ⚠️ (flagged weak)" if any(unit.lower() in wk.lower() for wk in weak) else ""
            lines.append(f"  Day {i+1}: {unit} ({w}%){flag}")
        lines.append(f"\n  Last day(s): Full practice exam + weak topic review")
    else:
        lines.append("Crunch-time plan:")
        for i in range(days_left - 1):
            unit, w = priority[i % len(priority)]
            flag = " ⚠️" if any(unit.lower() in wk.lower() for wk in weak) else ""
            lines.append(f"  Day {i+1}: {unit} ({w}%){flag}")
        lines.append(f"  Day {days_left} (exam day): Light review, rest well 🌟")

    if weak:
        lines.append(f"\n⚠️ Flagged for extra attention: {', '.join(weak)}")
    return "\n".join(lines)


def tool_record_practice_answer(config: AgentConfig, correct: bool) -> str:
    today = date.today().isoformat()
    sb    = get_supabase()
    if sb:
        try:
            result = (
                sb.table("daily_progress")
                .select("questions_answered")
                .eq("date", today)
                .eq("subject", config.key)
                .execute()
            )
            if result.data:
                count = result.data[0]["questions_answered"] + 1
                sb.table("daily_progress").update(
                    {"questions_answered": count, "last_updated": datetime.now().isoformat()}
                ).eq("date", today).eq("subject", config.key).execute()
            else:
                count = 1
                sb.table("daily_progress").insert(
                    {"date": today, "subject": config.key, "questions_answered": 1,
                     "last_updated": datetime.now().isoformat()}
                ).execute()
            status = "✓ Correct!" if correct else "Keep going!"
            return f"{status} ({count}/{MIN_QUESTIONS} questions done today)"
        except Exception:
            pass
    count  = _local_increment_today(config)
    status = "✓ Correct!" if correct else "Keep going!"
    return f"{status} ({count}/{MIN_QUESTIONS} questions done today)"


def execute_tool(name: str, tool_input: dict, config: AgentConfig) -> str:
    if name == "save_weak_topic":
        return tool_save_weak_topic(config, tool_input["topic"], tool_input["note"])
    elif name == "get_weak_topics":
        return tool_get_weak_topics(config)
    elif name == "get_study_schedule":
        return tool_get_study_schedule(config)
    elif name == "record_practice_answer":
        return tool_record_practice_answer(config, tool_input["correct"])
    return f"Unknown tool: {name}"

# ── Convenience helpers ────────────────────────────────────────────────────────

def days_remaining(config: AgentConfig) -> int:
    return (config.exam_date - date.today()).days

# ── CLI chat loop ─────────────────────────────────────────────────────────────

def chat(config: AgentConfig):
    client   = anthropic.Anthropic()
    messages: list[dict] = []
    days     = days_remaining(config)

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║  {config.icon}  {config.display_name} Tutor — Hi Sasha! 👋{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════╝{RESET}")
    print(f"\n{YELLOW}📅 Exam: {config.exam_date.strftime('%B %d, %Y')} ({days} days away!){RESET}")
    print(f"{DIM}Type 'quit' to exit • 'topics' to see weak areas{RESET}\n")

    while True:
        try:
            user_input = input(f"{BOLD}{CYAN}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GREEN}Good luck on the exam, Sasha! You've got this! 🌟{RESET}\n")
            sys.exit(0)

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print(f"\n{GREEN}Great work! Keep it up 🌟{RESET}\n")
            break
        if user_input.lower() == "topics":
            print(f"\n{YELLOW}{tool_get_weak_topics(config)}{RESET}\n")
            continue

        messages.append({"role": "user", "content": user_input})

        while True:
            print(f"\n{BOLD}{GREEN}Tutor:{RESET} ", end="", flush=True)
            assistant_content = []
            tool_calls = []

            with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=[{"type": "text", "text": config.system_prompt, "cache_control": {"type": "ephemeral"}}],
                tools=TOOLS,
                messages=messages,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_start" and event.content_block.type == "tool_use":
                        tool_calls.append({"id": event.content_block.id, "name": event.content_block.name, "input_str": ""})
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            print(event.delta.text, end="", flush=True)
                        elif event.delta.type == "input_json_delta" and tool_calls:
                            tool_calls[-1]["input_str"] += event.delta.partial_json
                final_msg = stream.get_final_message()
            print()

            for block in final_msg.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
                elif block.type == "thinking":
                    assistant_content.append({"type": "thinking", "thinking": block.thinking, "signature": block.signature})

            messages.append({"role": "assistant", "content": assistant_content})

            if final_msg.stop_reason != "tool_use":
                break

            tool_results = []
            for block in final_msg.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input, config)
                    print(f"  {DIM}[{block.name}: {result}]{RESET}")
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})

        print()


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{RED}Error: ANTHROPIC_API_KEY not set.{RESET}")
        sys.exit(1)

    # Pick subject from CLI arg: python agent.py calculus
    subject = sys.argv[1] if len(sys.argv) > 1 else "physics"
    if subject not in AGENTS:
        print(f"{RED}Unknown subject '{subject}'. Choose: {list(AGENTS)}{RESET}")
        sys.exit(1)

    chat(AGENTS[subject])
