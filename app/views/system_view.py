from flask import Blueprint, Response, redirect

system_bp = Blueprint("system", __name__)


@system_bp.route("/swagger", methods=["GET"])
def swagger_redirect() -> Response:
    return redirect("/apidocs")
