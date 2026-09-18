# Data and artifact reference

[Project overview](../README.md) · [Reproduction guide](../docs/reproduction.md)

MEMAUDIT releases the synthetic **50-user pooled-final benchmark** and the
artifacts needed to trace each result back to a conversation and memory record.
See the [project overview](../README.md) for the paper and citation.

## Benchmark composition

| Component | Released scope |
| --- | --- |
| Synthetic users | 50, identified as `user_001` through `user_050` |
| Hidden state per user | 31 entries across five categories |
| Assistance tasks | 31 per user; 1,550 total |
| Interaction runs | Five systems, each with 50 users and 1,550 episodes |
| Reconstruction settings | Dump-all for all five systems; native retrieval for the four memory systems |

Each user's hidden bank contains 7 skill, 7 knowledge, 7 episodic, 5 self-model,
and 5 assistance-preference entries. Dimensions are selected from a pool: the
31 dimension names are not necessarily identical across users.

| Category key | What the reference describes | Entries per user |
| --- | --- | ---: |
| `skill_memory` | What the user can do, including proficiency limits | 7 |
| `knowledge_memory` | What the user knows or misunderstands about the external world | 7 |
| `episodic_memory` | Past events that shape current judgments | 7 |
| `self_model` | The user's beliefs about their own abilities, identity, and traits | 5 |
| `assistance_preference` | How the user prefers to receive assistance | 5 |

The release is an evaluation artifact, not a predefined train/validation/test
split. User IDs are synthetic identifiers, not real-person identifiers.

## Artifact layout

```text
Deeppersona/data/user_memory_banks_pooled_final.json   Hidden reference banks
benchmark_data/CustomTasksPooledFinal/user_*.json    Accepted task pool
history/<run-id>/user_*/episode_*.json               Interaction transcripts
memory/<run-id>/user_*/memories.json                 Final stored memory
pref_judge/<run-id>/user_*/episode_*.json             Per-turn preference judgments
output/<run-id>/*.json                              Aggregate and per-user reports
output/<run-id>/recon_judge/user_*.json              Recovered slots and judge records
output/<run-id>/attribution/user_*.json              Staged failure attribution
output/_task_design_oracle/user_*.json               Shared task-design judgments
```

The interaction run IDs are `nomem_pooled_50`, `amem_pooled_50`,
`longctx_full_pooled_50`, `mem0_pooled_50`, and `memt_memonly_pooled_50`.
The four memory-system runs also have an `output/<run-id>_retrieve/` directory.
Those directories contain a second reconstruction setting for the same
interactions, not additional conversation runs. Their transcripts and memory
dumps live under the corresponding base run ID.

Some systems also save native vector-store state under
`memory/<run-id>/user_*/raw/`. This is implementation-specific and is not a
portable common schema. Heavy Mem-T raw workspaces are excluded from the
release; the final JSON memory dumps remain available.

## JSON records and joins

### Hidden user banks

The [bank file](../Deeppersona/data/user_memory_banks_pooled_final.json) has
top-level fields `generated_at`, `source`, `num_users`, and `users`. Each user
contains:

| Field | Meaning |
| --- | --- |
| `user_id` | Join key shared by tasks and evaluation artifacts |
| `base_profile` | Synthetic background: demographic, career, values, life-story, and interest fields |
| `memory_bank` | A dictionary of the five categories listed above |
| `memory_bank[category][].dimension` | The dimension being evaluated |
| `memory_bank[category][].short` | The reference value to recover |
| `memory_bank[category][].explanation` | User-specific explanation of that reference value |

Use `(user_id, category, dimension)` to identify a reference entry. Category
definitions distinguish, for example, actual skill from the user's possibly
inaccurate self-assessment.

### Tasks and episodes

Each [task file](../benchmark_data/CustomTasksPooledFinal/user_001.json) contains
`user_id`, `generated_at`, `n_tasks`, and a `tasks` array. A task record includes
`task`, `rationale`, `target_category`, `target_dimension`, `target_short`, and
`pipeline_note`.

`task` is the actual assistance request. The other fields document how the
task was designed and which hidden entry it targets. The runner loads only
`task` as agent-facing task text, with no answer ground truth for task completion.
It runs tasks in array order: the first task corresponds to `episode_1.json`,
the second to `episode_2.json`, and so on. There is no separate task-ID field.
Keep task ordering unchanged when joining transcripts to task metadata.

A [transcript](../history/amem_pooled_50/user_001/episode_1.json) stores `user_id`,
`task`, `ground_truth`, `end_reason`, `final_preference_score`, and `turns`.
Each turn records the assistant response, simulator feedback, and preference
score. `ground_truth` is `null` for these custom assistance tasks; hidden-state
reference answers live in the user bank and reconstruction records instead.

The corresponding [preference-judge file](../pref_judge/amem_pooled_50/user_001/episode_1.json)
stores the preference references and the per-preference reasons and scores for
each assistant turn. Join it to the transcript by run ID, user ID, and episode
number.

### Stored memory and reconstruction

A [memory dump](../memory/amem_pooled_50/user_001/memories.json) contains
`num_memories` and a `memories` array. Records share a `content` field; additional
IDs, tags, categories, metadata, and timestamps depend on the system. The
no-memory baseline has an empty memory list. Memory is collected after all
tasks for that user, rather than as a separate dump per episode.

A [reconstruction record](../output/amem_pooled_50/recon_judge/user_001.json)
contains `user_id`, `per_category`, `overall`, and `details`. Each detail has
`category`, `dimension`, `explanation`, `ground_truth`, `predicted`,
`slot_fill_reason`, `score`, `judge_reason`, and `scoring_mode`.
[Retrieve-mode records](../output/amem_pooled_50_retrieve/recon_judge/user_001.json)
also include `retrieved_memories`, the actual evidence supplied to the slot
filler for that dimension.

### Failure attribution

An [attribution record](../output/amem_pooled_50/attribution/user_001.json)
contains `user_id`, `tasks_dir`, `counts`, and the reconstruction details with an
added `attribution` object. That object records a label, score, intermediate
stages, and, where applicable, the targeted episode index.

The implemented labels are `ok`, `memory_failure`, `task_design_failure`,
`agent_elicitation_failure`, `simulator_too_strict`, and `no_targeted_task`
(with `unclassified` as a fallback). Scores of at least `0.75` receive `ok`.
For lower scores, a cached oracle first checks whether the task could invite
the target information, then dialogue judgments examine disclosure and
elicitation. `memory_failure` groups failures after disclosure; it does not
separately establish a write-side or read-side cause. These labels are
model-assisted diagnostics, not verified causal annotations.

## Scores and aggregation

[scorer.py](../scorer.py) defines the released metrics:

| Report key | Definition |
| --- | --- |
| `A_task_completion_rate` | Fraction of episodes ending with simulator satisfaction within the turn budget |
| `B_reconstruction` | Reference-match judgments on the scale `0`, `0.25`, `0.5`, `0.75`, `1` |
| `C_avg_turns_all` | Mean interaction length across all of a user's episodes |
| `C_avg_turns_satisfied` | Mean interaction length restricted to satisfied episodes |
| `D_preference_score` | Mean of available turn-level preference scores, on a 1–5 scale |
| `E_memory_footprint` | Number of memory records and mean characters per memory record |

Reconstruction scores are averaged within each category; a user's overall
reconstruction score is the mean of the five category means. Thus, the overall
score is a category macro-average, not a flat average of all 31 entries.
Benchmark reports then aggregate user-level scores and include means and
sample standard deviations. Memory footprint uses characters, not token counts.

Report files contain `num_users`, `per_user`, and `aggregate`. Intermediate
reports may cover fewer users; use a report with `num_users: 50` when reproducing
the full released comparison. Task completion measures simulated satisfaction
and should not be read as an independent correctness judgment.

## Preserve the evaluation boundary

The hidden bank is published so researchers can inspect the synthetic reference
state and run the simulator and evaluator. It is **not an input to the evaluated
assistant or its memory system**. Giving the assistant `base_profile`, reference
values, or task-design metadata would bypass the recovery problem.

In the released implementation:

- The simulator receives the hidden profile and bank. The evaluated assistant
  receives the task, conversational feedback, and evidence from its own memory.
- Task `rationale`, `target_short`, and other design metadata are excluded from
  the task text passed to the assistant.
- The reconstruction slot filler receives memory evidence, the dimension name,
  and a generic category definition. It does not receive the user's reference
  value or user-specific explanation.
- The reconstruction judge receives the prediction and hidden reference only
  after slot filling. Retrieve queries likewise exclude reference values and
  user-specific explanations.

The exported reconstruction and attribution JSON files contain reference values
for audit. Treat them as evaluation outputs, not extra memory available to a
new agent. Preserve this separation when adapting the benchmark to another
runner or dataset host.

## Provenance and licenses

The profiles, hidden banks, assistance tasks, and run artifacts are synthetic
benchmark material produced for this study. Persona-generation utilities are
provided under [Deeppersona/](../Deeppersona/), and the benchmark draws on external
resources including DeepPersona and O*NET. The pool selection is recorded in the
bank's `source` field. Inspect the generation utilities and paper for the
construction procedure.

The repository's top-level [LICENSE](../LICENSE) releases MEMAUDIT code and
generated benchmark artifacts under **CC BY 4.0**. Vendored A-Mem code retains
its [MIT License](../A-mem-sys/LICENSE); vendored Mem-T code retains its
[Apache License 2.0](../Mem-T/LICENSE). DeepPersona, O*NET, Mem0, OpenAI/API
services, Hugging Face model hosting, and other third-party datasets,
taxonomies, packages, model weights, and hosted services remain subject to
their respective licenses, model cards, acceptable-use policies, and terms.
The benchmark release does not grant additional rights to those upstream
resources. Mem-T model weights are not included; users obtain them upstream
under the corresponding model-card terms. The release includes benchmark
artifacts generated for this study, not an additional distribution of
third-party weights or unrelated proprietary service outputs.

When redistributing the benchmark, preserve attribution, the license, the
synthetic-data description, and the distinction between hidden evaluation
references and agent-visible inputs.
