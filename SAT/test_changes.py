"""
Tests for recent SAT app changes:
  - Topic test history persistence (agent.py)
  - Weak-topic analysis (agent.py)
  - SAT score prediction (agent.py)
  - Difficulty prompt injection (topic_test.py)
  - Session-state defaults (app.py static check)
"""

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── Helpers ───────────────────────────────────────────────────────────────────

_MATH_SAMPLE = [
    {"topic": "Linear Equations & Inequalities", "domain": "Algebra",
     "correct": 7, "total": 10, "pct": 70, "taken_at": "2026-05-15T10:00:00"},
    {"topic": "Quadratics", "domain": "Advanced Math",
     "correct": 3, "total": 10, "pct": 30, "taken_at": "2026-05-16T10:00:00"},
    {"topic": "Statistics & Data Analysis", "domain": "Problem Solving & Data Analysis",
     "correct": 5, "total": 8,  "pct": 62, "taken_at": "2026-05-17T10:00:00"},
    {"topic": "Geometry", "domain": "Geometry & Trigonometry",
     "correct": 6, "total": 10, "pct": 60, "taken_at": "2026-05-18T10:00:00"},
]

_RW_SAMPLE = [
    {"topic": "Words in Context", "domain": "Craft & Structure",
     "correct": 8, "total": 10, "pct": 80, "taken_at": "2026-05-15T11:00:00"},
    {"topic": "Transitions", "domain": "Expression of Ideas",
     "correct": 4, "total": 10, "pct": 40, "taken_at": "2026-05-16T11:00:00"},
    {"topic": "Subject-Verb & Pronoun Agreement", "domain": "Standard English Conventions",
     "correct": 5, "total": 8,  "pct": 62, "taken_at": "2026-05-17T11:00:00"},
]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_cwd(tmp_path, monkeypatch):
    """Run each test in an isolated temp directory so JSON files don't collide."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════════
# agent.py — history persistence
# ═══════════════════════════════════════════════════════════════════════════════

class TestTopicHistory:
    def test_load_empty_when_no_file(self, tmp_cwd):
        from agent import load_topic_history
        assert load_topic_history("math") == []

    def test_save_and_reload(self, tmp_cwd):
        from agent import save_topic_result, load_topic_history
        save_topic_result("math", "Quadratics", "Advanced Math", 7, 10)
        history = load_topic_history("math")
        assert len(history) == 1
        r = history[0]
        assert r["topic"]   == "Quadratics"
        assert r["domain"]  == "Advanced Math"
        assert r["correct"] == 7
        assert r["total"]   == 10
        assert r["pct"]     == 70
        assert "taken_at" in r

    def test_pct_rounds_correctly(self, tmp_cwd):
        from agent import save_topic_result, load_topic_history
        save_topic_result("math", "Geometry", "Geometry & Trigonometry", 1, 3)
        r = load_topic_history("math")[0]
        assert r["pct"] == 33

    def test_multiple_results_accumulate(self, tmp_cwd):
        from agent import save_topic_result, load_topic_history
        save_topic_result("math", "Algebra Topic", "Algebra", 8, 10)
        save_topic_result("math", "Quadratics",    "Advanced Math", 5, 10)
        assert len(load_topic_history("math")) == 2

    def test_math_and_rw_files_are_separate(self, tmp_cwd):
        from agent import save_topic_result, load_topic_history
        save_topic_result("math",            "Quadratics",   "Advanced Math",  7, 10)
        save_topic_result("reading_writing", "Transitions",  "Expression of Ideas", 3, 10)
        assert len(load_topic_history("math"))            == 1
        assert len(load_topic_history("reading_writing")) == 1

    def test_zero_total_gives_zero_pct(self, tmp_cwd):
        from agent import save_topic_result, load_topic_history
        save_topic_result("math", "Empty", "Algebra", 0, 0)
        assert load_topic_history("math")[0]["pct"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# agent.py — weak topic analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalyzeTopicPerformance:
    def _write(self, tmp_cwd, subject, data):
        path = tmp_cwd / f"{subject}_topic_history.json"
        path.write_text(json.dumps(data))

    def test_weak_topics_below_70(self, tmp_cwd):
        from agent import analyze_topic_performance
        self._write(tmp_cwd, "math", _MATH_SAMPLE)
        result = analyze_topic_performance("math")
        weak = result["weak_topics"]
        # Quadratics=30%, Geometry=60%, Statistics=62% → all < 70
        assert "Quadratics" in weak
        assert "Geometry"   in weak
        assert "Statistics & Data Analysis" in weak
        # Linear Equations = 70% → NOT weak
        assert "Linear Equations & Inequalities" not in weak

    def test_weak_topics_sorted_ascending(self, tmp_cwd):
        from agent import analyze_topic_performance
        self._write(tmp_cwd, "math", _MATH_SAMPLE)
        weak = analyze_topic_performance("math")["weak_topics"]
        pcts = [analyze_topic_performance("math")["topic_stats"][t]["pct"] for t in weak]
        assert pcts == sorted(pcts)

    def test_domain_stats_aggregated(self, tmp_cwd):
        from agent import analyze_topic_performance
        # Two Algebra topics: 7/10 + 8/10 = 15/20 = 75%
        data = [
            {"topic": "Linear Eq", "domain": "Algebra", "correct": 7, "total": 10, "pct": 70, "taken_at": "2026-01-01"},
            {"topic": "Systems",   "domain": "Algebra", "correct": 8, "total": 10, "pct": 80, "taken_at": "2026-01-02"},
        ]
        self._write(tmp_cwd, "math", data)
        ds = analyze_topic_performance("math")["domain_stats"]
        assert ds["Algebra"]["correct"] == 15
        assert ds["Algebra"]["total"]   == 20
        assert ds["Algebra"]["pct"]     == 75

    def test_attempts_counted_per_topic(self, tmp_cwd):
        from agent import analyze_topic_performance
        data = [
            {"topic": "Quadratics", "domain": "Advanced Math", "correct": 3, "total": 10, "pct": 30, "taken_at": "2026-01-01"},
            {"topic": "Quadratics", "domain": "Advanced Math", "correct": 6, "total": 10, "pct": 60, "taken_at": "2026-01-02"},
        ]
        self._write(tmp_cwd, "math", data)
        ts = analyze_topic_performance("math")["topic_stats"]["Quadratics"]
        assert ts["attempts"] == 2
        assert ts["correct"]  == 9
        assert ts["total"]    == 20

    def test_no_history_returns_empty(self, tmp_cwd):
        from agent import analyze_topic_performance
        result = analyze_topic_performance("math")
        assert result["topic_stats"]  == {}
        assert result["domain_stats"] == {}
        assert result["weak_topics"]  == []

    def test_perfect_score_not_weak(self, tmp_cwd):
        from agent import analyze_topic_performance
        data = [{"topic": "Algebra Topic", "domain": "Algebra",
                 "correct": 10, "total": 10, "pct": 100, "taken_at": "2026-01-01"}]
        self._write(tmp_cwd, "math", data)
        assert analyze_topic_performance("math")["weak_topics"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# agent.py — score prediction
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictSatScore:
    def test_returns_none_for_empty_histories(self):
        from agent import predict_sat_score
        assert predict_sat_score([], []) == {}

    def test_only_math_history_returns_math_only(self):
        from agent import predict_sat_score
        result = predict_sat_score(_MATH_SAMPLE, [])
        assert "math_scaled" in result
        assert "rw_scaled"   not in result
        assert "total"       not in result

    def test_only_rw_history_returns_rw_only(self):
        from agent import predict_sat_score
        result = predict_sat_score([], _RW_SAMPLE)
        assert "rw_scaled"   in result
        assert "math_scaled" not in result
        assert "total"       not in result

    def test_both_histories_returns_total(self):
        from agent import predict_sat_score
        result = predict_sat_score(_MATH_SAMPLE, _RW_SAMPLE)
        assert "math_scaled" in result
        assert "rw_scaled"   in result
        assert "total"       in result
        assert result["total"] == result["math_scaled"] + result["rw_scaled"]

    def test_scores_in_valid_sat_range(self):
        from agent import predict_sat_score
        result = predict_sat_score(_MATH_SAMPLE, _RW_SAMPLE)
        assert 200 <= result["math_scaled"] <= 800
        assert 200 <= result["rw_scaled"]   <= 800
        assert 400 <= result["total"]       <= 1600

    def test_perfect_scores_give_800(self):
        from agent import predict_sat_score
        perfect_math = [
            {"topic": "t", "domain": "Algebra",                          "correct": 10, "total": 10},
            {"topic": "t", "domain": "Advanced Math",                    "correct": 10, "total": 10},
            {"topic": "t", "domain": "Problem Solving & Data Analysis",  "correct": 10, "total": 10},
            {"topic": "t", "domain": "Geometry & Trigonometry",          "correct": 10, "total": 10},
        ]
        result = predict_sat_score(perfect_math, [])
        assert result["math_scaled"] == 800

    def test_zero_scores_give_200(self):
        from agent import predict_sat_score
        zero_math = [
            {"topic": "t", "domain": "Algebra",                          "correct": 0, "total": 10},
            {"topic": "t", "domain": "Advanced Math",                    "correct": 0, "total": 10},
            {"topic": "t", "domain": "Problem Solving & Data Analysis",  "correct": 0, "total": 10},
            {"topic": "t", "domain": "Geometry & Trigonometry",          "correct": 0, "total": 10},
        ]
        result = predict_sat_score(zero_math, [])
        assert result["math_scaled"] == 200

    def test_higher_performance_gives_higher_score(self):
        from agent import predict_sat_score
        high = [{"topic": "t", "domain": "Algebra", "correct": 9, "total": 10}]
        low  = [{"topic": "t", "domain": "Algebra", "correct": 2, "total": 10}]
        assert predict_sat_score(high, [])["math_scaled"] > predict_sat_score(low, [])["math_scaled"]

    def test_unknown_domain_ignored(self):
        from agent import predict_sat_score
        # Domain not in weight table → treated as uncovered, result still valid
        data = [{"topic": "t", "domain": "Unknown Domain", "correct": 5, "total": 10}]
        result = predict_sat_score(data, [])
        assert result == {}  # no covered domains → no score


# ═══════════════════════════════════════════════════════════════════════════════
# topic_test.py — difficulty prompt injection
# ═══════════════════════════════════════════════════════════════════════════════

class TestDifficultyPrompt:
    _MATH_TOPIC = {
        "label": "Quadratics",
        "domain": "Advanced Math",
        "subtopics": "factoring, quadratic formula, completing the square",
        "ka_url": "https://example.com",
        "ka_label": "KA",
    }
    _RW_TOPIC = {
        "label": "Transitions",
        "domain": "Expression of Ideas",
        "subtopics": "choosing the correct transition word",
        "ka_url": "https://example.com",
        "ka_label": "KA",
    }

    def _prompt(self, subject, topic, n, difficulty):
        from topic_test import _build_prompt
        return _build_prompt(subject, topic, n, difficulty)

    def test_math_mixed_prompt_mentions_spread(self):
        p = self._prompt("math", self._MATH_TOPIC, 10, "mixed")
        assert "easy, medium, and hard" in p.lower() or "spread" in p.lower()

    def test_math_easy_prompt_contains_easy(self):
        p = self._prompt("math", self._MATH_TOPIC, 10, "easy")
        assert "easy" in p.lower()
        assert "hard" not in p.lower()

    def test_math_medium_prompt_contains_medium(self):
        p = self._prompt("math", self._MATH_TOPIC, 10, "medium")
        assert "medium" in p.lower()

    def test_math_hard_prompt_contains_hard(self):
        p = self._prompt("math", self._MATH_TOPIC, 10, "hard")
        assert "hard" in p.lower()

    def test_rw_easy_prompt_contains_easy(self):
        p = self._prompt("reading_writing", self._RW_TOPIC, 10, "easy")
        assert "easy" in p.lower()

    def test_rw_hard_prompt_contains_hard(self):
        p = self._prompt("reading_writing", self._RW_TOPIC, 10, "hard")
        assert "hard" in p.lower()

    def test_default_difficulty_is_mixed(self):
        from topic_test import _build_prompt
        p_default = _build_prompt("math", self._MATH_TOPIC, 10)
        p_mixed   = _build_prompt("math", self._MATH_TOPIC, 10, "mixed")
        assert p_default == p_mixed

    def test_all_difficulties_produce_different_prompts(self):
        diffs = ["mixed", "easy", "medium", "hard"]
        prompts = [self._prompt("math", self._MATH_TOPIC, 10, d) for d in diffs]
        assert len(set(prompts)) == 4

    def test_generate_topic_test_signature_accepts_difficulty(self):
        import inspect
        from topic_test import generate_topic_test
        sig = inspect.signature(generate_topic_test)
        assert "difficulty" in sig.parameters

    def test_math_spr_count_included_in_prompt(self):
        p = self._prompt("math", self._MATH_TOPIC, 10, "medium")
        # 10 questions → 2 SPR, 8 MCQ
        assert "multiple choice" in p.lower() or "mcq" in p.lower()
        assert "spr" in p.lower() or "grid-in" in p.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# app.py — static checks (no Streamlit runtime needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAppStaticChecks:
    def test_tt_defaults_include_difficulty(self):
        import ast, pathlib
        src = pathlib.Path(__file__).parent / "app.py"
        tree = ast.parse(src.read_text())
        # Find _TT_DEFAULTS dict assignment
        defaults = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "_TT_DEFAULTS":
                        if isinstance(node.value, ast.Dict):
                            for k, v in zip(node.value.keys, node.value.values):
                                if isinstance(k, ast.Constant):
                                    defaults[k.value] = ast.literal_eval(v)
        assert "tt_difficulty"   in defaults, "_TT_DEFAULTS missing tt_difficulty"
        assert "tt_result_saved" in defaults, "_TT_DEFAULTS missing tt_result_saved"
        assert defaults["tt_difficulty"]   == "mixed"
        assert defaults["tt_result_saved"] == False

    def test_new_agent_functions_importable(self):
        from agent import (
            load_topic_history,
            save_topic_result,
            analyze_topic_performance,
            predict_sat_score,
        )
        assert callable(load_topic_history)
        assert callable(save_topic_result)
        assert callable(analyze_topic_performance)
        assert callable(predict_sat_score)

    def test_app_imports_new_functions(self):
        import ast, pathlib
        src = pathlib.Path(__file__).parent / "app.py"
        tree = ast.parse(src.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "agent":
                for alias in node.names:
                    imported.add(alias.name)
        for fn in ("load_topic_history", "save_topic_result",
                   "analyze_topic_performance", "predict_sat_score"):
            assert fn in imported, f"app.py does not import {fn} from agent"

    def test_generate_topic_test_import_in_app(self):
        import ast, pathlib
        src = pathlib.Path(__file__).parent / "app.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "topic_test":
                names = {a.name for a in node.names}
                assert "generate_topic_test" in names
                return
        pytest.fail("generate_topic_test not imported from topic_test in app.py")
