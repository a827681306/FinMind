"""API route for weekly financial digest (#121)."""

from datetime import date, datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..services.digest import get_weekly_digest

bp = Blueprint("digest", __name__)


@bp.get("")
@jwt_required()
def weekly():
    """Get weekly financial digest. Optional ?date=YYYY-MM-DD for end date."""
    uid = int(get_jwt_identity())
    date_str = request.args.get("date")
    end_date = None
    if date_str:
        try:
            end_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify(error="invalid date, expected YYYY-MM-DD"), 400
    result = get_weekly_digest(uid, end_date)
    return jsonify(result)
