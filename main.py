import ctypes
import logging
import logging.config
import os
import subprocess
import sys
import threading
import time

import yaml

# Load .env if present (ignored in containers where vars are injected directly)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _screenshots_cleanup_worker(folder: str, keep: int = 30, interval: int = 300) -> None:
    """Background thread: every `interval` seconds, delete oldest files in `folder` beyond `keep`."""
    while True:
        try:
            files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.isfile(os.path.join(folder, f))
            ]
            if len(files) > keep:
                files.sort(key=os.path.getmtime)
                for path in files[:len(files) - keep]:
                    os.remove(path)
                    logger.debug(f"Screenshots cleanup: deleted {path}")
        except Exception:
            logger.exception("Screenshots cleanup thread encountered an error")
        time.sleep(interval)


def _check_env() -> None:
    """Raise on startup if expected environment variables are not set."""
    required = ["DATABASE_URL_POOLED", "DATABASE_URL_DIRECT"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "  Copy .env.example to .env and fill in your values."
        )


def _build_frontend_if_needed() -> None:
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


def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def _relaunch_as_admin() -> None:
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    sys.exit(0)


def create_app():
    """Create and configure the Flask application."""
    from flasgger import Swagger
    from flask import Flask, send_from_directory
    from flask_cors import CORS

    from app.database.database import Database
    from app.views.calendar_view import calendar_bp
    from app.views.capture_screen_view import capture_bp
    from app.views.factions_view import factions_bp
    from app.views.reputations_view import reputations_bp
    from app.views.status_entries_view import status_entries_bp
    from app.views.system_view import system_bp
    from app.views.territory_view import territory_bp
    from config import get_config

    flask_app = Flask(
        __name__,
        template_folder="frontend/dist",
        static_folder="frontend/dist",
        static_url_path="/static",
    )
    flask_app.config.from_object(get_config())
    CORS(flask_app, origins=flask_app.config["CORS_ORIGINS"])
    Swagger(flask_app)

    database = Database(flask_app.config["DATABASE_URL"])
    flask_app.config["DATABASE"] = database

    flask_app.register_blueprint(calendar_bp, url_prefix="/api/calendar")
    flask_app.register_blueprint(capture_bp, url_prefix="/api/capture-screen")
    flask_app.register_blueprint(status_entries_bp, url_prefix="/api/status_entries")
    flask_app.register_blueprint(factions_bp, url_prefix="/api/factions")
    flask_app.register_blueprint(reputations_bp, url_prefix="/api/reputations")
    flask_app.register_blueprint(system_bp, url_prefix="/api/system")
    flask_app.register_blueprint(territory_bp, url_prefix="/api/territory")

    @flask_app.route("/", defaults={"path": ""})
    @flask_app.route("/<path:path>")
    def serve_react(path):
        """Serve the React app's index.html for all frontend routes"""
        if path and os.path.exists(os.path.join(flask_app.static_folder, path)):
            return send_from_directory(flask_app.static_folder, path)
        return send_from_directory(flask_app.static_folder, "index.html")

    return flask_app


with open("logging.yaml") as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

app = create_app()

if __name__ == "__main__":
    _check_env()
    screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Screenshots")
    t = threading.Thread(target=_screenshots_cleanup_worker, args=(screenshots_dir,), daemon=True)
    t.start()
    if not app.config["DEBUG"] and not _is_admin():
        logger.info("Not running as administrator — relaunching with elevation")
        _relaunch_as_admin()
    _build_frontend_if_needed()
    app.run(debug=app.config["DEBUG"], port=5000)
