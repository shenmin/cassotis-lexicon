param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Profile = "external_broad",
    [int]$MinHanzi = 2,
    [int]$MaxEntries = 0,
    [int]$PageviewsMonths = 6,
    [int]$PageviewsMaxRank = 1000,
    [string]$CacheFile = "",
    [string]$CacheSourceId = "",
    [string]$SourceUrl = "",
    [string]$SourceId = "",
    [string]$SourceName = "",
    [string]$SourceHomepage = "",
    [string]$SourceLicense = "",
    [string]$RiskLevel = "",
    [string]$RedistributionClass = "",
    [string]$AttributionRequired = "",
    [string]$SourceNotes = "",
    [string]$PinyinOverrides = "",
    [string]$OutputSc = "",
    [string]$OutputTc = "",
    [string]$OutputQueryPathSc = "",
    [string]$OutputQueryPathTc = "",
    [string]$QueryPathLmCorpusDir = "",
    [string]$SupportDictSc = "",
    [string]$SupportDictTc = "",
    [string]$Manifest = "",
    [string]$Report = ""
)

$ErrorActionPreference = "Stop"

function Get-PythonCommand {
    function Test-PythonCandidate {
        param(
            [string]$Command,
            [string[]]$PrefixArgs
        )
        $checkArgs = @()
        if ($PrefixArgs) {
            $checkArgs += $PrefixArgs
        }
        $checkArgs += "--version"
        try {
            & $Command @checkArgs *> $null
            return ($LASTEXITCODE -eq 0)
        }
        catch {
            return $false
        }
    }

    $candidates = @(
        @("py", "-3"),
        @((Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe")),
        @((Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")),
        @((Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe")),
        @((Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe")),
        @("python")
    )

    foreach ($candidate in $candidates) {
        if (-not $candidate -or $candidate.Count -lt 1) {
            continue
        }
        $command = [string]$candidate[0]
        if ([string]::IsNullOrWhiteSpace($command)) {
            continue
        }

        if (($command -notmatch "[\\/]" ) -and (-not (Get-Command $command -ErrorAction SilentlyContinue))) {
            continue
        }

        $prefixArgs = @()
        if ($candidate.Count -gt 1) {
            $prefixArgs += $candidate[1..($candidate.Count - 1)]
        }
        if (Test-PythonCandidate -Command $command -PrefixArgs $prefixArgs) {
            return $candidate
        }
    }

    throw "Python runtime not found. Please install Python 3."
}

$pythonCmd = @(Get-PythonCommand)
$scriptPath = Join-Path $Root "scripts\build_external_cedict.py"
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Missing script: $scriptPath"
}

Write-Host "Building external lexicon seed from external profile..."
Write-Host "Root: $Root"
Write-Host "Profile: $Profile  MinHanzi: $MinHanzi  MaxEntries: $MaxEntries  PageviewsMonths: $PageviewsMonths  PageviewsMaxRank: $PageviewsMaxRank"

$args = @(
    $scriptPath,
    "--profile", $Profile,
    "--min-hanzi", $MinHanzi,
    "--max-entries", $MaxEntries,
    "--pageviews-months", $PageviewsMonths,
    "--pageviews-max-rank", $PageviewsMaxRank
)

if ($SourceUrl -ne "") { $args += @("--source-url", $SourceUrl) }
if ($SourceId -ne "") { $args += @("--source-id", $SourceId) }
if ($SourceName -ne "") { $args += @("--source-name", $SourceName) }
if ($CacheFile -ne "") { $args += @("--cache-file", $CacheFile) }
if ($CacheSourceId -ne "") { $args += @("--cache-source-id", $CacheSourceId) }
if ($SourceHomepage -ne "") { $args += @("--source-homepage", $SourceHomepage) }
if ($SourceLicense -ne "") { $args += @("--source-license", $SourceLicense) }
if ($RiskLevel -ne "") { $args += @("--risk-level", $RiskLevel) }
if ($RedistributionClass -ne "") { $args += @("--redistribution-class", $RedistributionClass) }
if ($AttributionRequired -ne "") { $args += @("--attribution-required", $AttributionRequired) }
if ($SourceNotes -ne "") { $args += @("--source-notes", $SourceNotes) }
if ($PinyinOverrides -ne "") { $args += @("--pinyin-overrides", $PinyinOverrides) }
if ($OutputSc -ne "") { $args += @("--output-sc", $OutputSc) }
if ($OutputTc -ne "") { $args += @("--output-tc", $OutputTc) }
if ($OutputQueryPathSc -ne "") { $args += @("--query-path-output-sc", $OutputQueryPathSc) }
if ($OutputQueryPathTc -ne "") { $args += @("--query-path-output-tc", $OutputQueryPathTc) }
if ($QueryPathLmCorpusDir -ne "") { $args += @("--query-path-lm-corpus-dir", $QueryPathLmCorpusDir) }
if ($SupportDictSc -ne "") { $args += @("--support-dict-sc", $SupportDictSc) }
if ($SupportDictTc -ne "") { $args += @("--support-dict-tc", $SupportDictTc) }
if ($Manifest -ne "") { $args += @("--manifest", $Manifest) }
if ($Report -ne "") { $args += @("--report", $Report) }

$invokeArgs = @()
if ($pythonCmd.Count -gt 1) {
    $invokeArgs += $pythonCmd[1..($pythonCmd.Count - 1)]
}
$invokeArgs += $args

& $pythonCmd[0] @invokeArgs
if ($LASTEXITCODE -ne 0) {
    throw "External seed build failed with exit code $LASTEXITCODE"
}

Write-Host "Done."
