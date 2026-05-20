#!/usr/bin/env python3
"""
Topic-focused SAT mini-tests with Khan Academy review links.
"""

import json
import re

# ── Topic catalog ─────────────────────────────────────────────────────────────

_KA_MATH = "https://www.khanacademy.org/test-prep/v2-sat-math/x0fcc98a58ba3bea7"
_KA_RW   = "https://www.khanacademy.org/test-prep/sat-reading-and-writing/x0d47bcec73eb6c4b"

TOPIC_CATALOG = {
    "math": [
        {
            "label":     "Linear Equations & Inequalities",
            "domain":    "Algebra",
            "subtopics": "solving one- and two-variable linear equations, compound inequalities, absolute value equations and inequalities",
            "ka_url":    f"{_KA_MATH}:algebra-medium",
            "ka_label":  "SAT Algebra (Medium) — Khan Academy",
        },
        {
            "label":     "Systems of Equations",
            "domain":    "Algebra",
            "subtopics": "substitution method, elimination method, word problems involving two unknowns, number of solutions",
            "ka_url":    f"{_KA_MATH}:algebra-medium",
            "ka_label":  "SAT Algebra (Medium) — Khan Academy",
        },
        {
            "label":     "Linear Functions & Graphs",
            "domain":    "Algebra",
            "subtopics": "slope, y-intercept, slope-intercept and point-slope form, graphing lines, parallel and perpendicular lines, rate of change",
            "ka_url":    f"{_KA_MATH}:algebra-easier",
            "ka_label":  "SAT Algebra (Easier) — Khan Academy",
        },
        {
            "label":     "Quadratics",
            "domain":    "Advanced Math",
            "subtopics": "factoring, quadratic formula, completing the square, vertex form, discriminant, roots and zeros, parabola properties",
            "ka_url":    f"{_KA_MATH}:advanced-math-medium",
            "ka_label":  "SAT Advanced Math (Medium) — Khan Academy",
        },
        {
            "label":     "Exponential Functions",
            "domain":    "Advanced Math",
            "subtopics": "exponential growth and decay, percent change, doubling time, half-life, y = ab^x models",
            "ka_url":    f"{_KA_MATH}:advanced-math-medium",
            "ka_label":  "SAT Advanced Math (Medium) — Khan Academy",
        },
        {
            "label":     "Polynomials & Rational Expressions",
            "domain":    "Advanced Math",
            "subtopics": "polynomial operations, factoring higher-degree polynomials, rational equations, function notation, composition of functions",
            "ka_url":    f"{_KA_MATH}:advanced-math-harder",
            "ka_label":  "SAT Advanced Math (Harder) — Khan Academy",
        },
        {
            "label":     "Geometry",
            "domain":    "Geometry & Trigonometry",
            "subtopics": "area, perimeter, volume (cylinder, cone, sphere), Pythagorean theorem, similar triangles, circle properties, arc length, sector area",
            "ka_url":    f"{_KA_MATH}:geometry-and-trigonometry-medium",
            "ka_label":  "SAT Geometry & Trig (Medium) — Khan Academy",
        },
        {
            "label":     "Trigonometry",
            "domain":    "Geometry & Trigonometry",
            "subtopics": "sine, cosine, tangent (SOH-CAH-TOA), special right triangles (30-60-90, 45-45-90), unit circle basics, radians",
            "ka_url":    f"{_KA_MATH}:geometry-and-trigonometry-harder",
            "ka_label":  "SAT Geometry & Trig (Harder) — Khan Academy",
        },
        {
            "label":     "Statistics & Data Analysis",
            "domain":    "Problem Solving & Data Analysis",
            "subtopics": "mean, median, mode, range, standard deviation, scatter plots, line of best fit, correlation vs causation, data interpretation",
            "ka_url":    f"{_KA_MATH}:problem-solving-and-data-analysis-medium",
            "ka_label":  "SAT Problem Solving & Data Analysis (Medium) — Khan Academy",
        },
        {
            "label":     "Ratios, Rates & Proportions",
            "domain":    "Problem Solving & Data Analysis",
            "subtopics": "unit rates, proportional relationships, unit conversion, scale factors, direct and inverse variation",
            "ka_url":    f"{_KA_MATH}:problem-solving-and-data-analysis-easier",
            "ka_label":  "SAT Problem Solving & Data Analysis (Easier) — Khan Academy",
        },
        {
            "label":     "Percentages",
            "domain":    "Problem Solving & Data Analysis",
            "subtopics": "percent of a whole, percent change, simple interest, compound interest, tax, discount, markup",
            "ka_url":    f"{_KA_MATH}:problem-solving-and-data-analysis-medium",
            "ka_label":  "SAT Problem Solving & Data Analysis (Medium) — Khan Academy",
        },
        {
            "label":     "Probability",
            "domain":    "Problem Solving & Data Analysis",
            "subtopics": "basic probability, conditional probability, two-way tables, counting principle, independent and dependent events",
            "ka_url":    f"{_KA_MATH}:problem-solving-and-data-analysis-harder",
            "ka_label":  "SAT Problem Solving & Data Analysis (Harder) — Khan Academy",
        },
    ],
    "reading_writing": [
        {
            "label":     "Words in Context",
            "domain":    "Craft & Structure",
            "subtopics": "determining vocabulary meaning from context, choosing the best word to fit tone/meaning, distinguishing similar words",
            "ka_url":    f"{_KA_RW}:medium-craft-and-structure",
            "ka_label":  "SAT Craft & Structure (Medium) — Khan Academy",
        },
        {
            "label":     "Text Structure & Purpose",
            "domain":    "Craft & Structure",
            "subtopics": "identifying how a paragraph or sentence functions in the passage (introduces, contrasts, supports, concludes), author's purpose",
            "ka_url":    f"{_KA_RW}:medium-craft-and-structure",
            "ka_label":  "SAT Craft & Structure (Medium) — Khan Academy",
        },
        {
            "label":     "Cross-Text Connections",
            "domain":    "Craft & Structure",
            "subtopics": "comparing two short passages — agreement, disagreement, complementary perspectives, how author B would respond to author A",
            "ka_url":    f"{_KA_RW}:advanced-craft-and-structure",
            "ka_label":  "SAT Craft & Structure (Advanced) — Khan Academy",
        },
        {
            "label":     "Main Idea & Details",
            "domain":    "Information & Ideas",
            "subtopics": "central idea of a passage, specific supporting details, distinguishing main idea from supporting detail",
            "ka_url":    f"{_KA_RW}:foundations-information-and-ideas",
            "ka_label":  "SAT Information & Ideas (Foundations) — Khan Academy",
        },
        {
            "label":     "Inferences",
            "domain":    "Information & Ideas",
            "subtopics": "logical conclusions from a passage, what the text implies but does not state directly, avoiding over-inference",
            "ka_url":    f"{_KA_RW}:medium-information-and-ideas",
            "ka_label":  "SAT Information & Ideas (Medium) — Khan Academy",
        },
        {
            "label":     "Command of Evidence",
            "domain":    "Information & Ideas",
            "subtopics": "selecting the quote that best supports a given claim, interpreting data in tables or graphs alongside a passage",
            "ka_url":    f"{_KA_RW}:advanced-information-and-ideas",
            "ka_label":  "SAT Information & Ideas (Advanced) — Khan Academy",
        },
        {
            "label":     "Transitions",
            "domain":    "Expression of Ideas",
            "subtopics": "choosing the correct transition word (addition, contrast, cause/effect, example, sequence) to logically connect sentences or ideas",
            "ka_url":    f"{_KA_RW}:foundations-expression-of-ideas-and-standard-english-conventions",
            "ka_label":  "SAT Expression of Ideas & Conventions (Foundations) — Khan Academy",
        },
        {
            "label":     "Rhetorical Synthesis",
            "domain":    "Expression of Ideas",
            "subtopics": "selecting the sentence that best accomplishes a stated writing goal, synthesizing notes into a cohesive sentence",
            "ka_url":    f"{_KA_RW}:medium-expression-of-ideas-and-standard-english-conventions",
            "ka_label":  "SAT Expression of Ideas & Conventions (Medium) — Khan Academy",
        },
        {
            "label":     "Sentence Boundaries",
            "domain":    "Standard English Conventions",
            "subtopics": "fixing run-ons and fragments using periods, semicolons, commas + coordinating conjunctions (FANBOYS), subordinating conjunctions",
            "ka_url":    f"{_KA_RW}:foundations-expression-of-ideas-and-standard-english-conventions",
            "ka_label":  "SAT Expression of Ideas & Conventions (Foundations) — Khan Academy",
        },
        {
            "label":     "Subject-Verb & Pronoun Agreement",
            "domain":    "Standard English Conventions",
            "subtopics": "subject-verb agreement (including tricky prepositional phrases), pronoun-antecedent agreement in number and gender",
            "ka_url":    f"{_KA_RW}:medium-expression-of-ideas-and-standard-english-conventions",
            "ka_label":  "SAT Expression of Ideas & Conventions (Medium) — Khan Academy",
        },
        {
            "label":     "Punctuation",
            "domain":    "Standard English Conventions",
            "subtopics": "comma rules (introductory phrase, list, non-essential clause), semicolons, colons, apostrophes (possessives vs. contractions)",
            "ka_url":    f"{_KA_RW}:medium-expression-of-ideas-and-standard-english-conventions",
            "ka_label":  "SAT Expression of Ideas & Conventions (Medium) — Khan Academy",
        },
        {
            "label":     "Verb Tense & Modifiers",
            "domain":    "Standard English Conventions",
            "subtopics": "consistent verb tense, misplaced and dangling modifiers, parallel structure",
            "ka_url":    f"{_KA_RW}:advanced-expression-of-ideas-and-standard-english-conventions",
            "ka_label":  "SAT Expression of Ideas & Conventions (Advanced) — Khan Academy",
        },
    ],
}

# ── Tool schema (same structure as full test) ─────────────────────────────────

_SUBMIT_QUESTIONS_TOOL = {
    "name": "submit_questions",
    "description": "Submit the fully composed questions for this topic mini-test.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number":         {"type": "integer"},
                        "type":           {"type": "string", "enum": ["mcq", "spr"]},
                        "domain":         {"type": "string"},
                        "difficulty":     {"type": "string", "enum": ["easy", "medium", "hard"]},
                        "concept":        {"type": "string", "description": "The single specific concept this question tests, as a short 2-5 word phrase (e.g. 'Pythagorean theorem', 'factoring quadratics', 'comma splices', 'subject-verb agreement'). Used to generate a targeted Khan Academy review link."},
                        "passage":        {"type": "string"},
                        "question":       {"type": "string"},
                        "choices":        {"type": "array", "items": {"type": "string"}},
                        "correct_answer": {"type": "string"},
                        "explanation":    {"type": "string"},
                    },
                    "required": ["number", "type", "domain", "difficulty", "concept", "question", "correct_answer", "explanation"],
                },
            }
        },
        "required": ["questions"],
    },
}


_DIFFICULTY_LINE = {
    "mixed": "Difficulty: mixed — include a spread of easy, medium, and hard questions.",
    "easy":  "Difficulty: easy — all questions should test basic understanding and be straightforward.",
    "medium": "Difficulty: medium — all questions should require solid understanding and application.",
    "hard":  "Difficulty: hard — all questions should be challenging and require deep analysis or multi-step reasoning.",
}


def _build_prompt(subject: str, topic: dict, num_questions: int, difficulty: str = "mixed") -> str:
    diff_line = _DIFFICULTY_LINE.get(difficulty, _DIFFICULTY_LINE["mixed"])
    if subject == "math":
        spr_count = max(1, num_questions // 5) if num_questions >= 5 else 0
        mcq_count = num_questions - spr_count
        return f"""Generate {num_questions} SAT Math questions focused ENTIRELY on the topic: "{topic['label']}".

Subtopics to cover: {topic['subtopics']}
Domain: {topic['domain']}
{diff_line}
Format: {mcq_count} multiple choice (MCQ) + {spr_count} student-produced response (SPR/grid-in)

CRITICAL requirements:
• MCQ (type: "mcq"): exactly 4 choices starting with "A) ", "B) ", "C) ", "D) ". correct_answer is a single letter A–D.
• SPR (type: "spr"): NO choices field. correct_answer is a numeric string (e.g. "7", "3.5"). Single unambiguous numeric answer.
• Every question must be directly on the topic "{topic['label']}". Do NOT include questions on unrelated topics.
• Use clear, self-contained stems. If referencing a figure, describe it in text.
• passage field is optional — include only for word problems with a real-world scenario.
• Include a thorough explanation for every question.
• concept field: a short 2–5 word phrase naming the EXACT concept tested (e.g. "Pythagorean theorem", "slope-intercept form", "factoring quadratics", "circle arc length"). Be specific — this is used to link to the exact Khan Academy lesson.

Number questions 1 through {num_questions}. Call submit_questions with all {num_questions} questions."""

    else:  # reading_writing
        return f"""Generate {num_questions} SAT Reading & Writing questions focused ENTIRELY on the topic: "{topic['label']}".

Subtopics to cover: {topic['subtopics']}
Domain: {topic['domain']}
{diff_line}
All questions: multiple choice (type: "mcq") with exactly 4 choices.

CRITICAL requirements:
• Every question MUST include a "passage" field: a realistic 1–4 sentence excerpt (50–120 words) from an academic, literary, or informational text.
• Choices start with exactly "A) ", "B) ", "C) ", "D) ". correct_answer is a single letter A–D.
• Every question must be directly on the topic "{topic['label']}". Do NOT mix in unrelated question types.
• Include a thorough explanation for every question.
• concept field: a short 2–5 word phrase naming the EXACT concept tested (e.g. "comma splices", "transition words contrast", "subject-verb agreement", "vocabulary in context", "command of evidence textual"). Be specific — this is used to link to the exact Khan Academy lesson.

{_rw_specific_guidance(topic['label'])}

Number questions 1 through {num_questions}. Call submit_questions with all {num_questions} questions."""


def concept_ka_url(concept: str) -> str:
    """Build a Khan Academy SAT search URL for a specific concept."""
    import urllib.parse
    query = urllib.parse.quote_plus(f"SAT {concept}")
    return f"https://www.khanacademy.org/search?page_search_query={query}"


def _rw_specific_guidance(label: str) -> str:
    guides = {
        "Words in Context": 'Each question: "As used in the passage, the word/phrase X most nearly means..." with 4 vocabulary choices.',
        "Text Structure & Purpose": 'Each question asks what function a sentence/paragraph serves or why the author included it.',
        "Cross-Text Connections": 'Each question provides TWO short passages and asks how the authors relate to each other.',
        "Main Idea & Details": 'Mix of central idea questions and specific detail retrieval questions.',
        "Inferences": 'Each question asks what can be logically inferred or concluded from the passage.',
        "Command of Evidence": 'Alternate between text-evidence questions (which quote best supports X?) and data/graph interpretation.',
        "Transitions": 'Each passage contains a blank; the question asks which transition word/phrase best connects the ideas.',
        "Rhetorical Synthesis": 'Each question provides 3–4 bullet-point notes and asks which sentence best accomplishes a stated goal.',
        "Sentence Boundaries": 'Each passage contains a blank [______] or underline; test run-ons and fragments.',
        "Subject-Verb & Pronoun Agreement": 'Each passage contains a blank; test agreement errors.',
        "Punctuation": 'Each passage contains a blank; test comma, semicolon, colon, or apostrophe usage.',
        "Verb Tense & Modifiers": 'Each passage contains a blank; test verb tense consistency, modifiers, or parallel structure.',
    }
    return guides.get(label, "")


def generate_topic_test(
    client,
    subject: str,
    topic: dict,
    num_questions: int,
    difficulty: str = "mixed",
    on_status: callable = None,
) -> list[dict]:
    """Generate questions for one topic. Returns list of question dicts."""
    if on_status:
        on_status(f"Generating {num_questions} questions on **{topic['label']}**…")

    prompt = _build_prompt(subject, topic, num_questions, difficulty)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        tools=[_SUBMIT_QUESTIONS_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": prompt}],
    )

    def _attr(obj, *keys):
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
        if _attr(block, "type") == "tool_use" and _attr(block, "name") == "submit_questions":
            inp = _attr(block, "input") or {}
            if isinstance(inp, str):
                try:
                    inp = json.loads(inp)
                except json.JSONDecodeError:
                    inp = {}
            questions = inp.get("questions", []) if isinstance(inp, dict) else []
            for q in questions:
                if isinstance(q, dict) and q.get("type") == "mcq" and not q.get("choices"):
                    q["choices"] = ["A) —", "B) —", "C) —", "D) —"]
            return questions if isinstance(questions, list) else []

    # Fallback: try extracting JSON array from text
    for block in response.content:
        if _attr(block, "type") == "text":
            text = _attr(block, "text") or ""
            m = re.search(r'\[.*\]', text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
    return []
