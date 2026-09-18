#!/usr/bin/env python3
"""Validate and summarize the nine archived 50-user release reports offline.

Uses only the Python standard library. No models, API calls, or output writes.
The explicit manifest excludes earlier 49-user Mem-T reports and later reruns.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, stdev
import sys


# These are the final 50-user release aggregates, not a glob of output/.
RELEASE_REPORTS = {
    "No memory": {
        "dump_all": "output/nomem_pooled_50/nomem_20260501_030243_merged.json",
    },
    "A-Mem": {
        "dump_all": "output/amem_pooled_50/amem_20260501_030245_merged.json",
        "retrieve": "output/amem_pooled_50_retrieve/amem_20260501_030245_merged.json",
    },
    "Long context": {
        "dump_all": "output/longctx_full_pooled_50/longctx_full_20260501_030246_merged.json",
        "retrieve": "output/longctx_full_pooled_50_retrieve/longctx_full_20260501_030246_merged.json",
    },
    "Mem0": {
        "dump_all": "output/mem0_pooled_50/mem0_20260501_030248_merged.json",
        "retrieve": "output/mem0_pooled_50_retrieve/mem0_20260501_030248_merged.json",
    },
    "Mem-T (memory-only)": {
        "dump_all": "output/memt_memonly_pooled_50/memt_memonly_20260502_002256_merged.json",
        "retrieve": "output/memt_memonly_pooled_50_retrieve/memt_memonly_20260502_002256_merged.json",
    },
}
EXPECTED_USERS = {f"user_{i:03d}" for i in range(1, 51)}
CATEGORIES = (
    "skill_memory", "knowledge_memory", "episodic_memory", "self_model",
    "assistance_preference", "overall",
)


def check_summary(values: list[float], summary: dict, label: str) -> None:
    """Check stored means and sample standard deviations against user rows."""
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        raise ValueError(f"{label}: missing or non-finite per-user values")
    expected = {"mean": mean(values), "std": stdev(values)}
    for stat, value in expected.items():
        stored = summary[stat]
        if not isinstance(stored, (int, float)) or not math.isclose(
            stored, value, rel_tol=1e-10, abs_tol=1e-12
        ):
            raise ValueError(f"{label}: stored {stat} does not match user rows")


def read_report(repo_root: Path, relative_path: str) -> dict:
    with (repo_root / relative_path).open(encoding="utf-8") as handle:
        report = json.load(handle)
    users = report["per_user"]
    if (
        report["num_users"] != 50 or len(users) != 50
        or {user["user_id"] for user in users} != EXPECTED_USERS
    ):
        raise ValueError(f"{relative_path}: expected exactly user_001 through user_050")
    aggregate = report["aggregate"]
    for field, metric in (
        ("task_completion_rate", "A_task_completion_rate"),
        ("avg_turns_all", "C_avg_turns_all"),
        ("avg_preference_score", "D_preference_score"),
    ):
        check_summary([u[field] for u in users], aggregate[metric], relative_path + ": " + metric)
    for category in CATEGORIES:
        reconstruction = aggregate["B_reconstruction"]
        check_summary(
            [u["reconstruction"][category] for u in users],
            {stat: reconstruction[stat][category] for stat in ("mean", "std")},
            relative_path + ": reconstruction " + category,
        )
    for field in ("num_memories", "avg_memory_chars"):
        check_summary(
            [u[field] for u in users], aggregate["E_memory_footprint"][field],
            relative_path + ": " + field,
        )
    return report


def read_release(repo_root: Path) -> dict:
    reports = {}
    for system, modes in RELEASE_REPORTS.items():
        reports[system] = {
            mode: read_report(repo_root, path) for mode, path in modes.items()
        }
        # Scoring modes reuse an interaction trajectory; only recovery changes.
        if "retrieve" in reports[system]:
            shared = []
            for mode in ("dump_all", "retrieve"):
                shared.append({
                    u["user_id"]: {k: v for k, v in u.items() if k != "reconstruction"}
                    for u in reports[system][mode]["per_user"]
                })
            if shared[0] != shared[1]:
                raise ValueError(f"{system}: non-recovery user metrics differ between modes")
    return reports


def render_table(reports: dict, link_prefix: str) -> str:
    lines = [
        "| System | Users | Task completion (%) | Full-store recovery | Top-5 recovery |",
        "| :-- | --: | --: | --: | --: |",
    ]
    for system, modes in reports.items():
        aggregate = modes["dump_all"]["aggregate"]
        scores = []
        for mode in ("dump_all", "retrieve"):
            if mode not in modes:
                scores.append("—")
                continue
            reconstruction = modes[mode]["aggregate"]["B_reconstruction"]
            value = f"{reconstruction['mean']['overall']:.3f} ± {reconstruction['std']['overall']:.3f}"
            source = link_prefix + RELEASE_REPORTS[system][mode]
            score = f"[{value}]({source})"
            if system == "Mem-T (memory-only)" and mode == "dump_all":
                score += " †"
            scores.append(score)
        completion = 100 * aggregate["A_task_completion_rate"]["mean"]
        lines.append(f"| {system} | 50 | {completion:.3f} | {scores[0]} | {scores[1]} |")
    lines.extend([
        "",
        "Recovery is category-balanced on a 0–1 scale; ± is the sample standard deviation across users.",
        "Each linked recovery score points to its archived JSON report. These are release results, not new experiments.",
        "",
        "† Mem-T full-store recovery is a context-overflow diagnostic and is not directly comparable to the context-fit full-store results.",
        "The no-memory release has no retrieve-mode report; — means not reported.",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    parser.add_argument(
        "--link-prefix", default="",
        help="prefix for Markdown source links, e.g. ../ when embedding in docs/",
    )
    args = parser.parse_args()
    try:
        reports = read_release(args.repo_root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot summarize the complete 50-user release: {exc}", file=sys.stderr)
        return 1
    print(render_table(reports, args.link_prefix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
