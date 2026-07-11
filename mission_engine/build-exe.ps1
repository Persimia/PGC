# Freezes the mission engine into a standalone directory build (PyInstaller
# onedir: faster per-invocation startup than onefile, which re-extracts on
# every run - the Solar Scan item invokes the engine on every regenerate).
#
# Output:  dist\mission-engine\mission-engine.exe
# Stage:   pass -StageTo to copy the result next to a QGC build, e.g.
#          .\build-exe.ps1 -StageTo C:\dev\qgc-build\Release
#          which creates <StageTo>\pgc-engine\mission-engine.exe
#
# Code signing (R3) happens in the packaging phase, not here.
param(
    [string]$StageTo = ''
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

& .\.venv\Scripts\python.exe -m pip install --quiet pyinstaller
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onedir --console `
    --name mission-engine `
    --distpath dist `
    pyinstaller_entry.py
if ($LASTEXITCODE -ne 0) { exit 1 }

& .\dist\mission-engine\mission-engine.exe --help | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Output 'smoke test failed'; exit 1 }
Write-Output "built: $PSScriptRoot\dist\mission-engine\mission-engine.exe"

if ($StageTo) {
    if (-not (Test-Path $StageTo)) { Write-Output "stage target missing: $StageTo"; exit 1 }
    $dst = Join-Path $StageTo 'pgc-engine'
    robocopy .\dist\mission-engine $dst /MIR /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { Write-Output 'robocopy failed'; exit 1 }
    Write-Output "staged: $dst\mission-engine.exe"
}
exit 0
