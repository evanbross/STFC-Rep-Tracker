from flask import Blueprint, redirect

system_bp = Blueprint("system", __name__)


@system_bp.route("/api/swagger", methods=["GET"])
def swagger_redirect():
    return redirect("/apidocs")


@system_bp.route("/swagger", methods=["GET"])
def top_swagger_redirect():
    return redirect("/apidocs")
