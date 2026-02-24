"""Smart digest with weekly financial summary (#121).

Generates a weekly summary of spending, top categories, budget status,
and upcoming bills for a given user.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, extract

from ..extensions import db
from ..models import Expense, Category, Bill

logger = logging.getLogger("finmind.digest")


def get_weekly_digest(user_id: int, end_date: date = None):
    """Generate a weekly financial summary ending on end_date (default: today)."""
    if end_date is None:
        end_date = date.today()
    start_date = end_date - timedelta(days=6)

    # Total spending this week
    total = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= start_date,
            Expense.spent_at <= end_date,
            Expense.expense_type != "INCOME",
        )
        .scalar()
    )

    # Previous week for comparison
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    prev_total = (
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= prev_start,
            Expense.spent_at <= prev_end,
            Expense.expense_type != "INCOME",
        )
        .scalar()
    )

    # Top categories
    top_cats = (
        db.session.query(
            func.coalesce(Category.name, "Uncategorized").label("name"),
            func.sum(Expense.amount).label("total"),
        )
        .outerjoin(Category, (Category.id == Expense.category_id) & (Category.user_id == user_id))
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= start_date,
            Expense.spent_at <= end_date,
            Expense.expense_type != "INCOME",
        )
        .group_by(Category.name)
        .order_by(func.sum(Expense.amount).desc())
        .limit(5)
        .all()
    )

    # Transaction count
    tx_count = (
        db.session.query(func.count(Expense.id))
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= start_date,
            Expense.spent_at <= end_date,
        )
        .scalar()
    )

    # Upcoming bills (next 7 days)
    upcoming_end = end_date + timedelta(days=7)
    upcoming_bills = (
        Bill.query.filter(
            Bill.user_id == user_id,
            Bill.active == True,
            Bill.next_due_date >= end_date,
            Bill.next_due_date <= upcoming_end,
        )
        .order_by(Bill.next_due_date)
        .all()
    )

    total_f = float(total or 0)
    prev_f = float(prev_total or 0)
    change_pct = round((total_f - prev_f) / prev_f * 100, 1) if prev_f > 0 else 0.0

    return {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "total_spending": round(total_f, 2),
        "previous_week_spending": round(prev_f, 2),
        "change_pct": change_pct,
        "transaction_count": tx_count or 0,
        "top_categories": [
            {"name": c.name, "amount": round(float(c.total), 2)} for c in top_cats
        ],
        "upcoming_bills": [
            {
                "name": b.name,
                "amount": round(float(b.amount), 2),
                "due_date": b.next_due_date.isoformat(),
            }
            for b in upcoming_bills
        ],
    }
