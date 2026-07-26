"""
Catalog of faults to inject. Each fault is DATA, not code — grow the dataset by
adding entries here; the harness logic never changes.

Fields:
  label       : genuine_regression | transient | flaky_test  (infra is CI-only)
  description : human note -> goes into injected_fault
  file        : path relative to app repo
  mode        : "replace" (swap existing text) or "append" (add new code)
  find/replace: for mode="replace"
  append      : for mode="append"

NOTE: 'infra' faults break CI config and don't surface via local pytest, so they
are produced via the manual CI loop, not this harness.

Each 'replace' fault must match text that exists EXACTLY ONCE in the target file,
or the harness raises (safer than a silent partial change).
"""

FAULTS = [
    # ============================================================
    # GENUINE REGRESSION — real logic bugs, caught by an assertion
    # ============================================================
    {
        "label": "genuine_regression",
        "description": "Currency conversion: division flipped to multiplication (amount / rate -> amount * rate)",
        "file": "main.py",
        "mode": "replace",
        "find": "total_amount += amount / rate",
        "replace": "total_amount += amount * rate",
    },
    {
        "label": "genuine_regression",
        "description": "Base-currency expense subtracted instead of added to the total",
        "file": "main.py",
        "mode": "replace",
        "find": "            if currency == base_currency:\n                total_amount += amount",
        "replace": "            if currency == base_currency:\n                total_amount -= amount",
    },
    {
        "label": "genuine_regression",
        "description": "Conversion uses multiplication by reciprocal incorrectly (amount / rate -> amount / rate / rate)",
        "file": "main.py",
        "mode": "replace",
        "find": "total_amount += amount / rate",
        "replace": "total_amount += amount / rate / rate",
    },
    {
        "label": "genuine_regression",
        "description": "expenses_count no longer subtracts skipped currencies (off-by count)",
        "file": "main.py",
        "mode": "replace",
        "find": '"expenses_count": len(rows) - len(skipped_currency)',
        "replace": '"expenses_count": len(rows) + len(skipped_currency)',
    },
    {
        "label": "genuine_regression",
        "description": "Unknown-currency branch wrongly adds raw amount instead of skipping",
        "file": "main.py",
        "mode": "replace",
        "find": '                skipped_currency.append({"currency": currency, "amount": amount})',
        "replace": '                total_amount += amount\n                skipped_currency.append({"currency": currency, "amount": amount})',
    },
    {
        "label": "genuine_regression",
        "description": "base_currency no longer uppercased, breaking case-insensitive matching",
        "file": "main.py",
        "mode": "replace",
        "find": "    base_currency = base_currency.upper()",
        "replace": "    base_currency = base_currency",
    },
    {
        "label": "genuine_regression",
        "description": "Currency not uppercased on insert, breaking normalization",
        "file": "main.py",
        "mode": "replace",
        "find": "expense.currency.upper()",
        "replace": "expense.currency",
    },
    {
        "label": "genuine_regression",
        "description": "Amount validation gt=0 changed to ge=0, allowing zero amounts",
        "file": "main.py",
        "mode": "replace",
        "find": "amount: float = Field(gt=0)",
        "replace": "amount: float = Field(ge=0)",
    },
    {
        "label": "genuine_regression",
        "description": "Delete endpoint no longer returns 404 for missing id (guard removed)",
        "file": "main.py",
        "mode": "replace",
        "find": '        if cursor.rowcount == 0:\n            raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")',
        "replace": '        if cursor.rowcount == -1:\n            raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")',
    },
    {
        "label": "genuine_regression",
        "description": "List endpoint drops ORDER BY, breaking ordered-result expectations",
        "file": "main.py",
        "mode": "replace",
        "find": 'cursor.execute("SELECT * FROM expenses ORDER BY id")',
        "replace": 'cursor.execute("SELECT * FROM expenses ORDER BY id DESC")',
    },

    # ============================================================
    # TRANSIENT — external dependency failures (network/upstream)
    # Each appends a test that simulates a different failure mode.
    # ============================================================
    {
        "label": "transient",
        "description": "Exchange-rate API raises ConnectError (host unreachable)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
def test_injected_transient_connect_error(client, monkeypatch):
    """Injected transient: connection refused / host unreachable."""
    import httpx, main
    class C:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, *a, **k): raise httpx.ConnectError("Connection refused")
    monkeypatch.setattr(main.httpx, "AsyncClient", C)
    _add_expense(client, 100, "INR")
    assert client.get("/expenses/total?base_currency=USD").status_code == 200
''',
    },
    {
        "label": "transient",
        "description": "Exchange-rate API raises ReadTimeout (slow upstream)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
def test_injected_transient_read_timeout(client, monkeypatch):
    """Injected transient: upstream read timeout."""
    import httpx, main
    class C:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, *a, **k): raise httpx.ReadTimeout("Read timed out")
    monkeypatch.setattr(main.httpx, "AsyncClient", C)
    _add_expense(client, 100, "INR")
    assert client.get("/expenses/total?base_currency=USD").status_code == 200
''',
    },
    {
        "label": "transient",
        "description": "Exchange-rate API raises ConnectTimeout (handshake timeout)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
def test_injected_transient_connect_timeout(client, monkeypatch):
    """Injected transient: connection establishment timed out."""
    import httpx, main
    class C:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, *a, **k): raise httpx.ConnectTimeout("Connect timed out")
    monkeypatch.setattr(main.httpx, "AsyncClient", C)
    _add_expense(client, 100, "INR")
    assert client.get("/expenses/total?base_currency=USD").status_code == 200
''',
    },
    {
        "label": "transient",
        "description": "Exchange-rate API returns HTTP 503 (service unavailable upstream)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
def test_injected_transient_upstream_503(client, monkeypatch):
    """Injected transient: upstream returns 503."""
    import httpx, main
    class Resp:
        status_code = 503
        def raise_for_status(self):
            raise httpx.HTTPStatusError("503", request=None, response=self)
        def json(self): return {}
    class C:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, *a, **k): return Resp()
    monkeypatch.setattr(main.httpx, "AsyncClient", C)
    _add_expense(client, 100, "INR")
    assert client.get("/expenses/total?base_currency=USD").status_code == 200
''',
    },
    {
        "label": "transient",
        "description": "Exchange-rate API raises generic PoolTimeout (connection pool exhausted)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
def test_injected_transient_pool_timeout(client, monkeypatch):
    """Injected transient: connection pool exhausted."""
    import httpx, main
    class C:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, *a, **k): raise httpx.PoolTimeout("Pool timeout")
    monkeypatch.setattr(main.httpx, "AsyncClient", C)
    _add_expense(client, 100, "INR")
    assert client.get("/expenses/total?base_currency=USD").status_code == 200
''',
    },

    # ============================================================
    # FLAKY — non-deterministic failures, no code change
    # ============================================================
    {
        "label": "flaky_test",
        "description": "Random jitter in assertion (fails ~50% of runs)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
import random as _rnd_a
def test_injected_flaky_jitter(client, mock_rates):
    """Injected flaky: random jitter assertion."""
    _add_expense(client, 100, "USD")
    body = client.get("/expenses/total?base_currency=USD").json()
    assert body["total"] == 100.0 + _rnd_a.choice([0, 0.5])
''',
    },
    {
        "label": "flaky_test",
        "description": "Random failure via probability threshold (~50% fail)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
import random as _rnd_b
def test_injected_flaky_probability(client, mock_rates):
    """Injected flaky: passes only when random() > 0.5."""
    _add_expense(client, 100, "USD")
    body = client.get("/expenses/total?base_currency=USD").json()
    assert body["total"] == 100.0 and _rnd_b.random() > 0.5
''',
    },
    {
        "label": "flaky_test",
        "description": "Fails on even-numbered seconds (time-dependent, ~50%)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
import time as _t_c
def test_injected_flaky_time_parity(client, mock_rates):
    """Injected flaky: depends on current-second parity."""
    _add_expense(client, 100, "USD")
    body = client.get("/expenses/total?base_currency=USD").json()
    assert body["total"] == 100.0 and (int(_t_c.time()) % 2 == 0)
''',
    },
    {
        "label": "flaky_test",
        "description": "Random choice among wrong expected values (~66% fail)",
        "file": "tests/test_api.py",
        "mode": "append",
        "append": '''
import random as _rnd_d
def test_injected_flaky_random_expected(client, mock_rates):
    """Injected flaky: expected value chosen randomly, usually wrong."""
    _add_expense(client, 100, "USD")
    body = client.get("/expenses/total?base_currency=USD").json()
    assert body["total"] == _rnd_d.choice([100.0, 99.0, 101.0])
''',
    },
]