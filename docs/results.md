# Released results

This page summarizes the archived 50-user release. Each number below is read
from the released aggregate reports and checked against their per-user records.
These results use the simulator preserved on the
[`paper-v1` branch](https://github.com/sora1998/MEMAUDIT-bench/tree/paper-v1);
they are not measurements of the updated simulator on `main`.

## Results at a glance

<!-- BEGIN GENERATED RELEASE TABLE -->

| System | Users | Task completion (%) | Full-store recovery | Top-5 recovery |
| :-- | --: | --: | --: | --: |
| No memory | 50 | 99.935 | [0.000 ± 0.000](../output/nomem_pooled_50/nomem_20260501_030243_merged.json) | — |
| A-Mem | 50 | 99.935 | [0.611 ± 0.062](../output/amem_pooled_50/amem_20260501_030245_merged.json) | [0.540 ± 0.062](../output/amem_pooled_50_retrieve/amem_20260501_030245_merged.json) |
| Long context | 50 | 99.935 | [0.624 ± 0.067](../output/longctx_full_pooled_50/longctx_full_20260501_030246_merged.json) | [0.503 ± 0.075](../output/longctx_full_pooled_50_retrieve/longctx_full_20260501_030246_merged.json) |
| Mem0 | 50 | 99.871 | [0.613 ± 0.060](../output/mem0_pooled_50/mem0_20260501_030248_merged.json) | [0.473 ± 0.079](../output/mem0_pooled_50_retrieve/mem0_20260501_030248_merged.json) |
| Mem-T (memory-only) | 50 | 99.935 | [0.131 ± 0.251](../output/memt_memonly_pooled_50/memt_memonly_20260502_002256_merged.json) † | [0.465 ± 0.057](../output/memt_memonly_pooled_50_retrieve/memt_memonly_20260502_002256_merged.json) |

Recovery is category-balanced on a 0–1 scale; ± is the sample standard deviation across users.
Each linked recovery score points to its archived JSON report. These are release results, not new experiments.

† Mem-T full-store recovery is a context-overflow diagnostic and is not directly comparable to the context-fit full-store results.
The no-memory release has no retrieve-mode report; — means not reported.

<!-- END GENERATED RELEASE TABLE -->

The release illustrates why task completion and memory recovery need separate
measurements: the no-memory baseline completes 99.935% of tasks while recovering
none of the hidden user state. A-Mem, long context, and Mem0 all have lower
recovery through retrieval than through a full-store read. These are descriptive
comparisons of the archived runs; the table does not establish statistical
significance or performance on real users.

## What the numbers measure

The [hidden banks](../Deeppersona/data/user_memory_banks_pooled_final.json)
contain 50 synthetic users with 31 targets each: 7 skill, 7 knowledge,
7 episodic, 5 self-model, and 5 assistance-preference dimensions. Each user has
[31 assistance tasks](../benchmark_data/CustomTasksPooledFinal/), for 1,550 tasks
per system and 1,550 recovery targets per access mode.

The implementation is in [scorer.py](../scorer.py):

| Metric | Definition and denominator |
| :-- | :-- |
| Task completion, A | For each user, satisfied episodes / all 31 episodes; then the mean over 50 users, multiplied by 100. Satisfaction is the simulator's stopping signal, not an independently verified correctness label. |
| Recovery, B | Each target receives a semantic judge score in {0, 0.25, 0.5, 0.75, 1}. Scores are averaged within each category, the five categories receive equal weight, and user scores are averaged over 50 users. This is not an exact-match percentage or a flat mean over 1,550 targets. |
| Turns, C | Mean number of turns per episode for each user, then a mean over users. `C_avg_turns_all` includes unsatisfied episodes; `C_avg_turns_satisfied` includes only satisfied episodes within each user. |
| Preference, D | A 1–5 score averaged over scorable preferences within a turn, then over scored turns within each user, then over users. Unscorable turns are omitted; this is not a percentage. See also the [preference evaluator](../simulation.py). |
| Footprint, E | `num_memories` is the number of stored items per user. `avg_memory_chars` is each user's mean character count of item `content`; both are then averaged over users. Characters are not tokens, bytes, total serialized size, or API cost. |

The ± values are sample standard deviations across the 50 user scores. They are
not confidence intervals and do not quantify variation across repeated runs.

## Comparing the two access modes

`dump_all` passes the complete serialized memory store to the reconstruction
reader. `retrieve` asks the system's `search(query, k=5)` interface for evidence
for each target. The query contains a dimension name and a category guide; it
does not contain the user's ground-truth value or explanation.

The two reports for a system share its completed interaction trajectory and
non-recovery metrics. They change the memory access used for reconstruction,
not the preceding assistance tasks. A top-5 item limit does not equalize token
budgets across systems, because their item sizes and representations differ.
Full-store access is not a guaranteed upper bound when the reader cannot fit
the store in its context.

For Mem-T, the release uses `memt_memonly`: Mem-T memory operations with a shared
assistant backbone for the final response. The [paper, Table 2 and Appendix
I](https://arxiv.org/html/2606.24595v1#S4.T2) identifies its full-store score as a
context-overflow diagnostic. The archived full-store report contains 39 users
with zero overall recovery. Those values are preserved, not dropped or replaced
by successful-user averages. The exact stored mean is `0.13054285714285715`,
which rounds to `0.131` here; Table 2 prints `0.130`.

## Reproduce this summary offline

From the repository root, using Python 3.10 or later:

```bash
python scripts/summarize_results.py
```

No package installation, API key, GPU, or model call is required. To generate
the source links used on this page:

```bash
python scripts/summarize_results.py --link-prefix ../
```

The [script](../scripts/summarize_results.py) has an explicit manifest of nine
release aggregate paths. It verifies all 50 user IDs, recomputes the displayed
means and standard deviations from the user rows, and checks that paired
access-mode reports have identical non-recovery user metrics. It fails if the
expected reports are incomplete or inconsistent, and never writes to them.

The earlier `memt_memonly_20260501_174720_merged.json` files contain 49 users and
are excluded. The selected Mem-T reports are dated `20260502_002256`. Unrelated
reports and future reruns are also excluded rather than silently mixed into the
release summary. This check verifies aggregate consistency; it does not rerun
the LLM judges or independently revalidate their semantic judgments.
