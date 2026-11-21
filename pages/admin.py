from flask import Blueprint, request, jsonify, render_template
import config
from store import orders

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_ok():
    return bool(config.ADMIN_KEY) and request.args.get("key") == config.ADMIN_KEY


@bp.route("/data")
def data():
    if not admin_ok():
        return jsonify(error="Not allowed"), 403
    rows = [dict(ref=ref, **o) for ref, o in orders.items()]
    rows.reverse()
    paid = [o for o in rows if o["status"] == "SUCCESS"]
    return jsonify(
        orders=rows,
        total_count=len(rows),
        paid_count=len(paid),
        revenue=sum(o["total"] for o in paid),
    )


@bp.route("")
@bp.route("/")
def dashboard():
    if not admin_ok():
        return "Not allowed", 403
    return render_template("admin.html")
