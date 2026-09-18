# Reproducing MemAudit

[Project overview](../README.md) · [Data and artifact reference](../docs/data.md)

The release supports two workflows: inspect the saved evidence locally, or rerun
the interactions and evaluation with model access. All commands below run from
the repository root.

## 1. Inspect the release without model calls

```bash
git clone https://github.com/sora1998/MEMAUDIT-bench.git
cd MEMAUDIT-bench
```

Reading the released JSON files requires neither an API key nor the benchmark's
Python dependencies. For example, this standard-library-only command prints one
user's saved reconstruction scores:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path("output/amem_pooled_50/recon_judge/user_001.json")
record = json.loads(path.read_text())
print("User:", record["user_id"])
print("Overall reconstruction:", record["overall"])
for category, score in record["per_category"].items():
    print(f"  {category}: {score:.4f}")
PY
```

Start with the [artifact map](../docs/data.md#artifact-layout) to follow a task
through its transcript, stored memory, recovered state, and attribution. Aggregate
reports include a `num_users` field: select a report with `num_users: 50` for the
full benchmark, since some directories also retain intermediate reports.

## 2. Install the rerun environment

The recorded environment uses **Linux and Python 3.10**. API-based runs require
OpenAI access; Mem-T additionally requires a local model server and suitable GPU
resources.

```bash
conda create -n memaudit python=3.10
conda activate memaudit
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Alternatively, use `conda env create -f environment.yml`, then
`conda activate memaudit`. [requirements.txt](../requirements.txt) is a full
`pip freeze` snapshot, including the benchmark, A-Mem, Mem0, vector stores, and
Mem-T/vLLM packages. [environment.yml](../environment.yml) records the same
environment without a machine-local `prefix`. These are reference-environment
snapshots, not a minimal CPU-only dependency list.

The wrappers add the vendored [A-Mem](../A-mem-sys/) and [Mem-T](../Mem-T/) code
to `sys.path`; neither folder needs an editable install.

Set the API key in the shell used for reruns:

```bash
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

The shared default model is `GPT_MODEL` in [llm_client.py](../llm_client.py)
(`gpt-5.4-mini` in this release). The runner does not expose a model flag. Record
any changes to that configuration, agent-specific models, endpoints, or prompts
alongside results.

### Additional setup for Mem-T

Only `memt` and `memt_memonly` require the Mem-T model server. Obtain the
[Mem-T-4B checkpoint](https://huggingface.co/EdwinYue/Mem-T-4B) from its upstream
distribution and follow its model-card terms. Model weights are not bundled.

Serve the downloaded checkpoint using the vLLM packages in the environment:

```bash
export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
python -m vllm.entrypoints.openai.api_server \
  --model /path/to/Mem-T-4B \
  --served-model-name Mem-T-4B \
  --host 127.0.0.1 \
  --port 8765
```

In the benchmark shell, configure the wrapper before starting Python:

```bash
export MEMT_BASE_URL=http://127.0.0.1:8765/v1
export MEMT_MODEL_ID=Mem-T-4B
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

The wrapper creates temporary Chroma stores and trajectories, so the system
temporary directory must be writable and have space available. `OPENAI_API_KEY`
is still required for simulation and evaluation, and for the shared reply model
used by `memt_memonly`.

## 3. Run a one-user smoke test

This is an API-consuming run of **all 31 tasks for one user**, with up to 25
assistant turns per task, followed by reconstruction scoring:

```bash
python runner.py \
  --tasks-dir CustomTasksPooledFinal \
  --agent nomem \
  --run-id smoke_nomem_pooled_50 \
  --users user_001 \
  --scoring-modes dump_all
```

The default bank is
`Deeppersona/data/user_memory_banks_pooled_final.json`; `--bank` can override it.
Always specify `--tasks-dir CustomTasksPooledFinal` for the released tasks. This
argument names a folder **under `benchmark_data/`**; the CLI's historical default
`CustomTasks` is not the released pool. Omitting `--users` runs only
`user_001 user_002 user_003`, not all 50 users.

The smoke test writes `history/smoke_nomem_pooled_50/`,
`memory/smoke_nomem_pooled_50/`, `pref_judge/smoke_nomem_pooled_50/`, and
`output/smoke_nomem_pooled_50/`. API token logs go to
`usage/smoke_nomem_pooled_50_*.txt`; `usage/` is ignored by Git.

Use a fresh `--run-id` for each experiment. Reusing an ID can overwrite per-user
artifacts; the runner does not provide a resume flag. The `pooled_50` substring in
this smoke ID enables the attribution script to find the correct task pool; it
does not determine how many users are run.

## 4. Rerun all five baselines

Define the 50 release users in Bash:

```bash
USERS=$(printf "user_%03d " $(seq 1 50))
```

Run the no-memory baseline with dump-all scoring:

```bash
python runner.py \
  --tasks-dir CustomTasksPooledFinal \
  --agent nomem \
  --run-id nomem_pooled_50_rerun \
  --users $USERS \
  --scoring-modes dump_all
```

Run A-Mem, full long-context memory, and Mem0. Each system performs its own
interaction run, then evaluates both reconstruction modes on that run:

```bash
for AGENT in amem longctx_full mem0; do
  python runner.py \
    --tasks-dir CustomTasksPooledFinal \
    --agent "$AGENT" \
    --run-id "${AGENT}_pooled_50_rerun" \
    --users $USERS \
    --scoring-modes dump_all retrieve || break
done
```

After starting the Mem-T server, run the wrapper used in the paper:

```bash
python runner.py \
  --tasks-dir CustomTasksPooledFinal \
  --agent memt_memonly \
  --run-id memt_memonly_pooled_50_rerun \
  --users $USERS \
  --scoring-modes dump_all retrieve
```

`memt_memonly` uses Mem-T's memory formation, update, and retrieval mechanism,
then uses the shared OpenAI backbone for the final assistant response. The paper
labels this system **Mem-T**. The separate `memt` wrapper returns Mem-T-4B's own
final answer and is not the variant represented by the released results.

### What the scoring modes measure

| Mode | Reconstruction input | Output directory |
| --- | --- | --- |
| `dump_all` | The complete final memory dump for that user | `output/<run-id>/` |
| `retrieve` | The agent's native `search(query, k=5)` results for each dimension | `output/<run-id>_retrieve/` |

The retrieval query contains a dimension name and a category definition; it
excludes the user's reference answer and explanation. Both modes reconstruct a
value first, then judge it against the hidden reference. Requesting both modes
runs the episodes once and scores the same final agent state twice. It adds
reconstruction calls, not a second conversation run.

Transcripts, preference judgments, and memory dumps remain under the base
`<run-id>` in either case. Memory persists across a user's tasks, and each user
gets a fresh agent instance. The final simulator feedback from each episode is
also offered to the agent's memory interface before the next task or scoring.

The scorer reports task completion, reconstruction, interaction length,
preference scores, and memory footprint. See the
[metric definitions](../docs/data.md#scores-and-aggregation) before comparing
systems. `scorer.py` exposes Python scoring classes, not a standalone CLI for
rescoring a directory; calling its reconstruction evaluator makes model calls.

## 5. Rerun failure attribution

Attribution inspects low-recovery dimensions using the saved reconstruction
records, targeted tasks, and transcripts. It makes additional LLM judge calls
and writes `output/<run-id>/attribution/user_*.json`. A shared task-design oracle
cache lives under `output/_task_design_oracle/`.

For the new Mem0 run above:

```bash
# One user
python failure_attribution.py --run mem0_pooled_50_rerun --user user_001

# All users available in that run
python failure_attribution.py --run mem0_pooled_50_rerun
```

To rejudge a released run, substitute `mem0_pooled_50`; this overwrites its saved
attribution records. The script infers the task directory from the run name:
the `pooled_50` naming convention selects `CustomTasksPooledFinal`.

The script also provides `python failure_attribution.py --all`. In the current
implementation it scans every reconstruction directory, including `_retrieve`
directories, but looks for transcripts under that exact run name. The runner
stores these transcripts only under the base run. Use the base run IDs above
for attribution; do not interpret a fresh `_retrieve` attribution run as valid
unless its transcript lookup is adapted. The released attribution files can
always be inspected directly without rerunning them.

The oracle cache is keyed by user and dimension, not task text. If regenerating
tasks, use a separate checkout or archive the old cache before attribution so
that task-design judgments correspond to the new tasks. The Python
`attribute_user(..., tasks_dir=...)` interface accepts an explicit task folder;
the attribution CLI does not expose this argument.

## 6. Regenerate tasks

The accepted task pool is already included. To generate a separate candidate
pool for one user:

```bash
python task_generator.py user_001 \
  --bank Deeppersona/data/user_memory_banks_pooled_final.json \
  --n-per-entry 1 \
  --temperature 0.7 \
  --output-dir benchmark_data/CustomTasksPooledFinal_rerun
```

This makes model calls and writes `user_001.json` in the new directory. Multiple
user IDs can be supplied as positional arguments. To evaluate that pool, pass
`--tasks-dir CustomTasksPooledFinal_rerun` to the runner and select only users
whose task files have been generated. Task regeneration may produce different
wording or counts after retries; it is not an exact replay of the accepted
release.

## Cost and reproducibility

Simulator responses, assistant replies, memory operations for some systems,
slot filling, reconstruction judging, preference judging, task generation, and
attribution can consume model calls. A one-user smoke run is not a fixed-cost
single-call test. Review token logs and provider usage before scaling to the
full benchmark; the local tracker is not a billing statement.

Judge-style calls use temperature `0.0` in the code. Task generation, simulation,
API/model updates, retries, and memory-system behavior can still change results;
bitwise determinism is not guaranteed. Record the repository commit, environment,
task pool, users, run ID, model configuration, and scoring mode for every new
result. The released evidence supports auditing the reported experiments
without paying to repeat them.
