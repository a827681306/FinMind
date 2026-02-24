"""Tests for weekly financial digest (#121)."""


def _create_category(client, auth_header, name):
    r = client.post("/categories", json={"name": name}, headers=auth_header)
    assert r.status_code in (201, 409)
    r = client.get("/categories", headers=auth_header)
    return next(c["id"] for c in r.get_json() if c["name"] == name)


def _create_expense(client, auth_header, amount, desc, cat_id, date_str):
    r = client.post("/expenses", json={
        "amount": amount, "description": desc, "category_id": cat_id, "date": date_str,
    }, headers=auth_header)
    assert r.status_code == 201


class TestWeeklyDigest:
    def test_empty_digest(self, client, auth_header):
        r = client.get("/digest?date=2025-01-07", headers=auth_header)
        assert r.status_code == 200
        data = r.get_json()
        assert data["total_spending"] == 0
        assert data["transaction_count"] == 0
        assert data["top_categories"] == []
        assert data["change_pct"] == 0.0

    def test_digest_with_expenses(self, client, auth_header):
        cat = _create_category(client, auth_header, "Food")
        _create_expense(client, auth_header, 50.0, "Groceries", cat, "2026-03-10")
        _create_expense(client, auth_header, 30.0, "Lunch", cat, "2026-03-12")

        r = client.get("/digest?date=2026-03-14", headers=auth_header)
        assert r.status_code == 200
        data = r.get_json()
        assert data["total_spending"] == 80.0
        assert data["transaction_count"] == 2
        assert len(data["top_categories"]) == 1
        assert data["top_categories"][0]["name"] == "Food"

    def test_week_over_week_change(self, client, auth_header):
        cat = _create_category(client, auth_header, "Transport")
        # Previous week
        _create_expense(client, auth_header, 100.0, "Gas", cat, "2026-04-01")
        # This week
        _create_expense(client, auth_header, 150.0, "Gas", cat, "2026-04-08")

        r = client.get("/digest?date=2026-04-14", headers=auth_header)
        assert r.status_code == 200
        data = r.get_json()
        assert data["total_spending"] == 150.0
        assert data["previous_week_spending"] == 100.0
        assert data["change_pct"] == 50.0

    def test_invalid_date(self, client, auth_header):
        r = client.get("/digest?date=bad", headers=auth_header)
        assert r.status_code == 400

    def test_default_date(self, client, auth_header):
        r = client.get("/digest", headers=auth_header)
        assert r.status_code == 200
        data = r.get_json()
        assert "period" in data
        assert "start" in data["period"]
        assert "end" in data["period"]
