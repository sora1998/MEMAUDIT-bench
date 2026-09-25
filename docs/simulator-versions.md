# Simulator versions

Improve user simulator.

| Branch | Default simulator | Results |
| :-- | :-- | :-- |
| [`main`](https://github.com/sora1998/MEMAUDIT-bench/tree/main) | `v2` | Updated implementation; no new benchmark results |
| [`paper-v1`](https://github.com/sora1998/MEMAUDIT-bench/tree/paper-v1) | Original paper simulator | Published results |

On `main`, use `--simulator-version v2` (the default) for the current simulator,
or `--simulator-version paper-v1` for the original prompt. For example, after
[environment setup](reproduction.md#2-install-the-rerun-environment):

```bash
python runner.py \
  --simulator-version v2 \
  --tasks-dir CustomTasksPooledFinal \
  --agent nomem \
  --run-id smoke_nomem_v2_pooled_50 \
  --users user_001 \
  --scoring-modes dump_all
```

New episode histories record `simulator_config.version` and
`simulator_config.sha256` (the exact system-prompt hash). Use a fresh run ID for
each experiment and compare systems using the same simulator version.
Scoring and attribution are unchanged.

To use the complete original code snapshot:

```bash
git clone --branch paper-v1 https://github.com/sora1998/MEMAUDIT-bench.git MemAudit-paper-v1
cd MemAudit-paper-v1
```

Follow that branch's reproduction guide. Its runner predates the
`--simulator-version` option and always uses the original simulator.

The update is covered by offline code checks:

```bash
python -m unittest discover -s tests -v
```

These checks use mock responses and require no API key or model calls.
