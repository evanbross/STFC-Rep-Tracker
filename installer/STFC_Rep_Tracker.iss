; ============================================================
; STFC Rep Tracker — Inno Setup Script
;
; Prerequisites (run installer\prepare.bat first):
;   installer\python-3.12.9-embed-amd64.zip
;   installer\get-pip.py
;   installer\requirements_dist.txt
;   frontend\dist\  (built by npm run build)
; ============================================================

#define AppName    "STFC Rep Tracker"
#define AppVersion "1.0.0"
#define AppExeName "run.bat"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL=https://github.com
DefaultDirName={autopf64}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=dist
OutputBaseFilename=STFC_Rep_Tracker_Setup
Compression=lzma2/ultra64
SolidCompression=yes
; Admin required: app uses win32 window activation APIs
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
; Show a progress page for the long-running [Run] steps
ShowComponentSizes=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; ── Application source ────────────────────────────────────────────────────────
; Exclude dev-only folders and build artefacts.
Source: "..\*.py";                  DestDir: "{app}"; Flags: ignoreversion
Source: "..\run.bat";               DestDir: "{app}"; Flags: ignoreversion
; Ship example files only — the launcher copies them to the real paths on first run.
; Never bundle .env (credentials) or settings.yaml (personal config).
Source: "..\*.example";             DestDir: "{app}"; Flags: ignoreversion
; logging.yaml is not personal — bundle it directly.
Source: "..\logging.yaml";          DestDir: "{app}"; Flags: ignoreversion
; requirements.txt is referenced by some tooling but contains no credentials.
Source: "..\requirements*.txt";     DestDir: "{app}"; Flags: ignoreversion
Source: "..\app\*";          DestDir: "{app}\app";               Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "..\frontend\dist\*";DestDir: "{app}\frontend\dist";    Flags: ignoreversion recursesubdirs createallsubdirs

; ── Python embeddable (extracted to {app}\python at install time) ─────────────
Source: "python-3.12.9-embed-amd64.zip"; DestDir: "{tmp}"; Flags: deleteafterinstall

; ── pip bootstrap ─────────────────────────────────────────────────────────────
Source: "get-pip.py"; DestDir: "{tmp}"; Flags: deleteafterinstall

; ── Filtered requirements (torch/torchvision excluded — installed separately) ─
Source: "requirements_dist.txt"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#AppName}";      Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
; ── Step 1: Extract Python embeddable ────────────────────────────────────────
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Expand-Archive -Path '{tmp}\python-3.12.9-embed-amd64.zip' -DestinationPath '{app}\python' -Force"""; \
  StatusMsg: "Extracting Python runtime..."; \
  Flags: runhidden waituntilterminated

; ── Step 2: Enable site-packages in the _pth file ────────────────────────────
; The embeddable zip ships with 'import site' commented out, which blocks pip.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Get-ChildItem '{app}\python\*._pth' | ForEach-Object { (Get-Content $_) -replace '#import site','import site' | Set-Content $_ }"""; \
  StatusMsg: "Configuring Python runtime..."; \
  Flags: runhidden waituntilterminated

; ── Step 3: Bootstrap pip ────────────────────────────────────────────────────
Filename: "{app}\python\python.exe"; \
  Parameters: "{tmp}\get-pip.py --no-warn-script-location --quiet"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Installing pip..."; \
  Flags: runhidden waituntilterminated

; ── Step 4: Install PyTorch CPU-only ─────────────────────────────────────────
; Uses the PyTorch CPU wheel index to avoid downloading the ~2 GB CUDA build.
Filename: "{app}\python\python.exe"; \
  Parameters: "-m pip install torch==2.10.0+cpu torchvision==0.25.0+cpu --index-url https://download.pytorch.org/whl/cpu --no-warn-script-location --quiet"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Installing PyTorch (CPU) — this may take a few minutes..."; \
  Flags: waituntilterminated

; ── Step 5: Install remaining Python dependencies ────────────────────────────
Filename: "{app}\python\python.exe"; \
  Parameters: "-m pip install -r {tmp}\requirements_dist.txt --no-warn-script-location --quiet"; \
  WorkingDir: "{app}"; \
  StatusMsg: "Installing Python dependencies — this may take several minutes..."; \
  Flags: waituntilterminated

; ── Step 6: Download EasyOCR language models (~100 MB) ───────────────────────
Filename: "{app}\python\python.exe"; \
  Parameters: "-c ""import easyocr; easyocr.Reader(['en'], gpu=False)"""; \
  WorkingDir: "{app}"; \
  StatusMsg: "Downloading EasyOCR language models (~100 MB) — please wait..."; \
  Flags: waituntilterminated

[UninstallDelete]
; Remove the Python runtime we installed (not tracked by Inno Setup as individual files)
Type: filesandordirs; Name: "{app}\python"
; Remove runtime-generated files (not tracked as installed files)
Type: filesandordirs; Name: "{app}\Screenshots"
Type: files;          Name: "{app}\server.log"
Type: files;          Name: "{app}\.env"
Type: files;          Name: "{app}\settings.yaml"
Type: files;          Name: "{app}\google_token.json"
