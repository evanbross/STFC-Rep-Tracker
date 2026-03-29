import ctypes
import logging
import logging.config
import os
import subprocess
import sys

import yaml
from flasgger import Swagger
from flask import Flask, send_from_directory
from flask_cors import CORS

from app.database.database import Database
from app.views.capture_screen_view import capture_bp
from app.views.factions_view import factions_bp
from app.views.reputations_view import reputations_bp
from app.views.status_entries_view import status_entries_bp
from app.views.system_view import system_bp
from config import get_config

with open("logging.yaml") as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder="frontend/dist",
    static_folder="frontend/dist",
    static_url_path="/static",
)
app.config.from_object(get_config())
CORS(app, origins=app.config["CORS_ORIGINS"])
swagger = Swagger(app)
db = Database(app.config["DATABASE_PATH"])
app.config["DATABASE"] = db
app.register_blueprint(capture_bp, url_prefix="/api/capture-screen")
app.register_blueprint(status_entries_bp, url_prefix="/api/status_entries")
app.register_blueprint(factions_bp, url_prefix="/api/factions")
app.register_blueprint(reputations_bp, url_prefix="/api/reputations")
app.register_blueprint(system_bp, url_prefix="/api/system")



@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """Serve the React app's index.html for all frontend routes"""
    # If the path starts with 'api/', Flask will use the API routes instead of this catch-all
    # If the path is a file that exists in the static folder, Flask will serve it
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


def _build_frontend_if_needed():
    """Run 'npm run build' if any frontend source file is newer than dist/index.html."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    dist_index = os.path.join(project_root, "frontend", "dist", "index.html")
    watch_paths = [
        os.path.join(project_root, "frontend", "src"),
        os.path.join(project_root, "frontend", "index.html"),
        os.path.join(project_root, "frontend", "vite.config.js"),
        os.path.join(project_root, "frontend", "package.json"),
    ]

    needs_build = not os.path.exists(dist_index)
    if not needs_build:
        dist_mtime = os.path.getmtime(dist_index)
        for watch_path in watch_paths:
            if not os.path.exists(watch_path):
                continue
            if os.path.isfile(watch_path):
                if os.path.getmtime(watch_path) > dist_mtime:
                    logger.info(f"frontend rebuild needed: {os.path.basename(watch_path)} is newer than dist")
                    needs_build = True
                    break
            else:
                for dirpath, _, filenames in os.walk(watch_path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        if os.path.getmtime(filepath) > dist_mtime:
                            rel = os.path.relpath(filepath, project_root)
                            logger.info(f"frontend rebuild needed: {rel} is newer than dist")
                            needs_build = True
                            break
                    if needs_build:
                        break
            if needs_build:
                break

    if not needs_build:
        logger.info("frontend is up to date, skipping build")
        return

    frontend_dir = os.path.join(project_root, "frontend")
    logger.info("building frontend (npm run build)...")
    result = subprocess.run(
        "npm run build",
        cwd=frontend_dir,
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"npm run build failed:\n{result.stderr}")
    else:
        logger.info("frontend build completed successfully")


def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def _relaunch_as_admin():
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    sys.exit(0)


if __name__ == "__main__":
    if not app.config["DEBUG"] and not _is_admin():
        logger.info("Not running as administrator — relaunching with elevation")
        _relaunch_as_admin()
    _build_frontend_if_needed()
    app.run(debug=app.config["DEBUG"], port=5000)
