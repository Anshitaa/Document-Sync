"""
eval.py — Automated evaluation suite for the Docu-Sync pipeline.

Runs the full detect → generate workflow against known test cases and
scores output quality across multiple dimensions.  Designed for:
  - Pre-deploy sanity checks
  - Regression testing after prompt changes
  - Demonstrating pipeline quality in a portfolio / interview setting

Usage:
    # From the services/api/ directory:
    python eval.py

    # Verbose mode (shows full API responses):
    python eval.py --verbose

    # Save results to JSON:
    python eval.py --output results.json

Requirements:
    - GEMINI_API_KEY set in .env or environment
    - Demo images present at ../../demo/
"""

import os
import sys
import json
import time
import argparse
import textwrap
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.parent
DEMO_DIR  = REPO_ROOT / "demo"

# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class Score:
    name: str
    value: float        # 0.0 – 1.0
    max_value: float = 1.0
    note: str = ""

    @property
    def pct(self) -> int:
        return round(self.value / self.max_value * 100)

    @property
    def grade(self) -> str:
        if self.pct >= 90: return "A"
        if self.pct >= 75: return "B"
        if self.pct >= 60: return "C"
        if self.pct >= 40: return "D"
        return "F"


@dataclass
class TestResult:
    test_name: str
    description: str
    passed: bool
    scores: list[Score] = field(default_factory=list)
    overall: float = 0.0
    duration_ms: float = 0.0
    error: str = ""
    detect_response: dict = field(default_factory=dict)
    generate_response: dict = field(default_factory=dict)

    @property
    def overall_pct(self) -> int:
        return round(self.overall * 100)

    @property
    def grade(self) -> str:
        if self.overall_pct >= 90: return "A"
        if self.overall_pct >= 75: return "B"
        if self.overall_pct >= 60: return "C"
        if self.overall_pct >= 40: return "D"
        return "F"


# ── Scoring helpers ────────────────────────────────────────────────────────────


def score_detect_response(data: dict, expect_change: bool) -> list[Score]:
    """Score a /detect-change response across 6 dimensions."""
    scores = []

    # 1. Required fields present
    required = ["ssim", "boxes", "semantic_summary", "changed_elements",
                "severity", "change_type", "ssim_summary"]
    present = sum(1 for f in required if f in data)
    scores.append(Score(
        "Required fields",
        present / len(required),
        note=f"{present}/{len(required)} fields present",
    ))

    # 2. SSIM is a valid float in [0, 1]
    ssim = data.get("ssim", -1)
    valid_ssim = isinstance(ssim, (int, float)) and 0 <= ssim <= 1
    scores.append(Score(
        "SSIM validity",
        1.0 if valid_ssim else 0.0,
        note=f"ssim={ssim:.4f}" if valid_ssim else f"invalid ssim={ssim}",
    ))

    # 3. Semantic summary is substantive (> 30 chars)
    summary = data.get("semantic_summary", "")
    sem_score = min(1.0, len(summary) / 60) if summary else 0.0
    scores.append(Score(
        "Semantic summary quality",
        sem_score,
        note=f"{len(summary)} chars",
    ))

    # 4. Changed elements are specific (each element > 15 chars avg)
    elements = data.get("changed_elements", [])
    if elements:
        avg_len = sum(len(e) for e in elements) / len(elements)
        elem_score = min(1.0, avg_len / 30)
        note = f"{len(elements)} elements, avg {avg_len:.0f} chars"
    elif not expect_change:
        elem_score = 1.0
        note = "no changes expected, empty list OK"
    else:
        elem_score = 0.0
        note = "expected elements but got none"
    scores.append(Score("Changed elements specificity", elem_score, note=note))

    # 5. Severity is a valid enum value
    valid_severities = {"minor", "moderate", "significant"}
    severity = data.get("severity", "")
    scores.append(Score(
        "Severity validity",
        1.0 if severity in valid_severities else 0.0,
        note=f"severity='{severity}'",
    ))

    # 6. Change type is a valid enum value
    valid_types = {"layout", "color", "text", "component_added", "component_removed", "mixed"}
    change_type = data.get("change_type", "")
    scores.append(Score(
        "Change type validity",
        1.0 if change_type in valid_types else 0.0,
        note=f"change_type='{change_type}'",
    ))

    return scores


def score_generate_response(data: dict) -> list[Score]:
    """Score a /generate-update response across 5 dimensions."""
    scores = []

    # 1. Required fields present
    required = ["documentation", "confidence", "reasoning", "rag_chunks_used"]
    present = sum(1 for f in required if f in data)
    scores.append(Score(
        "Required fields",
        present / len(required),
        note=f"{present}/{len(required)} fields present",
    ))

    # 2. Documentation quality: length 40–400 chars, penalise too short or cut off
    doc = data.get("documentation", data.get("new_text", ""))
    if len(doc) >= 40:
        doc_score = min(1.0, len(doc) / 150)
    else:
        doc_score = len(doc) / 40
    scores.append(Score(
        "Documentation quality",
        doc_score,
        note=f"{len(doc)} chars",
    ))

    # 3. Confidence is a valid float in [0, 1]
    conf = data.get("confidence", -1)
    valid_conf = isinstance(conf, (int, float)) and 0 <= conf <= 1
    scores.append(Score(
        "Confidence validity",
        1.0 if valid_conf else 0.0,
        note=f"confidence={conf:.2f}" if valid_conf else f"invalid={conf}",
    ))

    # 4. Reasoning is substantive (> 40 chars)
    reasoning = data.get("reasoning", "")
    reason_score = min(1.0, len(reasoning) / 80) if reasoning else 0.0
    scores.append(Score(
        "Reasoning quality",
        reason_score,
        note=f"{len(reasoning)} chars",
    ))

    # 5. RAG was used (chunks_used > 0 when readme was provided)
    rag_used = data.get("rag_chunks_used", 0)
    scores.append(Score(
        "RAG utilisation",
        1.0 if rag_used > 0 else 0.5,
        note=f"{rag_used} chunk(s) retrieved",
    ))

    return scores


def compute_overall(scores: list[Score]) -> float:
    if not scores:
        return 0.0
    return sum(s.value for s in scores) / len(scores)


# ── Test runner ────────────────────────────────────────────────────────────────


def run_test(
    test_name: str,
    description: str,
    old_image_path: Path,
    new_image_path: Path,
    readme: str = "",
    expect_change: bool = True,
    verbose: bool = False,
) -> TestResult:
    """Run a single detect → generate test case and return scored results."""

    print(f"\n  Running: {test_name}...", end=" ", flush=True)
    t0 = time.time()

    # Import here so missing keys fail at test time, not import time
    from diff import compute_ssim_and_mask, summarize_change
    from llm_client import analyze_visual_changes, generate_documentation

    result = TestResult(test_name=test_name, description=description, passed=False)

    try:
        # Load images
        old_bytes = old_image_path.read_bytes()
        new_bytes = new_image_path.read_bytes()

        # ── Step 1: Detect ─────────────────────────────────────────────────
        ssim_score, boxes, _, _ = compute_ssim_and_mask(old_bytes, new_bytes)
        ssim_summary = summarize_change(ssim_score, boxes)
        vision = analyze_visual_changes(old_bytes, new_bytes)

        detect_data = {
            "ssim": float(ssim_score),
            "boxes": boxes,
            "ssim_summary": ssim_summary,
            "semantic_summary": vision.get("semantic_summary", ""),
            "changed_elements": vision.get("changed_elements", []),
            "change_type": vision.get("change_type", "mixed"),
            "severity": vision.get("severity", "moderate"),
            "summary": vision.get("semantic_summary", ssim_summary),
        }
        result.detect_response = detect_data

        # ── Step 2: Generate ───────────────────────────────────────────────
        change_summary = detect_data["summary"]
        gen_data = generate_documentation(change_summary, readme)
        gen_data["new_text"] = gen_data.get("documentation", "")
        result.generate_response = gen_data

        # ── Score ──────────────────────────────────────────────────────────
        detect_scores  = score_detect_response(detect_data, expect_change)
        generate_scores = score_generate_response(gen_data)

        result.scores = detect_scores + generate_scores
        result.overall = compute_overall(result.scores)
        result.passed = result.overall >= 0.65
        result.duration_ms = (time.time() - t0) * 1000

        status = "✓" if result.passed else "✗"
        print(f"{status}  ({result.overall_pct}%  grade {result.grade}  {result.duration_ms:.0f}ms)")

    except Exception as e:
        result.error = str(e)
        result.duration_ms = (time.time() - t0) * 1000
        print(f"✗  ERROR: {e}")

    if verbose and not result.error:
        print(f"\n     Detect:   {json.dumps(result.detect_response, indent=6)}")
        print(f"\n     Generate: {json.dumps(result.generate_response, indent=6)}")

    return result


# ── Report printer ─────────────────────────────────────────────────────────────


def print_report(results: list[TestResult]) -> None:
    W = 68
    print("\n" + "═" * W)
    print("  DOCU-SYNC EVAL REPORT".center(W))
    print("═" * W)

    for r in results:
        status = "PASS" if r.passed else ("ERROR" if r.error else "FAIL")
        color  = "\033[92m" if r.passed else "\033[91m"
        reset  = "\033[0m"
        print(f"\n  {color}[{status}]{reset}  {r.test_name}  ({r.overall_pct}% · {r.grade}  {r.duration_ms:.0f}ms)")
        print(f"         {r.description}")

        if r.error:
            print(f"\n         ⚠ {r.error}")
            continue

        # Score breakdown
        col_w = 30
        for s in r.scores:
            bar_filled = round(s.pct / 5)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            grade_col = "\033[92m" if s.pct >= 75 else ("\033[93m" if s.pct >= 50 else "\033[91m")
            print(f"    {s.name:<{col_w}} {grade_col}{bar}{reset} {s.pct:3d}%  {s.note}")

    # Overall summary
    passing = [r for r in results if r.passed]
    total = len(results)
    avg = sum(r.overall for r in results if not r.error) / max(len([r for r in results if not r.error]), 1)

    print("\n" + "─" * W)
    print(f"  Tests: {len(passing)}/{total} passed   Avg score: {avg*100:.1f}%")

    if avg >= 0.85:
        verdict = "\033[92m🟢 Pipeline is performing excellently\033[0m"
    elif avg >= 0.70:
        verdict = "\033[93m🟡 Pipeline is performing acceptably — review low-scoring dimensions\033[0m"
    else:
        verdict = "\033[91m🔴 Pipeline needs attention — check API keys and prompts\033[0m"
    print(f"  {verdict}")
    print("═" * W + "\n")


# ── Main ───────────────────────────────────────────────────────────────────────


def build_test_cases() -> list[dict]:
    """Define the eval test suite."""
    before = DEMO_DIR / "demo_before.png"
    after  = DEMO_DIR / "demo_after.png"

    sample_readme = textwrap.dedent("""
        # MyApp Documentation

        ## UI Components
        Our app features a blue submit button in the main form. The navigation
        bar uses a dark theme with white text. The dashboard displays a sidebar
        on the left with user settings.

        ## Getting Started
        Install the app and run `npm start`. The default port is 3000.

        ## Changelog
        See CHANGELOG.md for version history.

        ## Contributing
        PRs are welcome. Please follow the existing code style.
    """).strip()

    return [
        {
            "test_name": "Identical images — no change",
            "description": "Expect minimal SSIM diff, 'minor' severity, and stable documentation",
            "old": before,
            "new": before,           # same image — should detect no change
            "readme": sample_readme,
            "expect_change": False,
        },
        {
            "test_name": "Demo before → after (UI change)",
            "description": "Primary test: real before/after screenshots from the demo folder",
            "old": before,
            "new": after,
            "readme": sample_readme,
            "expect_change": True,
        },
        {
            "test_name": "Demo after → before (reversed)",
            "description": "Reverse direction — verifies the pipeline handles either order",
            "old": after,
            "new": before,
            "readme": "",            # no README — tests fallback gracefully
            "expect_change": True,
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Docu-Sync evaluation suite")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print full API responses for each test")
    parser.add_argument("--output", "-o", metavar="FILE",
                        help="Save results to a JSON file")
    parser.add_argument("--test", "-t", metavar="NAME",
                        help="Run only tests whose name contains NAME (case-insensitive)")
    args = parser.parse_args()

    # Check API key early
    if not os.getenv("GEMINI_API_KEY"):
        print("\n⚠  GEMINI_API_KEY not set — set it in services/api/.env before running eval.\n")
        sys.exit(1)

    # Check demo images exist
    before = DEMO_DIR / "demo_before.png"
    after  = DEMO_DIR / "demo_after.png"
    if not before.exists() or not after.exists():
        print(f"\n⚠  Demo images not found in {DEMO_DIR}\n"
              f"   Expected: demo_before.png and demo_after.png\n")
        sys.exit(1)

    print("\n" + "─" * 68)
    print("  Docu-Sync Evaluation Suite")
    print("─" * 68)
    print(f"  Demo images : {DEMO_DIR}")
    print(f"  Model       : gemini-1.5-flash-latest + text-embedding-004")

    test_cases = build_test_cases()
    if args.test:
        test_cases = [t for t in test_cases if args.test.lower() in t["test_name"].lower()]
        if not test_cases:
            print(f"\n⚠  No tests matched '{args.test}'\n")
            sys.exit(1)

    print(f"  Running {len(test_cases)} test(s)...\n")

    results = []
    for tc in test_cases:
        r = run_test(
            test_name=tc["test_name"],
            description=tc["description"],
            old_image_path=tc["old"],
            new_image_path=tc["new"],
            readme=tc.get("readme", ""),
            expect_change=tc.get("expect_change", True),
            verbose=args.verbose,
        )
        results.append(r)

    print_report(results)

    if args.output:
        out = [
            {
                "test_name": r.test_name,
                "passed": r.passed,
                "overall_pct": r.overall_pct,
                "grade": r.grade,
                "duration_ms": r.duration_ms,
                "error": r.error,
                "scores": [{"name": s.name, "pct": s.pct, "note": s.note} for s in r.scores],
                "detect_response": r.detect_response,
                "generate_response": r.generate_response,
            }
            for r in results
        ]
        Path(args.output).write_text(json.dumps(out, indent=2))
        print(f"  Results saved to {args.output}\n")

    # Exit code: 0 if all passed, 1 otherwise
    sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
