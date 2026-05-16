#!/usr/bin/env python3
"""
Full-length SAT practice test — generation, storage, and scoring.
Generates realistic 4-module tests (R&W ×2 + Math ×2) using Claude.
"""

import json
import os
import re
from datetime import datetime
from typing import Callable, Optional

TESTS_DIR = "/tmp/sasha_sat_full_tests"
os.makedirs(TESTS_DIR, exist_ok=True)

# ── Module definitions ────────────────────────────────────────────────────────

MODULE_CONFIGS = [
    {
        "key": "rw_1",
        "display": "Reading & Writing — Module 1",
        "section": "reading_writing",
        "module_num": 1,
        "time_minutes": 32,
        "num_questions": 27,
        "num_spr": 0,
        "difficulty_note": "easy to medium",
        "domain_counts": {
            "Information & Ideas": 7,
            "Craft & Structure": 8,
            "Expression of Ideas": 5,
            "Standard English Conventions": 7,
        },
    },
    {
        "key": "rw_2",
        "display": "Reading & Writing — Module 2",
        "section": "reading_writing",
        "module_num": 2,
        "time_minutes": 32,
        "num_questions": 27,
        "num_spr": 0,
        "difficulty_note": "medium to hard",
        "domain_counts": {
            "Information & Ideas": 7,
            "Craft & Structure": 8,
            "Expression of Ideas": 5,
            "Standard English Conventions": 7,
        },
    },
    {
        "key": "math_1",
        "display": "Math — Module 1",
        "section": "math",
        "module_num": 1,
        "time_minutes": 35,
        "num_questions": 22,
        "num_spr": 5,
        "difficulty_note": "easy to medium",
        "domain_counts": {
            "Algebra": 7,
            "Advanced Math": 6,
            "Problem Solving & Data Analysis": 4,
            "Geometry & Trigonometry": 5,
        },
    },
    {
        "key": "math_2",
        "display": "Math — Module 2",
        "section": "math",
        "module_num": 2,
        "time_minutes": 35,
        "num_questions": 22,
        "num_spr": 5,
        "difficulty_note": "medium to hard",
        "domain_counts": {
            "Algebra": 7,
            "Advanced Math": 6,
            "Problem Solving & Data Analysis": 4,
            "Geometry & Trigonometry": 5,
        },
    },
]

# ── Generation tool schema ────────────────────────────────────────────────────

_SUBMIT_QUESTIONS_TOOL = {
    "name": "submit_questions",
    "description": "Submit the fully composed questions for this module.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number":         {"type": "integer", "description": "Question number within this module (1-based)"},
                        "type":           {"type": "string", "enum": ["mcq", "spr"]},
                        "domain":         {"type": "string"},
                        "difficulty":     {"type": "string", "enum": ["easy", "medium", "hard"]},
                        "passage":        {"type": "string", "description": "Short passage (required for R&W; optional for Math with context)"},
                        "question":       {"type": "string"},
                        "choices":        {"type": "array", "items": {"type": "string"},
                                           "description": "MCQ only: exactly 4 strings starting with 'A) ', 'B) ', 'C) ', 'D) '"},
                        "correct_answer": {"type": "string", "description": "Letter A-D for MCQ; numeric string for SPR"},
                        "explanation":    {"type": "string", "description": "Full explanation of the correct answer"},
                    },
                    "required": ["number", "type", "domain", "difficulty", "question", "correct_answer", "explanation"],
                },
            }
        },
        "required": ["questions"],
    },
}

# ── Generation prompts ────────────────────────────────────────────────────────

def _rw_prompt(cfg: dict) -> str:
    dist = "\n".join(f"  • {d}: {n} questions" for d, n in cfg["domain_counts"].items())
    return f"""Generate {cfg['num_questions']} SAT Reading & Writing questions for Module {cfg['module_num']}.
Difficulty: {cfg['difficulty_note']}.

Domain distribution:
{dist}

CRITICAL requirements — follow exactly:
• Every question MUST include a "passage" field: a realistic 1-4 sentence excerpt (50-120 words) from an academic, literary, or informational text. The Digital SAT always pairs each R&W question with a passage.
• All questions are multiple choice (type: "mcq") with exactly 4 choices: A), B), C), D).
• Choices must start with exactly "A) ", "B) ", "C) ", "D) " (letter, close-paren, space).
• correct_answer is a single letter: A, B, C, or D.

Domain guidance:
• Information & Ideas — main idea, specific detail, inference, command of evidence (quote that supports a claim), or data interpretation.
• Craft & Structure — words-in-context ("As used in the passage, X most nearly means..."), text structure/purpose, or cross-text connections (give two short passages and ask how author B would respond to author A).
• Expression of Ideas — rhetorical synthesis ("Which sentence most effectively introduces...") or transitions ("Which choice most logically connects these sentences?").
• Standard English Conventions — the passage contains a blank [______] or underlined segment; the question asks which choice correctly completes or revises it. Test subject-verb agreement, pronoun agreement, comma use, semicolons, colons, verb tense, or sentence boundaries.

Number questions 1 through {cfg['num_questions']}. Call submit_questions with all {cfg['num_questions']} questions."""


def _math_prompt(cfg: dict) -> str:
    n_mcq = cfg["num_questions"] - cfg["num_spr"]
    dist  = "\n".join(f"  • {d}: {n} questions" for d, n in cfg["domain_counts"].items())
    return f"""Generate {cfg['num_questions']} SAT Math questions for Module {cfg['module_num']}.
Difficulty: {cfg['difficulty_note']}.
Total: {n_mcq} multiple choice (MCQ) + {cfg['num_spr']} student-produced response (SPR/grid-in).

Domain distribution (spread MCQ and SPR across domains):
{dist}

CRITICAL requirements — follow exactly:
• MCQ questions (type: "mcq"): 4 choices starting with "A) ", "B) ", "C) ", "D) ". correct_answer is A, B, C, or D.
• SPR questions (type: "spr"): NO choices field. correct_answer is a numeric string (integer or decimal, e.g. "7", "3.5", "12/5"). The question must have a single, unambiguous numeric answer.
• Calculator is available for all questions.
• Use clear, self-contained question stems. If a question references a figure, describe it in text (e.g., "In the figure, triangle ABC has sides...").
• Do NOT reference images, graphs, or tables you can't describe in text.
• passage field is optional — include only for word problems with a real-world scenario.

Domain guidance:
• Algebra — linear equations/inequalities, slope, systems of equations, linear functions.
• Advanced Math — quadratics (factoring, quadratic formula, vertex form), polynomials, exponential functions, rational equations, function notation.
• Problem Solving & Data Analysis — percent, ratio, rates, unit conversion, statistics (mean/median/mode), probability, scatter plots described in text.
• Geometry & Trigonometry — area, volume, Pythagorean theorem, similar triangles, circle properties, right-triangle trig (sin/cos/tan), arc length.

Number questions 1 through {cfg['num_questions']}. Call submit_questions with all {cfg['num_questions']} questions."""


# ── Module generation ─────────────────────────────────────────────────────────

def generate_module(client, cfg: dict) -> list[dict]:
    """Call Claude once to generate all questions for one module. Returns question list."""
    prompt = _rw_prompt(cfg) if cfg["section"] == "reading_writing" else _math_prompt(cfg)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        tools=[_SUBMIT_QUESTIONS_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    def _attr(obj, *keys):
        """Get attribute or dict key, trying each key in order."""
        for k in keys:
            try:
                return getattr(obj, k)
            except AttributeError:
                pass
            if isinstance(obj, dict):
                try:
                    return obj[k]
                except KeyError:
                    pass
        return None

    for block in response.content:
        btype = _attr(block, "type")
        bname = _attr(block, "name")
        if btype == "tool_use" and bname == "submit_questions":
            inp = _attr(block, "input") or {}
            if isinstance(inp, str):
                try:
                    inp = json.loads(inp)
                except json.JSONDecodeError:
                    inp = {}
            if not isinstance(inp, dict):
                inp = {}
            questions = inp.get("questions", [])
            if not isinstance(questions, list):
                questions = []
            for q in questions:
                if isinstance(q, dict) and q.get("type") == "mcq" and not q.get("choices"):
                    q["choices"] = ["A) —", "B) —", "C) —", "D) —"]
            return questions

    # Fallback: try to extract JSON from text content
    for block in response.content:
        btype = _attr(block, "type")
        btext = _attr(block, "text") or ""
        if btype == "text":
            m = re.search(r'\[.*\]', btext, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
    return []


def generate_full_test(client, on_status: Optional[Callable[[str], None]] = None) -> dict:
    """Generate all 4 modules. on_status(msg) is called with progress updates."""
    test_id = datetime.now().strftime("test_%Y%m%d_%H%M%S")
    modules = []

    for cfg in MODULE_CONFIGS:
        if on_status:
            on_status(f"Generating {cfg['display']} ({cfg['num_questions']} questions)…")
        questions = generate_module(client, cfg)
        modules.append({
            "key":          cfg["key"],
            "display":      cfg["display"],
            "section":      cfg["section"],
            "module_num":   cfg["module_num"],
            "time_minutes": cfg["time_minutes"],
            "questions":    questions,
        })
        if on_status:
            on_status(f"✅ {cfg['display']} — {len(questions)} questions generated")

    return {
        "id":         test_id,
        "created_at": datetime.now().isoformat(),
        "modules":    modules,
    }


# ── Storage ───────────────────────────────────────────────────────────────────

def save_test(test_data: dict) -> str:
    path = os.path.join(TESTS_DIR, f"{test_data['id']}.json")
    with open(path, "w") as f:
        json.dump(test_data, f, indent=2)
    return test_data["id"]


def load_test(test_id: str) -> dict:
    path = os.path.join(TESTS_DIR, f"{test_id}.json")
    with open(path) as f:
        return json.load(f)


def list_saved_tests() -> list[dict]:
    """Return list of test metadata dicts, newest first."""
    tests = []
    for fname in sorted(os.listdir(TESTS_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(TESTS_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            tests.append({
                "id":         data["id"],
                "created_at": data.get("created_at", ""),
                "path":       path,
            })
        except Exception:
            pass
    return tests


# ── Scoring ───────────────────────────────────────────────────────────────────

# Approximate raw→scaled tables derived from published College Board data.
# Each tuple: (raw_score, scaled_score). Linear interpolation between points.
_RW_TABLE = [
    (0, 200), (5, 280), (10, 330), (15, 380), (20, 430),
    (25, 480), (30, 530), (35, 575), (40, 620), (45, 660),
    (50, 720), (54, 800),
]
_MATH_TABLE = [
    (0, 200), (5, 280), (10, 350), (15, 420), (20, 490),
    (25, 540), (30, 590), (35, 640), (38, 690), (41, 740),
    (43, 770), (44, 800),
]


def _interpolate(raw: int, table: list[tuple]) -> int:
    if raw <= table[0][0]:
        return table[0][1]
    if raw >= table[-1][0]:
        return table[-1][1]
    for i in range(len(table) - 1):
        r0, s0 = table[i]
        r1, s1 = table[i + 1]
        if r0 <= raw <= r1:
            frac = (raw - r0) / (r1 - r0)
            return round(s0 + frac * (s1 - s0) / 10) * 10
    return table[-1][1]


def score_test(test_data: dict, answers: dict) -> dict:
    """
    answers: {module_idx: {q_idx: answer_str}}
    Returns a score report dict.
    """
    section_raw  = {"reading_writing": 0, "math": 0}
    section_total = {"reading_writing": 0, "math": 0}
    domain_scores: dict[str, dict] = {}
    question_results: list[dict]   = []

    for mod_idx, module in enumerate(test_data["modules"]):
        section = module["section"]
        mod_answers = answers.get(mod_idx, {})

        for q_idx, q in enumerate(module["questions"]):
            domain    = q.get("domain", "Unknown")
            given     = mod_answers.get(q_idx, "").strip().upper()
            correct   = q.get("correct_answer", "").strip().upper()

            # SPR: accept equivalent numeric forms (e.g. "3.5" == "3.50")
            if q.get("type") == "spr":
                try:
                    is_correct = abs(float(given) - float(correct)) < 0.01
                except ValueError:
                    is_correct = given == correct
            else:
                is_correct = bool(given) and given[0] == correct[0] if correct else False

            section_total[section] += 1
            if is_correct:
                section_raw[section] += 1

            if domain not in domain_scores:
                domain_scores[domain] = {"correct": 0, "total": 0}
            domain_scores[domain]["total"]   += 1
            if is_correct:
                domain_scores[domain]["correct"] += 1

            question_results.append({
                "module_idx":  mod_idx,
                "module":      module["display"],
                "q_idx":       q_idx,
                "number":      q.get("number", q_idx + 1),
                "domain":      domain,
                "type":        q.get("type", "mcq"),
                "given":       mod_answers.get(q_idx, ""),
                "correct":     q.get("correct_answer", ""),
                "is_correct":  is_correct,
                "explanation": q.get("explanation", ""),
                "question":    q.get("question", ""),
                "passage":     q.get("passage", ""),
                "choices":     q.get("choices", []),
            })

    rw_raw   = section_raw["reading_writing"]
    math_raw = section_raw["math"]
    rw_scaled   = _interpolate(rw_raw,   _RW_TABLE)
    math_scaled = _interpolate(math_raw, _MATH_TABLE)

    return {
        "rw_raw":    rw_raw,
        "rw_total":  section_total["reading_writing"],
        "rw_scaled": rw_scaled,
        "math_raw":    math_raw,
        "math_total":  section_total["math"],
        "math_scaled": math_scaled,
        "total_scaled": rw_scaled + math_scaled,
        "domain_scores":   domain_scores,
        "question_results": question_results,
    }
