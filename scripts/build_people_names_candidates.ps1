param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Output = "data/cache/people_names_candidates.tsv",
    [string]$Cache = "data/cache/wikidata_people_name_candidates.json",
    [int]$MinSitelinks = 8,
    [int]$LimitPerOccupation = 250,
    [switch]$Refresh
)

$ErrorActionPreference = "Stop"

function Get-PythonCommand {
    $candidates = @(
        @{ Command = "py"; Args = @("-3") },
        @{ Command = "python"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }
        & $candidate.Command @($candidate.Args + @("--version")) *> $null
        if ($LASTEXITCODE -eq 0) {
            return $candidate
        }
    }

    throw "Python runtime not found. Please install Python 3."
}

$scriptPath = Join-Path $Root "scripts\build_people_names_candidates.py"
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Missing script: $scriptPath"
}

$python = Get-PythonCommand
$args = @(
    $scriptPath,
    "--output", $Output,
    "--cache", $Cache,
    "--min-sitelinks", $MinSitelinks,
    "--limit-per-occupation", $LimitPerOccupation
)
if ($Refresh) {
    $args += "--refresh"
}

Push-Location $Root
try {
    & $python.Command @($python.Args + $args)
    if ($LASTEXITCODE -ne 0) {
        throw "People-name candidate build failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
