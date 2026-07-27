# ci-triage-dataset

Labeled CI failure logs for the agentic CI triage project. Every example is a
deliberate fault injection against the [expense-tracker-api](https://github.com/TheOnlyRoshan/expense-tracker-api)
toy application — never an accidental failure, so labels are known rather than
guessed.

## Contents

| Class | Count | Captured | Synthetic |
|---|---|---|---|
| genuine_regression | 16 | 16 | 0 |
| flaky_test | 13 | 13 | 0 |
| transient | 12 | 3 | 9 |
| infra | 8 | 1 | 7 |
| **Total** | **49** | **33** | **16** |

Labeling rules are in [`LABELING_RUBRIC.md`](LABELING_RUBRIC.md).

## Layout

```
dataset/
  genuine_regression/   001.json  001.log  ...
  flaky_test/
  transient/
  infra/
tools/
  check_duplicates.py
```

Each example is two files: `NNN.json` (metadata) and `NNN.log` (raw CI output).

## Schema

```json
{
  "id": "genuine_regression_013",
  "label": "genuine_regression",
  "log_file": "013.log",
  "injected_fault": "Root health endpoint returns key 'state' instead of 'status'",
  "commit_sha": null,
  "ci_provider": "github_actions",
  "trigger": "push",
  "failing_tests": ["test_root_health_check"],
  "log_source": "captured",
  "timestamp": "2026-07-28T09:17:00+05:30"
}
```

`log_source` is `captured` when the log came from a real test run, `synthetic`
when the log was constructed. `commit_sha` is `null` for synthetic examples and
is never fabricated.

## Provenance

**Captured (33).** The fault was applied to the application, the real 16-test
pytest suite was executed, and the true output recorded — real tracebacks, real
assertion diffs, real line numbers. `failing_tests` is parsed from the run.

**Synthetic (16).** Failures that cannot be triggered on demand — registry rate
limits, DNS SERVFAIL, runner loss, artifact-service outages. Log bodies
reproduce genuine tool output (pip resolver errors, git fetch retries, apt
messages) in GitHub Actions step framing.

Report accuracy on the two subsets separately. A large gap between them
indicates a problem with the eval set rather than the classifier.

## Design notes

**Class balance over raw count.** Six near-duplicate logs were removed after a
content-similarity check. Duplicates inflate the count without adding coverage
and distort evaluation scores, since one repeated failure shape can swing
accuracy by several points.

**Deliberate shortcut prevention.** Examples within each class are spread
across pipeline stages and log lengths, so a classifier cannot succeed on
surface cues:

- `infra` spans workflow parsing, runner scheduling, dependency resolution, and
  source builds — logs run from 2 to 60 lines, so "short log" is not learnable.
- `transient` spans checkout, dependency install, test execution, and artifact
  upload — so "httpx error inside a test" is not learnable.
- `transient_010` shows nine tests passing before the runner dies: pytest
  output is present but no test failed.
- `flaky_test` uses order dependence, races, float precision, timing budgets,
  wall-clock assumptions, iteration order, and resource leaks — not only
  randomised assertions.

**Known hard boundaries.** `transient` and `flaky_test` are the most confusable
pair; both are non-deterministic and both would pass on retry. They are
separated by whether the instability lives outside the repository or inside the
test. Expect this pair to dominate the confusion matrix.

**Single-log limits.** Flakiness is only provable across runs. A single log
from a flaky test can be surface-identical to a genuine regression. This is a
property of the task, not a defect in the data.

## Usage

Examples serve two disjoint roles. They must not overlap.

- **Few-shot exemplars** — a small subset included in the classifier prompt.
- **Evaluation set** — everything else. Never shown to the model; used only to
  score it.

Record the exemplar IDs in the pipeline's `config.yaml` so the split is fixed
and every evaluation run is reproducible.

Prefer `captured` examples as exemplars where possible, since they shape every
prediction the classifier makes.

## Tools

```bash
python tools/check_duplicates.py 0.90
```

Flags any pair of logs within a class above the given content-similarity
threshold. Exits non-zero when duplicates are found, so it can run in CI. Run
before adding new examples.
