# Applies the PGC carried patches to a fresh QGC clone. Idempotent: patches
# already applied are skipped; a patch that no longer applies cleanly fails
# loudly (upstream moved - re-derive it, see README "Carried patches").
# Usage: .\apply-patches.ps1 [-QgcRoot C:\dev\qgroundcontrol]
param(
    [string]$QgcRoot = 'C:\dev\qgroundcontrol'
)

if (-not (Test-Path (Join-Path $QgcRoot 'CMakeLists.txt'))) {
    Write-Output "QGC source tree not found at $QgcRoot"
    exit 1
}

$patches = Get-ChildItem (Join-Path $PSScriptRoot 'patches') -Filter '*.patch' | Sort-Object Name
$failed = $false

foreach ($patch in $patches) {
    cmd /c "git -C `"$QgcRoot`" apply --check `"$($patch.FullName)`" 2>nul"
    if ($LASTEXITCODE -eq 0) {
        cmd /c "git -C `"$QgcRoot`" apply `"$($patch.FullName)`""
        Write-Output "applied: $($patch.Name)"
        continue
    }

    cmd /c "git -C `"$QgcRoot`" apply --reverse --check `"$($patch.FullName)`" 2>nul"
    if ($LASTEXITCODE -eq 0) {
        Write-Output "already applied: $($patch.Name)"
    } else {
        Write-Output "FAILED (does not apply - upstream drift?): $($patch.Name)"
        $failed = $true
    }
}

if ($failed) { exit 1 }
Write-Output 'All patches accounted for.'
exit 0
