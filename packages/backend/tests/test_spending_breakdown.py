"""Tests for essential vs discretionary spending breakdown (Issue #120)."""

from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_category(client, auth_header, name):
    r = client.post("/categories", json={"name": name}, headers=auth_header)
    assert r.status_code == 201
    return r.get_json()["id"]


def _create_expense(client, auth_header, amount, category_id=None, dt=None):
    payload = {
        "amount": amount,
        "description": f"test-{amount}",
        "expense_type": "EXPENSE",
    }
    if category_id:
        payload["category_id"] = category_id
    if dt:
        payload["date"] = dt
    r = client.post("/expenses", json=payload, headers=auth_header)
    assert r.status_code == 201
    return r.get_json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSpendingBreakdown:
    def test_empty_month(self, client, auth_header):
        r = client.get("/spending?month=2020-01", headers=auth_header)
        assert r.status_code == 200
        body = r.get_json()
        assert body["total"] == 0
        assert body["essential_total"] == 0
        assert body["discretionary_total"] == 0
        assert body["essential_pct"] == 0
        assert body["discretionary_pct"] == 0
        assert body["categories"] == []

    def test_essential_classification(self, client, auth_header):
        today = date.today()
        ym = today.strftime("%Y-%m")
        cat_id = _create_category(client, auth_header, "Groceries")
        _create_expense(client, auth_header, 150.0, cat_id, today.isoformat())

        r = client.get(f"/spending?month={ym}", headers=auth_header)
        assert r.status_code == 200
        body = r.get_json()
        assert body["essential_total"] == 150.0
        assert body["discretionary_total"] == 0
        assert len(body["categories"]) == 1
        assert body["categories"][0]["classification"] == "essential"

    def test_discretionary_classification(self, client, auth_header):
        today = date.today()
        ym = today.strftime("%Y-%m")
        cat_id = _create_category(client, auth_header, "Entertainment")
        _create_expense(client, auth_header, 80.0, cat_id, today.isoformat())

        r = client.get(f"/spending?month={ym}", headers=auth_header)
        assert r.status_code == 200
        body = r.get_json()
        assert body["discretionary_total"] == 80.0
        assert body["essential_total"] == 0
        assert body["categories"][0]["classification"] == "discretionary"

    def test_mixed_spending(self, client, auth_header):
        today = date.today()
        ym = today.strftime("%Y-%m")
        rent_id = _create_category(client, auth_header, "Rent")
        dining_id = _create_category(client, auth_header, "Dining Out")

        _create_expense(client, auth_header, 1000.0, rent_id, today.isoformat())
        _create_expense(client, auth_header, 200.0, dining_id, today.isoformat())

        r = client.get(f"/spending?month={ym}", headers=auth_header)
        assert r.status_code == 200
        body = r.get_json()
        assert body["essential_total"] == 1000.0
        assert body["discretionary_total"] == 200.0
        assert body["total"] == 1200.0
        # Percentages
        assert abs(body["essential_pct"] - 83.3) < 0.2
        assert abs(body["discretionary_pct"] - 16.7) < 0.2

    def test_uncategorized_defaults_to_discretionary(self, client, auth_header):
        today = date.today()
        ym = today.strftime("%Y-%m")
        _create_expense(client, auth_header, 50.0, dt=today.isoformat())

        r = client.get(f"/spending?month={ym}", headers=auth_header)
        assert r.status_code == 200
        body = r.get_json()
        assert body["discretionary_total"] == 50.0
        cats = body["categories"]
        assert any(c["category_name"] == "Uncategorized" for c in cats)

    def test_income_excluded(self, client, auth_header):
        today = date.today()
        ym = today.strftime("%Y-%m")
        r = client.post(
            "/expenses",
            json={
                "amount": 5000.0,
                "description": "salary",
                "expense_type": "INCOME",
                "date": today.isoformat(),
            },
            headers=auth_header,
        )
        assert r.status_code == 201

        r = client.get(f"/spending?month={ym}", headers=auth_header)
        assert r.status_code == 200
        body = r.get_json()
        assert body["total"] == 0

    def test_invalid_month_rejected(self, client, auth_header):
        r = client.get("/spending?month=bad", headers=auth_header)
        assert r.status_code == 400

        r = client.get("/spending?month=2025-13", headers=auth_header)
        assert r.status_code == 400

    def test_defaults_to_current_month(self, client, auth_header):
        r = client.get("/spending", headers=auth_header)
        assert r.status_code == 200
        body = r.get_json()
        assert body["period"] == date.today().strftime("%Y-%m")

    def test_response_structure(self, client, auth_header):
        r = client.get("/spending", headers=auth_header)
        assert r.status_code == 200
        body = r.get_json()
        required = {
            "period", "essential_total", "discretionary_total",
            "total", "essential_pct", "discretionary_pct", "categories",
        }
        assert required.issubset(body.keys())

    def test_categories_sorted_by_amount_desc(self, client, auth_header):
        today = date.today()
        ym = today.strftime("%Y-%m")
        cat_a = _create_category(client, auth_header, "Insurance")
        cat_b = _create_category(client, auth_header, "Shopping")

        _create_expense(client, auth_header, 50.0, cat_a, today.isoformat())
        _create_expense(client, auth_header, 300.0, cat_b, today.isoformat())

        r = client.get(f"/spending?month={ym}", headers=auth_header)
        assert r.status_code == 200
        cats = r.get_json()["categories"]
        amounts = [c["amount"] for c in cats]
        assert amounts == sorted(amounts, reverse=True)
