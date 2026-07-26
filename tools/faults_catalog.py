"""
Catalog of faults to inject. Each fault is data, not code — add new entries
here to grow the dataset without touching the harness logic.

Each fault is a dict with:
  label       : one of genuine_regression | transient | flaky_test | infra
  description : human-readable note (goes into injected_fault in metadata)
  file        : path (relative to app repo) of the file to modify
  mode        : "replace" (swap existing text) or "append" (add new code)
  find/replace: for mode="replace" — the exact text to find and its replacement
  append      : for mode="append" — the code block to add to the end of the file

NOTE: 'infra' faults (breaking CI config) don't surface through local pytest,
so they are generated via the manual CI loop, not this harness. This catalog
covers the three pytest-visible categories.
"""

FAULTS = [
    # ---------------- genuine_regression ----------------
    {
        "label": "genuine_regression",
        "description": "Flip division to multiplication in currency conversion (amount / rate -> amount * rate)",
        "file": "main.py",
        "mode": "replace",
        "find": "total_amount += amount / rate",
        "replace": "total_amount += amount * rate",
    },

    # ---------------- transient ----------------
    {
        "label": "transient",
        "description": "Simulate a network ConnectError on the exchange-rate call; app returns 503, test asserts 200",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
def test_injected_transient_network_failure(client, monkeypatch):
    """Injected: simulates the exchange-rate API being unreachable."""
    import httpx
    import main

    class FailingAsyncClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, *a, **k):
            raise httpx.ConnectError("Connection failed")

    monkeypatch.setattr(main.httpx, "AsyncClient", FailingAsyncClient)
    _add_expense(client, 100, "INR")
    response = client.get("/expenses/total?base_currency=USD")
    assert response.status_code == 200
''',
    },

    # ---------------- flaky_test ----------------
    {
        "label": "flaky_test",
        "description": "Non-deterministic assertion (random jitter) — fails intermittently with no code change",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
import random as _injected_random

def test_injected_flaky_rounding(client, mock_rates):
    """Injected: non-deterministic assertion, fails ~50% of runs."""
    _add_expense(client, 100, "USD")
    body = client.get("/expenses/total?base_currency=USD").json()
    jitter = _injected_random.choice([0, 0.5])
    assert body["total"] == 100.0 + jitter
''',
    },
]