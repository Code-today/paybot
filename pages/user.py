from flask import Blueprint, render_template
from mockdata.menu import MENU

bp = Blueprint("user", __name__)


@bp.route("/")
def home():
    return render_template("user.html", menu=MENU)
