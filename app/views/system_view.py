import os

from flask import Blueprint, current_app, redirect, send_from_directory

system_bp = Blueprint("system", __name__)


@system_bp.route("/api/swagger", methods=["GET"])
def swagger_redirect():
    return redirect("/apidocs")


@system_bp.route("/swagger", methods=["GET"])
def top_swagger_redirect():
    return redirect("/apidocs")


@system_bp.route("/", defaults={"path": ""})
@system_bp.route("/<path:path>")
def serve_react(path):
    dist_dir = current_app.template_folder
    if path != "" and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    else:
        return send_from_directory(dist_dir, "index.html")
