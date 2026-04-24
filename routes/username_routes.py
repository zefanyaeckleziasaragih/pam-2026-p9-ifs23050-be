import logging
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db, limiter
from models.username import GeneratedUsername
from services.ai_service import generate_usernames

logger = logging.getLogger(__name__)

username_bp = Blueprint("usernames", __name__)

VALID_STYLES = {"gaming", "professional", "cute", "aesthetic", "funny", "minimalist", "fantasy", "tech"}


@username_bp.route("", methods=["GET"])
@jwt_required()
def get_usernames():
    user_id = int(get_jwt_identity())

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 50)

    pagination = (
        GeneratedUsername.query.filter_by(user_id=user_id)
        .order_by(GeneratedUsername.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        "data": [r.to_dict() for r in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@username_bp.route("/<int:item_id>", methods=["GET"])
@jwt_required()
def get_username(item_id):
    user_id = int(get_jwt_identity())
    item = GeneratedUsername.query.filter_by(id=item_id, user_id=user_id).first()

    if not item:
        return jsonify({"message": "Not found"}), 404

    return jsonify({"data": item.to_dict()}), 200


@username_bp.route("/generate", methods=["POST"])
@jwt_required()
@limiter.limit("10 per minute;50 per day")
def generate():
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data:
        return jsonify({"message": "Request body is required"}), 400

    keyword = (data.get("keyword") or "").strip()
    style = (data.get("style") or "gaming").strip().lower()
    total = int(data.get("total", 5))

    if not keyword:
        return jsonify({"message": "keyword is required"}), 400

    if style not in VALID_STYLES:
        return jsonify({
            "message": f"Invalid style. Valid options: {', '.join(sorted(VALID_STYLES))}"
        }), 400

    total = max(1, min(total, 20))  # clamp 1–20

    try:
        result = generate_usernames(keyword, style, total)
    except Exception as e:
        logger.error("AI generation failed for user %s: %s", user_id, str(e))
        return jsonify({"message": "Failed to generate usernames. Please try again later."}), 500

    record = GeneratedUsername(
        user_id=user_id,
        keyword=keyword,
        style=style,
        total=total,
        usernames=json.dumps(result["usernames"]),
        description=result.get("description", ""),
    )

    db.session.add(record)
    db.session.commit()

    return jsonify({"data": record.to_dict()}), 200


@username_bp.route("/<int:item_id>", methods=["DELETE"])
@jwt_required()
def delete_username(item_id):
    user_id = int(get_jwt_identity())
    item = GeneratedUsername.query.filter_by(id=item_id, user_id=user_id).first()

    if not item:
        return jsonify({"message": "Not found"}), 404

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Deleted"}), 200
