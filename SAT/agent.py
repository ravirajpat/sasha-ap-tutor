#!/usr/bin/env python3
"""
SAT Exam Prep — Multi-Agent: Math & Reading and Writing
"""

import anthropic
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime

# ── Global constants ──────────────────────────────────────────────────────────

MODEL         = "claude-opus-4-7"
MIN_QUESTIONS = int(os.environ.get("MIN_QUESTIONS", "5"))

LEVEL_NAMES = {0: "Untested", 1: "Beginner", 2: "Developing", 3: "Proficient", 4: "Advanced", 5: "Expert"}
LEVEL_ICONS = {0: "○○○○○", 1: "●○○○○", 2: "●●○○○", 3: "●●●○○", 4: "●●●●○", 5: "●●●●●"}

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
    key: str                  # "math" | "reading_writing"
    display_name: str         # shown in UI
    icon: str                 # emoji
    exam_date: date
    units: list
    unit_weights: dict        # unit_name → int (%)
    system_prompt: str
    performance_file: str
    weak_topics_file: str
    daily_progress_file: str

# ── Shared Tools schema ───────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "save_weak_topic",
        "description": "Save a topic Sasha is struggling with for later review. Call proactively whenever she makes an error or seems confused.",
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
        "description": "Record that Sasha answered a practice question. Call after every MCQ or grid-in answer she submits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "correct": {"type": "boolean", "description": "Whether her answer was correct"},
            },
            "required": ["correct"],
        },
    },
]

_GENERATE_PRACTICE_TEST_TOOL = {
    "name": "generate_practice_test",
    "description": (
        "Generate a printable practice test PDF and a separate answer key PDF. "
        "Call AFTER you have composed all questions and full answers/explanations. "
        "The two PDFs are saved to /tmp and ready to download."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Test title, e.g. 'Algebra Practice Test' or 'Grammar & Conventions Quiz'",
            },
            "scope": {
                "type": "string",
                "description": "What the test covers, e.g. 'Linear Equations and Inequalities' or 'Sentence Boundaries'",
            },
            "mcq_questions": {
                "type": "array",
                "description": "Multiple choice questions (aim for 10-15)",
                "items": {
                    "type": "object",
                    "properties": {
                        "number":         {"type": "integer"},
                        "question":       {"type": "string"},
                        "choices":        {
                            "type": "array",
                            "description": "Exactly 4 choices, each starting with 'A) ', 'B) ', 'C) ', 'D) '",
                            "items": {"type": "string"},
                        },
                        "correct_answer": {"type": "string", "description": "Just the letter: A, B, C, or D"},
                        "explanation":    {"type": "string", "description": "Step-by-step solution"},
                    },
                    "required": ["number", "question", "choices", "correct_answer", "explanation"],
                },
            },
            "spr_questions": {
                "type": "array",
                "description": "Student-Produced Response / grid-in questions — Math only (aim for 3-4). Leave empty for Reading & Writing.",
                "items": {
                    "type": "object",
                    "properties": {
                        "number":   {"type": "integer"},
                        "question": {"type": "string", "description": "Full question text"},
                        "answer":   {"type": "string", "description": "The correct numeric or expression answer"},
                        "solution": {"type": "string", "description": "Complete worked solution"},
                    },
                    "required": ["number", "question", "answer", "solution"],
                },
            },
        },
        "required": ["title", "scope", "mcq_questions"],
    },
}

ALL_TOOLS = TOOLS + [_GENERATE_PRACTICE_TEST_TOOL]

# ── System Prompts ─────────────────────────────────────────────────────────────

_MATH_PROMPT = """You are Sasha's personal SAT Math tutor. Sasha is taking the SAT on June 6, 2026.

## Your Role
You are a warm, encouraging, and expert SAT Math tutor. You build problem-solving intuition — you teach strategies first, not just formulas. You celebrate wins and help Sasha build confidence. You adapt your teaching to what she's struggling with.

## SAT Math Exam Overview
- **Format**: 44 questions total across 2 adaptive modules (70 minutes total)
  - Module 1: 22 questions — 35 minutes
  - Module 2: 22 questions (harder or easier, based on Module 1) — 35 minutes
- **Question types**: ~75% Multiple Choice (MCQ) + ~25% Student-Produced Response (SPR / grid-in)
- **Calculator**: Desmos graphing calculator built in — available for ALL questions
- **Score**: 200–800 (Math section score); total SAT = 400–1600

## SAT Math Content Domains & Weights

| Domain | Core Topics | ~Weight |
|--------|-------------|---------|
| Algebra | Linear equations/functions/inequalities, systems of linear equations | 35% |
| Advanced Math | Quadratics, polynomials, rational/radical/exponential equations, absolute value, function notation | 35% |
| Problem Solving & Data Analysis | Ratios, rates, percentages, unit conversion, scatter plots, statistics, probability, data interpretation | 15% |
| Geometry & Trigonometry | Area & volume, lines & angles, triangles, circles, coordinate geometry, right-triangle trig, radians | 15% |

## Key Formulas — PROVIDED on the test (SAT Math Reference Sheet)
- Circle: A = πr², C = 2πr
- Rectangle: A = lw
- Triangle: A = ½bh
- Pythagorean theorem: a² + b² = c²
- Special right triangles: 30-60-90 (1 : √3 : 2) and 45-45-90 (1 : 1 : √2)
- Box: V = lwh  |  Cylinder: V = πr²h  |  Sphere: V = ⁴⁄₃πr³  |  Cone: V = ⅓πr²h  |  Pyramid: V = ⅓lwh

## Key Formulas — MEMORIZE (NOT on reference sheet)
- Quadratic formula: x = (−b ± √(b²−4ac)) / 2a
- Discriminant: b²−4ac  (>0 → 2 real roots, =0 → 1 root, <0 → no real roots)
- Slope: m = (y₂−y₁)/(x₂−x₁)
- Slope-intercept form: y = mx + b
- Point-slope form: y − y₁ = m(x − x₁)
- Standard form: ax + by = c
- Vertex form: y = a(x−h)² + k  (vertex at (h, k))
- Midpoint: ((x₁+x₂)/2, (y₁+y₂)/2)
- Distance: d = √((x₂−x₁)² + (y₂−y₁)²)
- Percent change: (new − old) / old × 100%
- Simple interest: A = P(1 + rt)
- Compound interest: A = P(1 + r/n)^(nt)
- Trig ratios: sin = opp/hyp, cos = adj/hyp, tan = opp/adj
- Pythagorean identity: sin²θ + cos²θ = 1
- Arc length (radians): s = rθ

## How You Teach

### When generating practice questions:
Always format MCQs like this:
```
📝 PRACTICE QUESTION
[Question text with all necessary information]

A) [option]
B) [option]
C) [option]
D) [option]

[Wait for Sasha's answer before revealing solution]
```

For grid-in (SPR) questions:
```
📝 GRID-IN QUESTION
[Question text]

Enter your answer: ___________

[Wait for Sasha's answer before revealing solution]
```

### When she gets something wrong:
- Never make her feel bad
- Say "Close! Here's the key strategy..." or "Great attempt — let me walk you through this"
- Reteach using a simpler example first
- Use `save_weak_topic` to log it

### When she gets something right:
- Celebrate! "Yes! Exactly right 🎉"
- Ask a quick follow-up or harder variation to deepen understanding

## SAT Math Strategies to Teach
- **Plug in numbers**: For abstract algebra questions, substitute specific values
- **Back-solve**: For MCQ, test answer choices starting from B or C (the middle)
- **Use Desmos**: For hard quadratic/trig/exponential graphs, use the built-in calculator
- **Dimensional analysis**: Always check units match; cross-multiply to convert
- **Read carefully**: SAT often hides what's being asked — underline the exact question

## Skill: Generate Practice Test (PDF)
When Sasha asks for a practice test on a topic:
1. Compose **12 MCQ** and **3 SPR/grid-in** questions appropriate for that scope.
   - MCQ: clear question, 4 choices (A/B/C/D), one correct answer, step-by-step explanation.
   - SPR: numeric answer question with full worked solution.
   - Use ASCII math notation: x^2 not x², sqrt() for square roots.
2. Call `generate_practice_test` with all the composed content.
3. Tell Sasha the file paths so she can download and print them.

## Tools You Have
- `save_weak_topic`: Call whenever Sasha struggles. Be proactive — log it without asking.
- `get_weak_topics`: Call when she asks for a review of weak areas.
- `get_study_schedule`: Call when she asks what to study today or this week.
- `record_practice_answer`: Call EVERY TIME Sasha submits an answer. Never skip this.
- `generate_practice_test`: After composing questions to produce printable PDFs.

Always be encouraging. SAT Math is all about strategy, and Sasha absolutely has this!"""


_RW_PROMPT = """You are Sasha's personal SAT Reading & Writing tutor. Sasha is taking the SAT on June 6, 2026.

## Your Role
You are a warm, encouraging, and expert SAT Reading & Writing tutor. You teach question strategies, grammar rules, and how to approach each passage type. You celebrate wins and help Sasha build confidence.

## SAT Reading & Writing Exam Overview
- **Format**: 54 questions total across 2 adaptive modules (64 minutes total)
  - Module 1: 27 questions — 32 minutes
  - Module 2: 27 questions (adaptive) — 32 minutes
- **All questions**: Multiple Choice (A–D), each based on a short passage
- **Passage length**: 1–3 sentences up to ~150 words; always self-contained
- **Score**: 200–800 (Reading & Writing section score); total SAT = 400–1600

## SAT R&W Content Domains & Weights

| Domain | Question Types | ~Weight |
|--------|----------------|---------|
| Information & Ideas | Central ideas & details, inferences, command of evidence (textual & quantitative) | 26% |
| Craft & Structure | Words in context, text structure & purpose, cross-text connections | 28% |
| Expression of Ideas | Rhetorical synthesis, transitions | 20% |
| Standard English Conventions | Sentence boundaries, form/structure/sense (grammar), punctuation | 26% |

## Domain Deep Dives

### Information & Ideas (26%)
- **Central Ideas & Details**: What is the passage mainly about? What specific detail does the author include?
- **Inferences**: What can be logically concluded? Stay close to the text — don't over-infer.
- **Command of Evidence (Textual)**: Which quote from the text best supports a given claim?
- **Command of Evidence (Quantitative)**: What does the graph/table show? How does data support or undermine the argument?

### Craft & Structure (28%)
- **Words in Context**: What does the underlined word mean AS USED in the passage? Look for tone and context clues.
- **Text Structure & Purpose**: Why did the author write this? What is the passage's organizational pattern?
- **Cross-Text Connections**: How do two passages relate — agree, disagree, one elaborates on the other?

### Expression of Ideas (20%)
- **Rhetorical Synthesis**: Given a set of notes/bullets, which sentence best accomplishes a stated writing goal?
- **Transitions**: Which transition word/phrase logically connects these two ideas?
  - Addition: furthermore, moreover, in addition
  - Contrast: however, nevertheless, in contrast, on the other hand
  - Cause/Result: therefore, consequently, thus, as a result
  - Illustration: for example, for instance, specifically

### Standard English Conventions (26%)
- **Sentence Boundaries**: Fix run-ons (use period, semicolon, or coordinating conjunction) and fragments (add subject or verb)
- **Form, Structure, Sense**: Subject-verb agreement, pronoun agreement, verb tense consistency, modifier placement, parallel structure
- **Punctuation**:
  - Comma: separate introductory phrases, list items, coordinate adjectives, non-restrictive clauses
  - Semicolon: join two independent clauses (no conjunction needed)
  - Colon: introduce a list or explanation; must have independent clause before it
  - Dash: add emphasis or interruption; can replace comma or colon

## How You Teach

### When generating practice questions:
Always format MCQs like this:
```
📝 PRACTICE QUESTION
"[Short passage text in quotes]"

[Question text]

A) [option]
B) [option]
C) [option]
D) [option]

[Wait for Sasha's answer before revealing solution]
```

### Key Strategies to Teach
- **Read the question first** (not the passage): Know exactly what to look for
- **Stay in the passage**: If the text doesn't say it, it's probably wrong
- **Words in Context**: Cover the choices, predict the meaning, then match — never just pick the common definition
- **Grammar**: Read the whole sentence. Identify the subject. Check agreement.
- **Transitions**: Identify the logical relationship BEFORE looking at choices
- **Elimination**: Every wrong answer is wrong for a specific reason — find it

### When she gets something wrong:
- Never make her feel bad
- Explain BOTH why the correct answer is right AND why the wrong one is tempting
- Use `save_weak_topic` to log recurring error patterns

### When she gets something right:
- Celebrate! "Yes! Exactly right 🎉"
- Reinforce the strategy that worked

## Skill: Generate Practice Test (PDF)
When Sasha asks for a practice test:
1. Compose **15 passage-based MCQ** questions for the given scope.
   - Each question must include a short passage (1-3 sentences).
   - 4 choices (A/B/C/D), one correct answer, explanation of why each choice is right or wrong.
2. Call `generate_practice_test` with all composed content (leave `spr_questions` empty).
3. Tell Sasha the file paths so she can download and print them.

## Tools You Have
- `save_weak_topic`: Log whenever Sasha struggles. Be proactive.
- `get_weak_topics`: When she asks for a review of weak areas.
- `get_study_schedule`: When she asks what to study today.
- `record_practice_answer`: Call EVERY TIME she submits an answer.
- `generate_practice_test`: After composing a full practice set.

Always be encouraging. With the right strategies, Reading & Writing is absolutely conquerable!"""


# ── Agent Configs ─────────────────────────────────────────────────────────────

MATH_CONFIG = AgentConfig(
    key="math",
    display_name="SAT Math",
    icon="📐",
    exam_date=date(2026, 6, 6),
    units=[
        "Algebra",
        "Advanced Math",
        "Problem Solving & Data Analysis",
        "Geometry & Trigonometry",
    ],
    unit_weights={
        "Algebra": 35,
        "Advanced Math": 35,
        "Problem Solving & Data Analysis": 15,
        "Geometry & Trigonometry": 15,
    },
    system_prompt=_MATH_PROMPT,
    performance_file="math_performance.json",
    weak_topics_file="math_weak_topics.json",
    daily_progress_file="math_daily_progress.json",
)

RW_CONFIG = AgentConfig(
    key="reading_writing",
    display_name="SAT Reading & Writing",
    icon="📖",
    exam_date=date(2026, 6, 6),
    units=[
        "Information & Ideas",
        "Craft & Structure",
        "Expression of Ideas",
        "Standard English Conventions",
    ],
    unit_weights={
        "Information & Ideas": 26,
        "Craft & Structure": 28,
        "Expression of Ideas": 20,
        "Standard English Conventions": 26,
    },
    system_prompt=_RW_PROMPT,
    performance_file="rw_performance.json",
    weak_topics_file="rw_weak_topics.json",
    daily_progress_file="rw_daily_progress.json",
)

AGENTS: dict[str, AgentConfig] = {
    "math":           MATH_CONFIG,
    "reading_writing": RW_CONFIG,
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


def get_daily_topic(config: AgentConfig) -> str:
    """Return today's study unit using a weight-prioritised round-robin schedule."""
    ordered = sorted(
        config.units,
        key=lambda u: config.unit_weights.get(u, 0),
        reverse=True,
    )
    idx = date.today().toordinal() % len(ordered)
    return ordered[idx]

# ── Tool implementations ──────────────────────────────────────────────────────

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
        return f"The SAT exam is today or has passed — good luck, Sasha! 🌟"

    lines = [f"📅 SAT Exam: {config.exam_date.strftime('%B %d, %Y')} ({days_left} days away)\n"]
    priority = sorted(config.unit_weights.items(), key=lambda x: x[1], reverse=True)

    if days_left >= len(priority):
        lines.append(f"Recommended {config.display_name} focus areas:")
        for i, (unit, w) in enumerate(priority):
            flag = " ⚠️ (flagged weak)" if any(unit.lower() in wk.lower() for wk in weak) else ""
            lines.append(f"  Day {i+1}: {unit} ({w}%){flag}")
        lines.append(f"\n  Last day(s): Full practice set + weak topic review")
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
    status = "✓ Correct!" if correct else "Keep going!"
    today  = date.today().isoformat()
    sb     = get_supabase()
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
            return f"{status} ({count}/{MIN_QUESTIONS} questions done today)"
        except Exception:
            pass
    count = _local_increment_today(config)
    return f"{status} ({count}/{MIN_QUESTIONS} questions done today)"


_FONTS_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_FONT_NORMAL = os.path.join(_FONTS_DIR, "DejaVuSans.ttf")
_FONT_BOLD   = os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")


def _build_pdf(path: str, config: AgentConfig, title: str, scope: str,
               mcq_questions: list, spr_questions: list,
               include_answers: bool) -> None:
    from fpdf import FPDF

    MARGIN = 20
    LINE_H = 7

    pdf = FPDF(format="Letter")
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=True, margin=MARGIN)

    pdf.add_font("AU",  fname=_FONT_NORMAL)
    pdf.add_font("AUB", fname=_FONT_BOLD)

    pdf.add_page()
    W = pdf.epw

    def mc(font, size, text, color=(0, 0, 0), indent=0):
        pdf.set_font(font, size=size)
        pdf.set_text_color(*color)
        pdf.set_x(MARGIN + indent)
        pdf.multi_cell(W - indent, LINE_H, text, new_x="LMARGIN", new_y="NEXT")

    # ── Header ──────────────────────────────────────────────────────────────
    label = "ANSWER KEY" if include_answers else "PRACTICE TEST"
    mc("AUB", 16, f"{config.display_name}  —  {label}")
    mc("AU",  12, title)
    mc("AU",  11, f"Scope: {scope}")
    mc("AU",  11, f"Date: {date.today().strftime('%B %d, %Y')}")
    pdf.ln(2)
    pdf.set_draw_color(60, 60, 60)
    pdf.set_line_width(0.5)
    pdf.line(MARGIN, pdf.get_y(), MARGIN + W, pdf.get_y())
    pdf.ln(4)

    if not include_answers:
        mc("AU", 11, "Name: ____________________________    Date: ____________    Period: _____")
        pdf.ln(3)

    # ── Part I: MCQ ─────────────────────────────────────────────────────────
    if mcq_questions:
        mc("AUB", 13, f"Part I: Multiple Choice  ({len(mcq_questions)} questions)")
        if not include_answers:
            mc("AU", 10, "Circle the letter of the best answer.")
        pdf.ln(2)

        for q in mcq_questions:
            mc("AUB", 11, f"{q['number']}.  {q['question']}")
            for choice in q.get("choices", []):
                mc("AU", 11, choice, indent=8)
            if include_answers:
                mc("AUB", 11, f"Answer: {q['correct_answer']}", color=(0, 120, 0), indent=8)
                mc("AU",  11, q["explanation"], color=(0, 100, 0), indent=8)
                pdf.set_text_color(0, 0, 0)
            pdf.ln(3)

    # ── Part II: SPR (Math grid-in questions) ──────────────────────────────
    if spr_questions:
        pdf.add_page()
        mc("AUB", 13, f"Part II: Student-Produced Response  ({len(spr_questions)} questions)")
        if not include_answers:
            mc("AU", 10, "Grid in your answer. No penalty for guessing — always enter an answer.")
        pdf.ln(3)

        for q in spr_questions:
            mc("AUB", 11, f"{q['number']}.  {q['question']}")
            pdf.ln(2)
            if include_answers:
                mc("AUB", 11, f"Answer: {q['answer']}", color=(0, 120, 0), indent=8)
                for line in q["solution"].splitlines():
                    mc("AU", 11, line if line.strip() else " ", color=(0, 100, 0), indent=5)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.set_draw_color(200, 200, 200)
                for _ in range(8):
                    y = pdf.get_y() + LINE_H
                    pdf.line(MARGIN, y, MARGIN + W, y)
                    pdf.ln(LINE_H)
            pdf.ln(5)

    pdf.output(path)


def _email_practice_test(config: AgentConfig, title: str, scope: str,
                          test_path: str, key_path: str,
                          n_mcq: int, n_spr: int) -> str:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText as _MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    gmail_user  = os.environ.get("GMAIL_USER")
    gmail_pass  = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    sasha_email = os.environ.get("SASHA_EMAIL")

    if not all([gmail_user, gmail_pass, sasha_email]):
        return "email skipped (GMAIL_USER / GMAIL_APP_PASSWORD / SASHA_EMAIL not set)"

    msg = MIMEMultipart()
    msg["From"]    = gmail_user
    msg["To"]      = sasha_email
    msg["Subject"] = f"📝 Practice Test Ready: {title}"

    spr_line = f"  {n_spr} Grid-In (SPR)\n" if n_spr else ""
    body = (
        f"Hi Sasha! 👋\n\n"
        f"Your {config.display_name} practice test is attached and ready to print!\n\n"
        f"  📄 {title}\n"
        f"  Scope: {scope}\n"
        f"  {n_mcq} Multiple Choice\n"
        f"{spr_line}\n"
        f"Two files attached:\n"
        f"  1. Practice Test  — work through it without peeking!\n"
        f"  2. Answer Key     — check your work after.\n\n"
        f"Good luck! You've got this 🌟\n\n"
        f"— Your SAT Tutor"
    )
    msg.attach(_MIMEText(body, "plain"))

    for path in [test_path, key_path]:
        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        server.login(gmail_user, gmail_pass)
        server.send_message(msg)

    return f"emailed to {sasha_email}"


def tool_generate_practice_test(config: AgentConfig, title: str, scope: str,
                                 mcq_questions: list, spr_questions: list) -> str:
    out_dir = os.path.join("/tmp", "sasha_sat_practice_tests")
    os.makedirs(out_dir, exist_ok=True)

    safe = re.sub(r'[^\w]', '_', title)[:40].strip('_')
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    test_path = os.path.join(out_dir, f"{safe}_{ts}.pdf")
    key_path  = os.path.join(out_dir, f"{safe}_{ts}_ANSWER_KEY.pdf")

    try:
        _build_pdf(test_path, config, title, scope, mcq_questions, spr_questions, include_answers=False)
        _build_pdf(key_path,  config, title, scope, mcq_questions, spr_questions, include_answers=True)
    except ImportError:
        return "PDF generation requires fpdf2. Install with: pip install fpdf2"
    except Exception as e:
        return f"Error generating PDFs: {e}"

    try:
        email_status = _email_practice_test(
            config, title, scope, test_path, key_path,
            len(mcq_questions), len(spr_questions),
        )
    except Exception as e:
        email_status = f"email failed: {e}"

    return (
        f"Practice test saved!\n"
        f"  Test:       {test_path}\n"
        f"  Answer Key: {key_path}\n"
        f"  ({len(mcq_questions)} MCQ"
        + (f" + {len(spr_questions)} SPR" if spr_questions else "")
        + f")\n"
        f"  Email: {email_status}"
    )


def execute_tool(name: str, tool_input: dict, config: AgentConfig) -> str:
    if name == "save_weak_topic":
        return tool_save_weak_topic(config, tool_input["topic"], tool_input["note"])
    elif name == "get_weak_topics":
        return tool_get_weak_topics(config)
    elif name == "get_study_schedule":
        return tool_get_study_schedule(config)
    elif name == "record_practice_answer":
        return tool_record_practice_answer(config, tool_input["correct"])
    elif name == "generate_practice_test":
        return tool_generate_practice_test(
            config,
            tool_input["title"],
            tool_input["scope"],
            tool_input.get("mcq_questions", []),
            tool_input.get("spr_questions", []),
        )
    return f"Unknown tool: {name}"

# ── Convenience helpers ────────────────────────────────────────────────────────

def days_remaining(config: AgentConfig) -> int:
    return (config.exam_date - date.today()).days

# ── CLI chat loop ─────────────────────────────────────────────────────────────

def chat(config: AgentConfig):
    client   = anthropic.Anthropic()
    messages: list[dict] = []
    days     = days_remaining(config)
    tools    = ALL_TOOLS

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║  {config.icon}  {config.display_name} Tutor — Hi Sasha! 👋{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════╝{RESET}")
    print(f"\n{YELLOW}📅 SAT Exam: {config.exam_date.strftime('%B %d, %Y')} ({days} days away!){RESET}")
    print(f"{DIM}Type 'quit' to exit • 'topics' to see weak areas{RESET}\n")

    while True:
        try:
            user_input = input(f"{BOLD}{CYAN}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GREEN}Good luck on the SAT, Sasha! You've got this! 🌟{RESET}\n")
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
                max_tokens=8192,
                thinking={"type": "adaptive"},
                system=[{"type": "text", "text": config.system_prompt, "cache_control": {"type": "ephemeral"}}],
                tools=tools,
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

    subject = sys.argv[1] if len(sys.argv) > 1 else "math"
    if subject not in AGENTS:
        print(f"{RED}Unknown subject '{subject}'. Choose: {list(AGENTS)}{RESET}")
        sys.exit(1)

    chat(AGENTS[subject])
