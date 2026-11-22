import re
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request

from app.extensions import db
from app.models import Budget, User

api = Blueprint("api", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@api.route("/")
def index():
    return jsonify({"status": "ok", "message": "Budget API is running"})


@api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


def make_token(user):
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=current_app.config["JWT_EXPIRES_MINUTES"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        parts = header.split()
        if len(parts) != 2 or parts[0] != "Bearer":
            return jsonify({"error": "authentication required"}), 401
        try:
            data = jwt.decode(
                parts[1],
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
            )
        except jwt.InvalidTokenError:  # covers expired and tampered tokens
            return jsonify({"error": "invalid or expired token"}), 401
        try:
            user_id = int(data["sub"])
        except (KeyError, ValueError):
            return jsonify({"error": "invalid or expired token"}), 401
        user = db.session.get(User, user_id)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


@api.route("/auth/register", methods=["POST"])
def register():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400

    email = body.get("email")
    password = body.get("password")
    if not isinstance(email, str) or len(email) > 254 or not EMAIL_RE.match(email):
        return jsonify({"error": "valid email required"}), 400
    if not isinstance(password, str) or not (8 <= len(password) <= 128):
        return jsonify({"error": "password must be 8-128 characters"}), 400

    email = email.strip().lower()
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@api.route("/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400

    email = body.get("email")
    password = body.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({"error": "email and password required"}), 400

    user = User.query.filter_by(email=email.strip().lower()).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "invalid email or password"}), 401

    return jsonify({"token": make_token(user), "user": user.to_dict()}), 200


@api.route("/auth/profile", methods=["GET"])
@token_required
def profile():
    return jsonify(g.current_user.to_dict()), 200


MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def is_amount(value):
    # numbers only (bool is a subclass of int, so exclude it), and not negative
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def get_owned_budget(budget_id):
    """Return (budget, error_response). Order: 404, then 403."""
    budget = db.session.get(Budget, budget_id)
    if budget is None:
        return None, (jsonify({"error": "budget not found"}), 404)
    if budget.user_id != g.current_user.id:
        return None, (jsonify({"error": "forbidden"}), 403)
    return budget, None


@api.route("/budgets", methods=["POST"])
@token_required
def create_budget():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400

    month = body.get("month")
    planned = body.get("planned")
    actual = body.get("actual", 0)

    if not isinstance(month, str) or not MONTH_RE.match(month):
        return jsonify({"error": "month must be in YYYY-MM format"}), 400
    if not is_amount(planned) or not is_amount(actual):
        return jsonify({"error": "planned and actual must be non-negative numbers"}), 400

    exists = Budget.query.filter_by(user_id=g.current_user.id, month=month).first()
    if exists:
        return jsonify({"error": f"budget already exists for {month}"}), 400

    # owner comes from the token, never from the request body
    budget = Budget(user_id=g.current_user.id, month=month, planned=planned, actual=actual)
    db.session.add(budget)
    db.session.commit()
    return jsonify(budget.to_dict()), 201


@api.route("/budgets", methods=["GET"])
@token_required
def list_budgets():
    budgets = (
        Budget.query.filter_by(user_id=g.current_user.id)
        .order_by(Budget.month.desc())
        .all()
    )
    return jsonify([b.to_dict() for b in budgets]), 200


@api.route("/budgets/<int:budget_id>", methods=["GET"])
@token_required
def get_budget(budget_id):
    budget, error = get_owned_budget(budget_id)
    if error:
        return error
    return jsonify(budget.to_dict()), 200


@api.route("/budgets/<int:budget_id>", methods=["PATCH"])
@token_required
def update_budget(budget_id):
    budget, error = get_owned_budget(budget_id)
    if error:
        return error

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400

    # only planned and actual are editable; id, user_id, month are ignored
    updates = {k: body[k] for k in ("planned", "actual") if k in body}
    if not updates:
        return jsonify({"error": "provide planned and/or actual"}), 400
    if not all(is_amount(v) for v in updates.values()):
        return jsonify({"error": "planned and actual must be non-negative numbers"}), 400

    for field, value in updates.items():
        setattr(budget, field, value)
    db.session.commit()
    return jsonify(budget.to_dict()), 200


@api.route("/budgets/<int:budget_id>", methods=["DELETE"])
@token_required
def delete_budget(budget_id):
    budget, error = get_owned_budget(budget_id)
    if error:
        return error
    db.session.delete(budget)
    db.session.commit()
    return "", 204