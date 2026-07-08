"""
Tests for the architecture-concepts demo data (demo_architecture.py).
The key assertion is the double-entry invariant: every transfer's legs sum to zero —
including the FAILED transfer once its compensation legs are counted.
"""

from conftest import auth

URL = "/api/admin/architecture/demo"


def test_demo_endpoint_requires_auth(client):
    assert client.get(URL).status_code == 401


def test_double_entry_legs_sum_to_zero(client):
    data = client.get(URL, headers=auth("admin-token")).json()
    checks = data["double_entry_zero_sum_check"]
    assert len(checks) >= 3  # settled, pending, failed+compensated
    for transfer_id, check in checks.items():
        assert check["balanced"] is True, f"{transfer_id} legs do not sum to zero"


def test_all_concepts_present(client):
    data = client.get(URL, headers=auth("admin-token")).json()

    # Accounts + optimistic locking: version column present and advancing
    accounts = data["accounts_and_optimistic_locking"]
    assert any(a["version"] > 1 for a in accounts)
    # Account lifecycle: at least one non-ACTIVE account
    assert any(a["status"] == "FROZEN" for a in accounts)

    # Transfer state machine covers happy, in-flight, and failed paths
    states = {t["state"] for t in data["transfer_state_machine"]}
    assert {"SETTLED", "PENDING", "FAILED"} <= states

    # Compensation: FAILED transfer has appended COMPENSATION legs (never deletes)
    comp_legs = [l for l in data["double_entry_ledger_legs"]
                 if l["entry_type"] == "COMPENSATION"]
    assert len(comp_legs) == 2

    # Outbox: at least one event still unpublished (relay lag is the normal state)
    events = data["outbox_events"]
    assert any(not e["published"] for e in events)
    assert any(e["published"] for e in events)

    # Notifications: async consumer states incl. FAILED with retries
    notif_status = {n["status"] for n in data["notifications"]}
    assert {"SENT", "PENDING", "FAILED"} <= notif_status
    assert any(n["retries"] > 0 for n in data["notifications"])
