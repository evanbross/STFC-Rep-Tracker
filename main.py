# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import datetime
import errno
import ipaddress
import logging.config
import os
import ssl
import subprocess
import sys
import threading
import time

import yaml
from flask import Flask
from werkzeug.serving import make_server

from app import screenshot_retention
from app.app_config import capture_cfg, screenshots_dir
from app.paths import is_frozen, resource_path, runtime_path
from app.request_guards import install_cross_origin_write_guard
from app.views.community_mod_view import community_mod_bp, max_payload_size
from app.views.validation import register_error_handlers
from app.win_process import SingleInstanceLock, is_admin, relaunch_as_admin
from config import AppSettings, load_settings

# Load .env if present (ignored in containers where vars are injected directly)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _check_env(app_settings: AppSettings) -> None:
    """Raise on startup if the database environment variables are not set."""
    missing = app_settings.missing_database_vars()  # ai: claude-opus-5-5 | 2026-11-06
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "  Copy .env.example to .env and fill in your values."
        )


def _build_frontend_if_needed() -> None:
    """Run 'npm run build' if any frontend source file is newer than dist/index.html."""
    if is_frozen():
        logger.info("running from packaged executable, skipping frontend build check")
        return

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


# ── Single-instance helpers ───────────────────────────────────────────────────
# Werkzeug's server (used by both app.run() below and _run_community_mod_https_server)
# sets allow_reuse_address on its listening socket, which on Windows lets a second
# backend process silently bind the same port instead of failing — see launcher.py's
# analogous guard. This mutex stops a second `main.py` instance (started via the
# launcher or directly, e.g. `python main.py`) before it ever reaches a bind() call.
_backend_lock = SingleInstanceLock("Global\\STFCRepTrackerBackend")  # ai: claude-opus-5-5 | 2026-11-06


# ai: claude-opus-5-5 | 2026-11-06
def _warm_ocr_reader() -> None:
    """Background thread: load the EasyOCR model now, so the first capture doesn't stall on it."""
    try:
        # Windows-only capture stack, imported here for the same reason create_app
        # imports capture_bp lazily: containers run without it (DISABLE_CAPTURE).
        from app.screen_processing.screen_capture import get_reader
        started = time.monotonic()
        get_reader()
        logger.info("OCR model loaded in %.1fs", time.monotonic() - started)
    except Exception:
        logger.exception("OCR warm-up failed; the model will load on first capture instead")


def _ensure_community_mod_cert(cert_dir: str) -> tuple[str, str]:
    """
    Return (cert_path, key_path), generating a self-signed certificate if either
    file is missing. The cert is valid for 10 years and covers localhost / 127.0.0.1.
    """
    os.makedirs(cert_dir, exist_ok=True)
    cert_path = os.path.join(cert_dir, "community_mod_cert.pem")
    key_path = os.path.join(cert_dir, "community_mod_key.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        logger.info("community-mod HTTPS: using existing cert at %s", cert_path)
        return cert_path, key_path

    logger.info("community-mod HTTPS: generating self-signed certificate in %s", cert_dir)
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    logger.info("community-mod HTTPS: certificate generated (valid 10 years)")
    return cert_path, key_path


# ai: claude-opus-5-5 | 2026-11-06
def create_community_mod_app() -> Flask:
    """Minimal app exposing only the community-mod blueprint, for the HTTPS listener.

    No CORS: the mod is not a browser page (captured requests carry no Origin),
    so nothing needs to read responses cross-origin. The write guard still
    rejects any browser page that tries to POST here.
    """
    https_app = Flask("community_mod_https")
    # This listener only takes community payloads, so cap every body at that size.
    https_app.config["MAX_CONTENT_LENGTH"] = max_payload_size() + 1
    install_cross_origin_write_guard(https_app, cors_origins=())
    https_app.register_blueprint(community_mod_bp, url_prefix="/api/community-mod")
    return https_app


# ai: claude-opus-5-5 | 2026-11-06
def _run_community_mod_https_server(cert_path: str, key_path: str, port: int = 7443) -> None:
    """Serve create_community_mod_app() over HTTPS on the configured bind host (loopback by default)."""
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(cert_path, key_path)

    bind_host = capture_cfg("community_mod", "bind_host", default="127.0.0.1")
    server = make_server(bind_host, port, create_community_mod_app(), ssl_context=ssl_ctx)
    logger.info("community-mod HTTPS server listening on https://%s:%d/api/community-mod", bind_host, port)
    server.serve_forever()


def create_app(app_settings: AppSettings):
    """Create and configure the Flask application."""
    from flasgger import Swagger
    from flask import redirect, send_from_directory
    from flask_cors import CORS

    from app.database.database import Database
    from app.views.calendar_view import calendar_bp
    from app.views.factions_view import factions_bp
    from app.views.reputations_view import reputations_bp
    from app.views.spocks_club_view import spocks_club_bp  # ai: claude-opus-5-5 | 2026-11-17
    from app.views.status_entries_view import status_entries_bp
    from app.views.target_types_view import target_types_bp
    from app.views.territory_view import territory_bp

    flask_app = Flask(
        __name__,
        template_folder=resource_path(os.path.join("frontend", "dist")),
        static_folder=resource_path(os.path.join("frontend", "dist")),
        static_url_path="/static",
    )
    flask_app.config.from_mapping(app_settings.flask_config())  # ai: claude-opus-5-5 | 2026-11-06
    CORS(flask_app, origins=flask_app.config["CORS_ORIGINS"])
    install_cross_origin_write_guard(flask_app, flask_app.config["CORS_ORIGINS"])  # ai: claude-opus-5-5 | 2026-11-06
    register_error_handlers(flask_app)  # ai: claude-opus-5-5 | 2026-11-06
    Swagger(flask_app)

    database = Database(flask_app.config["DATABASE_URL"], app_settings.database_url_direct)  # ai: claude-opus-5-5 | 2026-11-06
    flask_app.config["DATABASE"] = database

    flask_app.register_blueprint(calendar_bp, url_prefix="/api/calendar")
    # The capture blueprint imports Windows-only packages (pygetwindow, pyautogui,
    # pywin32) at module level.  Skip it when running in a container where those
    # packages are not installed.
    if not app_settings.disable_capture:  # ai: claude-opus-5-5 | 2026-11-06
        from app.views.capture_screen_view import capture_bp
        flask_app.register_blueprint(capture_bp, url_prefix="/api/capture-screen")
    flask_app.register_blueprint(community_mod_bp, url_prefix="/api/community-mod")
    flask_app.register_blueprint(status_entries_bp, url_prefix="/api/status_entries")
    flask_app.register_blueprint(factions_bp, url_prefix="/api/factions")
    flask_app.register_blueprint(reputations_bp, url_prefix="/api/reputations")
    flask_app.register_blueprint(spocks_club_bp, url_prefix="/api/spocks-club")  # ai: claude-opus-5-5 | 2026-11-17
    flask_app.register_blueprint(target_types_bp, url_prefix="/api/target-types")
    flask_app.register_blueprint(territory_bp, url_prefix="/api/territory")

    @flask_app.route("/swagger")
    def swagger_alias():
        return redirect("/apidocs")

    @flask_app.route("/", defaults={"path": ""})
    @flask_app.route("/<path:path>")
    def serve_react(path):
        """Serve the React app's index.html for all frontend routes"""
        if path and os.path.exists(os.path.join(flask_app.static_folder, path)):
            return send_from_directory(flask_app.static_folder, path)
        return send_from_directory(flask_app.static_folder, "index.html")

    return flask_app


with open(resource_path("logging.yaml"), encoding="utf-8") as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)


# ai: claude-opus-5-5 | 2026-11-06
def create_wsgi_app() -> Flask:
    """App factory for WSGI servers (gunicorn "main:create_wsgi_app()") and tests.

    Importing main has no side effects beyond logging setup: the schema init
    and connection pool start only when an app is actually built.
    """
    app_settings = load_settings()
    _check_env(app_settings)
    return create_app(app_settings)


# ai: claude-opus-5-5 | 2026-11-06
def _serve() -> None:
    """Desktop entry point. Cheap checks run first, so a duplicate or
    about-to-relaunch process exits before any network or model work (N-P4):
    single-instance lock -> elevation -> env check -> create_app -> listeners.
    """
    if not _backend_lock.acquire():
        logger.error(
            "Another STFC Rep Tracker backend instance is already running — "
            "exiting instead of racing it for ports 7300/7443."
        )
        sys.exit(1)

    app_settings = load_settings()
    debug = app_settings.flask_env == "development"
    if not debug and not is_admin():
        logger.info("Not running as administrator — relaunching with elevation")
        relaunch_as_admin(_backend_lock)

    _check_env(app_settings)
    flask_app = create_app(app_settings)
    screenshot_retention.start(screenshots_dir())  # ai: claude-opus-5-5 | 2026-11-06 — signalled by writers (R11)

    cert_path, key_path = _ensure_community_mod_cert(runtime_path("certs"))
    threading.Thread(target=_run_community_mod_https_server, args=(cert_path, key_path), daemon=True).start()

    if not app_settings.disable_capture:
        threading.Thread(target=_warm_ocr_reader, name="ocr-warmup", daemon=True).start()

    _build_frontend_if_needed()
    port = app_settings.port
    try:
        flask_app.run(debug=debug, port=port, use_reloader=False)
    except OSError as e:
        # WSAEACCES (10013) on Windows means the port is either in use or in the
        # system's excluded port range.  Give a concrete, actionable message.
        if e.errno in (errno.EACCES, 10013):
            logger.error(
                f"Cannot bind to port {port}: access denied.\n"
                f"  Another application is likely using port {port}, or Windows has excluded it.\n"
                f"  Run:  netstat -ano | findstr :{port}  to find the conflicting process.\n"
                f"  Then kill it with:  taskkill /PID <pid> /F\n"
                f"  Or check excluded ranges with:  netsh int ipv4 show excludedportrange protocol=tcp"
            )
        else:
            logger.error(f"Failed to start server on port {port}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    _serve()
