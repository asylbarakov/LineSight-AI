$ErrorActionPreference = 'Stop'
$setupArguments = $args
$candidates = @()
if ($env:LINESIGHT_PYTHON) {
    $candidates += @{ File = $env:LINESIGHT_PYTHON; Prefix = @() }
} else {
    $candidates += @{ File = 'py'; Prefix = @('-3') }
    $candidates += @{ File = 'python'; Prefix = @() }
}
foreach ($candidate in $candidates) {
    if (-not (Get-Command $candidate.File -ErrorAction SilentlyContinue)) { continue }
    $prefix = $candidate.Prefix
    & $candidate.File @prefix -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>$null
    if ($LASTEXITCODE -ne 0) { continue }
    & $candidate.File @prefix -B (Join-Path $PSScriptRoot 'scripts/linesight.py') @setupArguments
    exit $LASTEXITCODE
}
Write-Error 'Python 3.10+ is required. Install it or set LINESIGHT_PYTHON to its executable.'
exit 1
