$ErrorActionPreference = "Stop"
python "$PSScriptRoot\setup.py" @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
