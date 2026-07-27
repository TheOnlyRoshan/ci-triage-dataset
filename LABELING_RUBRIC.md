# Labeling Rubric

The rules used to assign a label to every example in this dataset. Applied
consistently at labeling time, and reused verbatim as the class definitions in
the classifier's system prompt.

## The two questions that decide everything

Ask them in this order.

**Q1 — Is the application code at fault?**
Yes → `genuine_regression`. Stop.

**Q2 — Would re-running this exact commit, with no changes, probably pass?**

| Answer | Label | Why |
|---|---|---|
| No, it fails every time | `infra` | The pipeline configuration is wrong |
| Yes, it's a coin flip caused by the environment | `transient` | An external system misbehaved |
| Yes, it's a coin flip caused by the test itself | `flaky_test` | The test's own logic is unstable |

The `transient` / `flaky_test` split turns on **where the instability lives** —
outside the repository, or inside the test code.

---

## genuine_regression

Application logic is wrong. The test correctly caught it.

Include: wrong arithmetic, broken validation, changed response contract,
incorrect SQL, wrong status codes, off-by-one counts.

Exclude: a test that fails while the application is correct → `flaky_test`.

Signal: a specific assertion failure that points at real behaviour, reproducible
on every run.

## transient

Something outside the repository failed in a way that would likely succeed on
retry. Both the commit and the CI configuration are correct.

Include: network timeouts, upstream 5xx, DNS SERVFAIL, registry rate limits,
runner loss, mirror hash mismatches, artifact-service outages, disk exhaustion.

Exclude: a permanently unreachable URL → `infra`. A test whose own logic is
unstable → `flaky_test`.

Note: transient failures occur at **any** pipeline stage — checkout, install,
test execution, artifact upload. Do not assume they only appear inside pytest.

## flaky_test

The test is non-deterministic. The application is fine and the environment is
fine; the test would pass on a retry with nothing changed.

Include: randomised assertions, wall-clock or timing dependence, order
dependence, shared mutable state, float equality without tolerance, race
conditions, assumptions about a clean workspace.

Exclude: an external service failing → `transient`.

Note: a single log from a flaky test can look identical to a genuine
regression. Flakiness is only provable across runs. When one log is all you
have, judge by whether the *assertion itself* is unstable.

## infra

The pipeline configuration is wrong. Deterministic — re-running changes nothing.
No application code is involved.

Include: invalid runtime versions, unresolvable dependency pins, dependency
conflicts, missing system libraries, malformed workflow YAML, non-existent
runner labels, missing secrets.

Exclude: a correctly configured pipeline whose network call happened to fail
→ `transient`.

---

## Resolved edge cases

**Unreachable package index (`infra_003`) — infra, not transient.**
The URL is permanently wrong, so every retry fails identically. The log
*resembles* a network failure, which is exactly why the rule is stated:
deterministic → infra.

**Missing environment library (`infra_005`) — infra, not genuine_regression.**
The build fails because the runner lacks a system library, not because the
application is broken.

**Clean-workspace assumption (`flaky_test_010`) — flaky_test, not infra.**
The runner's behaviour is normal; the test made an unsafe assumption about it.
The unstable logic is in the test, so it is flaky.

**Runner loss mid-suite (`transient_010`) — transient, not genuine_regression.**
Nine tests pass before the runner dies. Pytest output is present, but no test
failed. Presence of test output does not imply a test problem.

**Exchange-rate service failure — transient, not genuine_regression.**
The application handles the outage correctly by returning 503; the test asserts
200. Surface signal is an assertion failure, but the cause is external.

---

## Field conventions

- `failing_tests` — populated from the run. Empty when the job failed before
  tests executed. Never left empty to imply a label.
- `log_source` — `captured` for real CI or real local runs, `synthetic` for
  hand-constructed logs. Report accuracy on both subsets separately; a large
  gap indicates the eval set, not the classifier, is the problem.
- `commit_sha` — `null` for synthetic examples. Never fabricated.

## Maintenance

The dataset grows monotonically. Every production misclassification gets
labeled and added, so the same failure cannot silently return.

Before adding an example, check it is not a near-duplicate of one already
present. Duplicates inflate the count without adding coverage and distort
evaluation scores. `tools/check_duplicates.py` flags any pair above 0.90
content similarity.
