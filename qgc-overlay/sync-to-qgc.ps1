# Syncs the overlay into the upstream QGC clone's custom/ directory.
# Usage: .\sync-to-qgc.ps1 [-QgcRoot C:\dev\qgroundcontrol]
# After the FIRST sync (or any CMakeLists/CustomOverrides change), reconfigure;
# for QML/C++-only changes an incremental build suffices.
param(
    [string]$QgcRoot = 'C:\dev\qgroundcontrol'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path (Join-Path $QgcRoot 'CMakeLists.txt'))) {
    throw "QGC source tree not found at $QgcRoot"
}

$src = Join-Path $PSScriptRoot 'custom'
$dst = Join-Path $QgcRoot 'custom'

# /MIR mirrors exactly (deletes files removed from the overlay)
robocopy $src $dst /MIR /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with code $LASTEXITCODE" }

Write-Output "Overlay synced: $src -> $dst"
exit 0  # robocopy exit codes 1-7 mean success; don't leak them
