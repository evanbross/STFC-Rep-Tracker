$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$python = Join-Path $here "python\pythonw.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $here ".venv\Scripts\pythonw.exe"
}

& $python (Join-Path $here "launcher.py")
