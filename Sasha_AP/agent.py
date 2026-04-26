#!/usr/bin/env python3
"""
AP Physics 1 Exam Prep Agent for Sasha
Exam date: May 6, 2026
"""

import anthropic
import json
import os
import sys
from datetime import date, datetime

# ── Configuration ────────────────────────────────────────────────────────────

EXAM_DATE = date(2026, 5, 6)
WEAK_TOPICS_FILE = "weak_topics.json"
PERFORMANCE_FILE = "performance.json"
MODEL = "claude-opus-4-7"

UNITS = [
    "Unit 1: Kinematics"
    "Unit 2: Force and Translational Dynamics."
    "Unit 3: Work, Energy, and Power"
    "Unit 4: Linear Momentum
    "Unit 5: Torque and Rotational Dynamics"
    "Unit 6: Energy and Momentum of Rotating Systems"
    "Unit 7: Oscillations"
    "Unit 8: Fluids"
    ]

UNIT_WEIGHTS = {
    "Kinematics": 10,
    "Forces & Translational Dynamics": 18,
    "Work, Energy, and Power": 18,
    "Linear Momentum": 10,
    "Torque and Rotational Dynamics": 10,
    "Energy and Momentum of Rotating Systems": 5,
    "Oscillations": 5,
    "Fluids": 10
    ,
}

LEVEL_NAMES = {
    0: "Untested",
    1: "Beginner",
    2: "Developing",
    3: "Proficient",
    4: "Advanced",
    5: "Expert",
}

LEVEL_ICONS = {
    0: "○○○○○",
    1: "●○○○○",
    2: "●●○○○",
    3: "●●●○○",
    4: "●●●●○",
    5: "●●●●●",
}

DIFFICULTY_NAMES = {
    1: "Easy",
    2: "Medium",
    3: "Hard",
}

# ── ANSI colors ───────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"

# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Sasha's personal AP Physics 1 tutor. Sasha is a 15-year-old student with her AP Physics 1 exam on May 6, 2026.

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
| 3 | Circular Motion & Gravitation (centripetal, gravity) | 7% |
| 4 | Energy (work, KE, PE, conservation of energy) | 17% |
| 5 | Momentum & Impulse (collisions, conservation) | 12% |
| 6 | Simple Harmonic Motion (springs, pendulums) | 5% |
| 7 | Torque & Rotational Motion (moment of inertia, angular momentum) | 12% |
| 8 | Electric Charge & Force (Coulomb's law, conductors) | 7% |
| 9 | DC Circuits (Ohm's law, series/parallel, Kirchhoff's laws) | 10% |
| 10 | Mechanical Waves & Sound (interference, standing waves) | 10% |

## Key Formulas Sasha Should Know
- Kinematics: v = v₀ + at, x = v₀t + ½at², v² = v₀² + 2ax
- Forces: F = ma, W = mg, f = μN
- Circular: ac = v²/r, Fc = mv²/r
- Gravity: Fg = Gm₁m₂/r²
- Energy: KE = ½mv², PE = mgh, W = Fd·cosθ
- Momentum: p = mv, J = FΔt = Δp
- Springs: F = -kx, PE = ½kx², T = 2π√(m/k)
- Pendulum: T = 2π√(L/g)
- Torque: τ = rF·sinθ, τ_net = Iα
- Electricity: F = kq₁q₂/r², V = IR, P = IV
- Waves: v = fλ, f = 1/T

## How You Teach

### When explaining concepts:
- Start with a real-world example Sasha can visualize
- Walk through the physics step by step
- Highlight common exam traps and misconceptions
- Connect the topic to other units (physics is connected!)

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

For FRQs:
```
📝 FREE RESPONSE QUESTION
[Question with scenario, diagram description if needed]
Part (a): [question]
Part (b): [question]
...

[Guide her through each part after she attempts it]
```

### When she gets something wrong:
- Never make her feel bad
- Say "Close! Here's the trick..." or "Great attempt — let's look at this together"
- Reteach the concept from a different angle
- Use the `save_weak_topic` tool to log it for later review

### When she gets something right:
- Celebrate! "Yes! Exactly right 🎉"
- Ask a follow-up to deepen understanding

## Study Strategy for 11 Days
Prioritize high-weight units: Forces (18%), Energy (17%), Momentum (12%), Torque (12%).
Daily structure: 20 min concept review → 20 min practice MCQs → 20 min FRQ practice.

## Tools You Have
- `save_weak_topic`: Call this whenever Sasha struggles with a concept. Be proactive — log it without asking.
- `get_weak_topics`: Call this when Sasha asks for a review of what to work on, or at the start of a session.
- `get_study_schedule`: Call this when Sasha asks what to study today or this week.

Always be encouraging. You believe in Sasha completely."""

# ── Tools ─────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "save_weak_topic",
        "description": "Save a topic Sasha is struggling with for later review. Call this proactively whenever she makes an error or seems confused.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The specific topic or concept she's struggling with (e.g., 'Conservation of momentum in 2D collisions')"
                },
                "note": {
                    "type": "string",
                    "description": "Brief note about what specifically was confusing or the mistake she made"
                }
            },
            "required": ["topic", "note"]
        }
    },
    {
        "name": "get_weak_topics",
        "description": "Retrieve the list of topics Sasha has struggled with in past sessions.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_study_schedule",
        "description": "Get a recommended day-by-day study schedule based on days remaining and weak topics.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# ── Tool Implementations ───────────────────────────────────────────────────────

def load_performance() -> dict:
    if not os.path.exists(PERFORMANCE_FILE):
        return {"units": {}}
    with open(PERFORMANCE_FILE) as f:
        return json.load(f)


def save_performance(data: dict) -> None:
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def tool_get_performance_report() -> str:
    data = load_performance()
    if not data.get("units"):
        return "No performance data yet — start practicing to build your report!"
    lines = ["Performance Report:"]
    for unit in UNITS:
        u = data["units"].get(unit, {})
        level = u.get("level", 0)
        total = u.get("total", 0)
        correct = u.get("correct", 0)
        if total > 0:
            acc = int((correct / total) * 100)
            lines.append(f"• {unit}: Level {level} ({LEVEL_NAMES[level]}) — {acc}% accuracy ({correct}/{total})")
        else:
            lines.append(f"• {unit}: Not yet tested")
    return "\n".join(lines)


def load_weak_topics() -> list[dict]:
    if not os.path.exists(WEAK_TOPICS_FILE):
        return []
    with open(WEAK_TOPICS_FILE) as f:
        return json.load(f)


def save_weak_topics(topics: list[dict]) -> None:
    with open(WEAK_TOPICS_FILE, "w") as f:
        json.dump(topics, f, indent=2)


def tool_save_weak_topic(topic: str, note: str) -> str:
    topics = load_weak_topics()
    entry = {
        "topic": topic,
        "note": note,
        "logged_at": datetime.now().isoformat()
    }
    # Avoid exact duplicates
    if not any(t["topic"].lower() == topic.lower() for t in topics):
        topics.append(entry)
        save_weak_topics(topics)
        return f"✓ Logged '{topic}' as a topic to review."
    else:
        return f"'{topic}' is already in the review list."


def tool_get_weak_topics() -> str:
    topics = load_weak_topics()
    if not topics:
        return "No weak topics logged yet — great start!"
    lines = [f"• {t['topic']}: {t['note']}" for t in topics]
    return "Topics to review:\n" + "\n".join(lines)


def tool_get_study_schedule() -> str:
    today = date.today()
    days_left = (EXAM_DATE - today).days
    weak_topics = load_weak_topics()
    weak_names = [t["topic"] for t in weak_topics]

    schedule_lines = [
        f"📅 AP Physics 1 Exam: {EXAM_DATE.strftime('%B %d, %Y')} ({days_left} days away)\n"
    ]

    # High-priority units by weight
    priority_units = [
        ("Forces & Newton's Laws", "18%"),
        ("Energy", "17%"),
        ("Momentum & Impulse", "12%"),
        ("Torque & Rotational Motion", "12%"),
        ("DC Circuits", "10%"),
        ("Kinematics", "10%"),
        ("Mechanical Waves & Sound", "10%"),
        ("Electric Charge & Force", "7%"),
        ("Circular Motion & Gravitation", "7%"),
        ("Simple Harmonic Motion", "5%"),
    ]

    if days_left <= 0:
        return "The exam is today or has passed — good luck, Sasha! 🌟"

    if days_left >= 10:
        schedule_lines.append("Recommended focus areas:")
        for i, (unit, weight) in enumerate(priority_units[:days_left]):
            flag = " ⚠️ (flagged weak)" if any(unit.lower() in w.lower() for w in weak_names) else ""
            schedule_lines.append(f"  Day {i+1}: {unit} ({weight}){flag}")
        schedule_lines.append(f"\n  Last {max(1, days_left - len(priority_units))} day(s): Full practice exam + weak topic review")
    else:
        schedule_lines.append("Crunch-time plan:")
        for i in range(days_left - 1):
            unit, weight = priority_units[i % len(priority_units)]
            flag = " ⚠️" if any(unit.lower() in w.lower() for w in weak_names) else ""
            schedule_lines.append(f"  Day {i+1}: {unit} ({weight}){flag}")
        schedule_lines.append(f"  Day {days_left} (exam day): Light review, rest well 🌟")

    if weak_names:
        schedule_lines.append(f"\n⚠️  Flagged for extra attention: {', '.join(weak_names)}")

    return "\n".join(schedule_lines)


def execute_tool(name: str, tool_input: dict) -> str:
    if name == "save_weak_topic":
        return tool_save_weak_topic(tool_input["topic"], tool_input["note"])
    elif name == "get_weak_topics":
        return tool_get_weak_topics()
    elif name == "get_study_schedule":
        return tool_get_study_schedule()
    return f"Unknown tool: {name}"


# ── Conversation Loop ──────────────────────────────────────────────────────────

def days_remaining() -> int:
    return (EXAM_DATE - date.today()).days


def print_welcome():
    days = days_remaining()
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║       AP Physics 1 Tutor — Hi Sasha! 👋               ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════╝{RESET}")
    print(f"\n{YELLOW}📅 Exam date: May 6, 2026  ({days} days away!){RESET}")
    print(f"{DIM}Type 'quit' to exit • Type 'topics' to see your weak areas{RESET}\n")
    print(f"{GREEN}What would you like to work on today?{RESET}")
    print(f"{DIM}Ideas: 'quiz me on Newton's laws', 'explain energy conservation',")
    print(f"       'give me a hard FRQ on momentum', 'what should I study today?'{RESET}\n")


def chat():
    client = anthropic.Anthropic()
    messages: list[dict] = []

    print_welcome()

    while True:
        # Get user input
        try:
            user_input = input(f"{BOLD}{CYAN}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GREEN}Good luck on the exam, Sasha! You've got this! 🌟{RESET}\n")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye"):
            print(f"\n{GREEN}Great work today! Keep it up — May 6th will be here before you know it! 🌟{RESET}\n")
            break

        # Shortcut: 'topics' shows weak topics without going to the model
        if user_input.lower() == "topics":
            print(f"\n{YELLOW}{tool_get_weak_topics()}{RESET}\n")
            continue

        messages.append({"role": "user", "content": user_input})

        # Agentic loop: keep going until the model stops calling tools
        while True:
            print(f"\n{BOLD}{GREEN}Tutor:{RESET} ", end="", flush=True)

            # Stream the response
            assistant_content = []
            tool_calls = []

            with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }],
                tools=TOOLS,
                messages=messages,
            ) as stream:
                current_block_type = None

                for event in stream:
                    if event.type == "content_block_start":
                        current_block_type = event.content_block.type
                        if current_block_type == "tool_use":
                            tool_calls.append({
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input_str": ""
                            })

                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            print(event.delta.text, end="", flush=True)
                        elif event.delta.type == "input_json_delta" and tool_calls:
                            tool_calls[-1]["input_str"] += event.delta.partial_json

                final_msg = stream.get_final_message()

            print()  # newline after streamed response

            # Collect content blocks for history
            for block in final_msg.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
                elif block.type == "thinking":
                    assistant_content.append({
                        "type": "thinking",
                        "thinking": block.thinking,
                        "signature": block.signature
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            # No tool calls → we're done
            if final_msg.stop_reason != "tool_use":
                break

            # Execute tools and feed results back
            tool_results = []
            for block in final_msg.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    # Show tool activity as a dim note
                    print(f"  {DIM}[{block.name}: {result}]{RESET}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

        print()  # blank line between turns


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Sanity check
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{RED}Error: ANTHROPIC_API_KEY environment variable not set.{RESET}")
        print("Run: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    chat()
