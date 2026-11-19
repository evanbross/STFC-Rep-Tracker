# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
import ctypes
import os
import runpy
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import messagebox, scrolledtext, ttk

from app.paths import is_frozen, runtime_dir
from app.win_process import SingleInstanceLock, is_admin, relaunch_as_admin

# ── Constants ─────────────────────────────────────────────────────────────────

_HERE = runtime_dir()  # ai: claude-opus-5-5 | 2026-11-06
_PREFERRED_PORT = 7300
_BACKEND_ARG = "--backend"
_launcher_lock = SingleInstanceLock("Global\\STFCRepTrackerLauncher")  # ai: claude-opus-5-5 | 2026-11-06

# ai: claude-opus-5-5 | 2026-11-12
# Shared dev-Caddy client from the zt-common package (../infra/zt-common), installed
# as an editable *dev* dependency. Optional on purpose: the installed app
# (embedded Python + requirements.txt, exported with --no-dev) doesn't have it,
# and there's no dev Caddy on a user's machine anyway.
try:
    from zt_common import caddy_registry as _caddy_registry
except ImportError:
    _caddy_registry = None

_BG = "#1a1a2e"
_FG = "#cfd8dc"
_ACCENT = "#00b4d8"
_MUTED = "#607d8b"
_ENTRY_BG = "#263238"
_LOG_BG = "#10101c"
_LOG_FG = "#a5d6a7"
_MAX_LOG_LINES = 2000

# Keys we require the user to fill in, with user-facing help text.
_SETUP_FIELDS: list[tuple[str, str, str]] = [
    (
        "DATABASE_URL_POOLED",
        "PostgreSQL pooled connection string",
        "From your database provider (e.g. Neon: console.neon.tech → project → Connection Details → Pooled).",
    ),
    (
        "DATABASE_URL_DIRECT",
        "PostgreSQL direct connection string",
        "Same page — toggle 'Connection pooling' off to get the direct URL.",
    ),
    (
        "SECRET_KEY",
        "Flask secret key",
        "Secures session cookies. Click Generate for a random value, or paste your own.",
    ),
]

# Substrings that identify a value as an unfilled placeholder.
_PLACEHOLDER_MARKERS = ("USER", "PASSWORD", "HOST", "DBNAME", "change-me-in-production")


# ── .env helpers ──────────────────────────────────────────────────────────────

def _parse_env_file(path: str) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    data[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return data


def _update_env_file(path: str, updates: dict[str, str]) -> None:
    """Write `updates` into the .env file, preserving existing comments and keys."""
    lines: list[str] = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

    written: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                written.add(key)
                continue
        new_lines.append(line)

    for key, val in updates.items():
        if key not in written:
            new_lines.append(f"{key}={val}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def _is_placeholder(value: str) -> bool:
    return not value or any(marker in value for marker in _PLACEHOLDER_MARKERS)


def _needs_setup(env_data: dict[str, str]) -> bool:
    return any(_is_placeholder(env_data.get(key, "")) for key, _, _ in _SETUP_FIELDS)


# ── Single-instance helpers ───────────────────────────────────────────────────

def _warn_already_running_and_exit() -> None:
    ctypes.windll.user32.MessageBoxW(
        0,
        "STFC Rep Tracker is already running. Check your taskbar for the existing window.",
        "STFC Rep Tracker",
        0x40,  # MB_ICONINFORMATION
    )
    sys.exit(0)


def _run_backend_child() -> None:
    sys.argv = ["main.py"]
    runpy.run_module("main", run_name="__main__")


# ── Port / server helpers ─────────────────────────────────────────────────────

def _find_free_port(start: int = _PREFERRED_PORT, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    # Fallback: let the OS assign any available port
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
    except OSError as exc:
        raise RuntimeError(
            f"No free port found in range {start}–{start + attempts - 1} and OS fallback "
            f"also failed: {exc}\n"
            "Diagnostic: run  netsh int ipv4 show excludedportrange protocol=tcp\n"
            "If Winsock is corrupt: run  netsh winsock reset  then reboot."
        ) from exc


def _wait_for_server(port: int, timeout: int = 60) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False



# ── Setup dialog ──────────────────────────────────────────────────────────────

class SetupDialog(tk.Toplevel):
    """Modal first-time-setup dialog that populates missing .env values."""

    def __init__(self, parent: tk.Tk, env_path: str, env_data: dict[str, str]) -> None:
        super().__init__(parent)
        self._env_path = env_path
        self._env_data = env_data
        self.result: dict[str, str] | None = None

        self.title("STFC Rep Tracker — First-Time Setup")
        self.resizable(False, False)
        self.configure(bg=_BG)
        self.grab_set()
        self.focus_set()

        self._vars: dict[str, tk.StringVar] = {}
        self._build_ui()
        self._center_on(parent)

    def _build_ui(self) -> None:
        title_font = tkfont.Font(family="Segoe UI", size=12, weight="bold")
        label_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        help_font = tkfont.Font(family="Segoe UI", size=8)
        entry_font = tkfont.Font(family="Consolas", size=9)

        outer = tk.Frame(self, bg=_BG, padx=24, pady=16)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="First-Time Setup", font=title_font, fg=_ACCENT, bg=_BG).pack(anchor="w")
        tk.Label(
            outer,
            text=(
                "The app needs a few values before it can start.\n"
                "These are saved to .env in the install folder and never leave your machine."
            ),
            font=help_font,
            fg=_MUTED,
            bg=_BG,
            justify="left",
            wraplength=480,
        ).pack(anchor="w", pady=(4, 14))

        for key, label, help_text in _SETUP_FIELDS:
            current = self._env_data.get(key, "")
            initial = "" if _is_placeholder(current) else current

            var = tk.StringVar(value=initial)
            self._vars[key] = var

            tk.Label(outer, text=label, font=label_font, fg=_FG, bg=_BG).pack(anchor="w")

            row = tk.Frame(outer, bg=_BG)
            row.pack(fill="x", pady=(3, 0))

            entry = tk.Entry(
                row,
                textvariable=var,
                font=entry_font,
                bg=_ENTRY_BG,
                fg="#eceff1",
                insertbackground="#eceff1",
                relief="flat",
                width=54,
            )
            entry.pack(side="left", fill="x", expand=True, ipady=5)

            if key == "SECRET_KEY":
                ttk.Button(
                    row,
                    text="Generate",
                    command=lambda v=var: v.set(secrets.token_hex(32)),
                ).pack(side="left", padx=(8, 0))

            tk.Label(
                outer,
                text=help_text,
                font=help_font,
                fg=_MUTED,
                bg=_BG,
                justify="left",
                wraplength=480,
            ).pack(anchor="w", pady=(3, 12))

        sep = ttk.Separator(outer, orient="horizontal")
        sep.pack(fill="x", pady=(4, 12))

        btn_row = tk.Frame(outer, bg=_BG)
        btn_row.pack(fill="x")

        tk.Label(
            btn_row,
            text="You can edit .env manually at any time to change these values.",
            font=help_font,
            fg=_MUTED,
            bg=_BG,
        ).pack(side="left")

        ttk.Button(
            btn_row,
            text="Save & Start",
            style="Action.TButton",
            command=self._save,
        ).pack(side="right")

    def _save(self) -> None:
        updates: dict[str, str] = {}
        missing: list[str] = []

        for key, label, _ in _SETUP_FIELDS:
            val = self._vars[key].get().strip()
            if not val:
                missing.append(label)
            else:
                updates[key] = val

        if missing:
            messagebox.showwarning(
                "Missing Values",
                "Please fill in all fields before continuing:\n\n" + "\n".join(f"• {m}" for m in missing),
                parent=self,
            )
            return

        _update_env_file(self._env_path, updates)
        self.result = updates
        self.destroy()

    def _center_on(self, parent: tk.Tk) -> None:
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")


# ── Main launcher window ──────────────────────────────────────────────────────

class LauncherWindow:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._process: subprocess.Popen | None = None
        self._port: int | None = None
        self._restart_btn: ttk.Button | None = None
        self._app_url: str | None = None
        self._caddy_app_name: str = "stfc"

        self._configure_styles()
        self._build_ui()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Defer config check so the window is visible before any dialogs appear.
        root.after(150, self._ensure_config)

    # ── Styles ────────────────────────────────────────────────────────────────

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Action.TButton",
            font=("Segoe UI", 10),
            padding=(10, 5),
            background=_ACCENT,
            foreground=_BG,
        )
        style.configure(
            "Stop.TButton",
            font=("Segoe UI", 10),
            padding=(10, 5),
            background="#455a64",
            foreground="#ffffff",
        )

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.title("STFC Rep Tracker")
        self.root.resizable(True, True)
        self.root.configure(bg=_BG)

        title_font = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        status_font = tkfont.Font(family="Segoe UI", size=10)

        tk.Label(self.root, text="STFC Rep Tracker", font=title_font, fg=_ACCENT, bg=_BG).pack(
            fill="x", padx=20, pady=(14, 6)
        )

        self._status_var = tk.StringVar(value="Initialising…")
        tk.Label(
            self.root,
            textvariable=self._status_var,
            font=status_font,
            fg=_FG,
            bg=_BG,
            width=44,
            anchor="w",
        ).pack(fill="x", padx=20)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=20, pady=10)

        btn_frame = tk.Frame(self.root, bg=_BG)
        btn_frame.pack(padx=20, pady=(0, 18))

        self._open_btn = ttk.Button(
            btn_frame,
            text="Open Browser",
            style="Action.TButton",
            command=self._open_browser,
            state="disabled",
        )
        self._open_btn.grid(row=0, column=0, padx=(0, 8))

        self._restart_btn = ttk.Button(
            btn_frame,
            text="Restart",
            style="Stop.TButton",
            command=self._restart_backend,
            state="disabled",
        )
        self._restart_btn.grid(row=0, column=1, padx=(0, 8))

        ttk.Button(btn_frame, text="Stop", style="Stop.TButton", command=self._on_close).grid(row=0, column=2)

        # ai: claude-sonnet-5 | 2026-08-01
        tk.Label(self.root, text="Console Output", font=status_font, fg=_MUTED, bg=_BG, anchor="w").pack(
            fill="x", padx=20
        )

        log_frame = tk.Frame(self.root, bg=_BG)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(4, 14))

        self._log_widget = scrolledtext.ScrolledText(
            log_frame,
            height=18,
            width=90,
            bg=_LOG_BG,
            fg=_LOG_FG,
            insertbackground=_LOG_FG,
            font=tkfont.Font(family="Consolas", size=9),
            relief="flat",
            state="disabled",
            wrap="word",
        )
        self._log_widget.pack(fill="both", expand=True)

    # ── Config / first-run ────────────────────────────────────────────────────

    def _ensure_config(self) -> None:
        """Copy example files if absent, then show setup dialog if .env has placeholders."""
        env_path = os.path.join(_HERE, ".env")
        env_example = os.path.join(_HERE, ".env.example")
        settings_path = os.path.join(_HERE, "settings.yaml")
        settings_example = os.path.join(_HERE, "settings.yaml.example")

        # Silently copy example files for any that are missing.
        if not os.path.exists(settings_path) and os.path.exists(settings_example):
            shutil.copy2(settings_example, settings_path)

        if not os.path.exists(env_path) and os.path.exists(env_example):
            shutil.copy2(env_example, env_path)

        env_data = _parse_env_file(env_path)
        self._caddy_app_name = env_data.get("CADDY_APP_NAME", "stfc")

        if _needs_setup(env_data):
            self._status_var.set("Setup required — please fill in the configuration.")
            dialog = SetupDialog(self.root, env_path, env_data)
            self.root.wait_window(dialog)

            if dialog.result is None:
                # User closed the dialog without saving.
                self._status_var.set("Setup cancelled. Close this window to exit.")
                return

        threading.Thread(target=self._start_backend, daemon=True).start()

    # ── Backend lifecycle ─────────────────────────────────────────────────────

    def _start_backend(self) -> None:
        try:
            port = _find_free_port()
            self._port = port
            self._set_status(f"Starting server on port {port}…")
            self.root.after(0, lambda: self._open_btn.config(state="disabled"))
            self.root.after(0, lambda: self._set_restart_button_state("disabled"))
            self.root.after(0, self._clear_log)

            env = os.environ.copy()
            env["PORT"] = str(port)

            if is_frozen():
                command = [sys.executable, _BACKEND_ARG]
            else:
                python = os.path.join(_HERE, "python", "python.exe")
                if not os.path.exists(python):
                    python = sys.executable
                command = [python, os.path.join(_HERE, "main.py")]

            log_path = os.path.join(_HERE, "server.log")
            self._process = subprocess.Popen(
                command,
                env=env,
                cwd=_HERE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            threading.Thread(
                target=self._pump_output, args=(self._process, log_path), daemon=True
            ).start()

            self._set_status(f"Waiting for server on port {port}…")
            if _wait_for_server(port):
                url, caddy_ok = self._resolve_app_url(port)
                self.root.after(0, lambda: self._on_server_ready(url, caddy_ok))
            else:
                self._set_status("Server did not start — check server.log for details.")
                self.root.after(0, lambda: self._set_restart_button_state("normal"))
        except Exception as exc:
            self._set_status(f"Error: {exc}")
            self.root.after(0, lambda: self._set_restart_button_state("normal"))

    # ai: claude-sonnet-5 | 2026-07-31
    def _resolve_app_url(self, port: int) -> tuple[str, bool]:
        """Attempt Caddy registration and return (url, caddy_ok).

        caddy_ok reflects whether register() actually succeeded, not just
        whether the caddy_registry module imported — a prior version of this
        code conflated the two, which let the UI show/open http://<name>.localhost
        even when Caddy never registered the route (e.g. Caddy started after
        this app, or isn't running at all).
        """
        caddy_ok = _caddy_registry is not None and _caddy_registry.register(
            self._caddy_app_name, port
        )
        url = (
            f"http://{self._caddy_app_name}.localhost"
            if caddy_ok
            else f"http://localhost:{port}"
        )
        return url, caddy_ok

    def _on_server_ready(self, url: str, caddy_ok: bool) -> None:
        self._app_url = url
        suffix = "" if caddy_ok else " — Caddy unavailable, using direct port"
        self._status_var.set(f"Now running on {url} (using port {self._port}){suffix}")
        self._open_btn.config(state="normal")
        self._set_restart_button_state("normal")

    # ── Actions ───────────────────────────────────────────────────────────────

    # ai: claude-sonnet-5 | 2026-07-31
    def _open_browser(self) -> None:
        # Re-resolve on each click (not a background poll — only runs on this
        # explicit user action) so a Caddy stack that started late is picked
        # up without requiring an app restart.
        if self._port is not None:
            url, caddy_ok = self._resolve_app_url(self._port)
            self._on_server_ready(url, caddy_ok)
        if self._app_url:
            webbrowser.open(self._app_url)

    def _restart_backend(self) -> None:
        self._open_btn.config(state="disabled")
        self._set_restart_button_state("disabled")
        self._status_var.set("Restarting server…")
        threading.Thread(target=self._restart_backend_worker, daemon=True).start()

    def _restart_backend_worker(self) -> None:
        self._stop_backend()
        self._start_backend()

    def _on_close(self) -> None:
        self._stop_backend()
        self.root.destroy()

    def _stop_backend(self) -> None:
        if _caddy_registry is not None:
            _caddy_registry.deregister(self._caddy_app_name)
        self._app_url = None
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._process = None
        self._port = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str) -> None:
        self.root.after(0, lambda: self._status_var.set(msg))

    def _set_restart_button_state(self, state: str) -> None:
        if self._restart_btn:
            self._restart_btn.config(state=state)

    # ai: claude-sonnet-5 | 2026-08-01
    def _pump_output(self, process: subprocess.Popen, log_path: str) -> None:
        """Tee the child process's stdout/stderr to server.log and the console pane."""
        with open(log_path, "w", encoding="utf-8") as log_file:
            assert process.stdout is not None
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
                self.root.after(0, self._append_log, line)
        process.stdout.close()

    def _append_log(self, line: str) -> None:
        self._log_widget.configure(state="normal")
        self._log_widget.insert("end", line)
        line_count = int(self._log_widget.index("end-1c").split(".")[0])
        if line_count > _MAX_LOG_LINES:
            self._log_widget.delete("1.0", f"{line_count - _MAX_LOG_LINES}.0")
        self._log_widget.see("end")
        self._log_widget.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_widget.configure(state="normal")
        self._log_widget.delete("1.0", "end")
        self._log_widget.configure(state="disabled")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if _BACKEND_ARG in sys.argv:
        _run_backend_child()
        return

    if not is_admin():
        relaunch_as_admin()
        return

    if not _launcher_lock.acquire():
        _warn_already_running_and_exit()
        return

    root = tk.Tk()
    LauncherWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
