[CmdletBinding()]
param(
    [string]$Root = "",
    [ValidateSet("external_broad", "external_cedict", "clean_permissive")]
    [string]$Profile = "external_broad",
    [int]$MinHanzi = 2,
    [int]$MaxEntries = 0,
    [string]$CacheFile = "",
    [string]$CacheSourceId = "",
    [switch]$SkipRegression,
    [int]$DefaultRank = 10,
    [int]$PreviewTop = 8,
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
    [string]$QueryPathLmCorpusDir = "",
    [switch]$LmTransitionExactPairsOnly,
    [switch]$SkipReadmeSnapshot
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $Root = $PSScriptRoot
    }
    else {
        $Root = (Get-Location).Path
    }
}
$Root = (Resolve-Path $Root).Path

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

function Invoke-PythonScript {
    param(
        [string]$ScriptPath,
        [string[]]$ScriptArgs
    )

    $pythonCmd = @(Get-PythonCommand)
    $invokeArgs = @()
    if ($pythonCmd.Count -gt 1) {
        $invokeArgs += $pythonCmd[1..($pythonCmd.Count - 1)]
    }
    $invokeArgs += $ScriptPath
    if ($ScriptArgs) {
        $invokeArgs += $ScriptArgs
    }

    & $pythonCmd[0] @invokeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python step failed with exit code ${LASTEXITCODE}: $ScriptPath"
    }
}

if (-not (Test-Path -LiteralPath $Root)) {
    throw "Root path not found: $Root"
}

$buildScript = Join-Path $Root "scripts\build_external_seed.ps1"
$validateScript = Join-Path $Root "scripts\validate_regression_samples.py"
$readmeSnapshotScript = Join-Path $Root "scripts\update_readme_snapshot.py"

if (-not (Test-Path -LiteralPath $buildScript)) {
    throw "Missing build script: $buildScript"
}
if ((-not $SkipRegression) -and (-not (Test-Path -LiteralPath $validateScript))) {
    throw "Missing regression validator: $validateScript"
}
if ((-not $SkipReadmeSnapshot) -and (-not (Test-Path -LiteralPath $readmeSnapshotScript))) {
    throw "Missing README snapshot updater: $readmeSnapshotScript"
}

if ($CacheSourceId -eq "") {
    switch ($Profile) {
        "external_broad" { $CacheSourceId = "cc-cedict" }
        "external_cedict" { $CacheSourceId = "cc-cedict" }
        "clean_permissive" { $CacheSourceId = "opencc-stphrases" }
        default { $CacheSourceId = "" }
    }
}

if ($CacheFile -eq "") {
    switch ($CacheSourceId) {
        "cc-cedict" { $CacheFile = "data/cache/cedict.gz" }
        "opencc-stphrases" { $CacheFile = "data/cache/opencc_stphrases.txt" }
        default { $CacheFile = "" }
    }
}

Write-Host "== Cassotis Lexicon rebuild_all =="
Write-Host "Root: $Root"
Write-Host "Profile: $Profile  MinHanzi: $MinHanzi  MaxEntries: $MaxEntries"
if ($CacheFile -ne "") {
    Write-Host "Cache: $CacheFile (source: $CacheSourceId)"
}
if ($SkipRegression) {
    Write-Host "Regression validation: skipped"
}
if ($SkipReadmeSnapshot) {
    Write-Host "README dictionary snapshot update: skipped"
}

$buildArgs = @{
    Root = $Root
    Profile = $Profile
    MinHanzi = $MinHanzi
    MaxEntries = $MaxEntries
    OutputQueryPathSc = "data/generated/dict_query_path_prior_sc.txt"
    OutputQueryPathTc = "data/generated/dict_query_path_prior_tc.txt"
}
if ($CacheFile -ne "") { $buildArgs["CacheFile"] = $CacheFile }
if ($CacheSourceId -ne "") { $buildArgs["CacheSourceId"] = $CacheSourceId }
if ($SourceUrl -ne "") { $buildArgs["SourceUrl"] = $SourceUrl }
if ($SourceId -ne "") { $buildArgs["SourceId"] = $SourceId }
if ($SourceName -ne "") { $buildArgs["SourceName"] = $SourceName }
if ($SourceHomepage -ne "") { $buildArgs["SourceHomepage"] = $SourceHomepage }
if ($SourceLicense -ne "") { $buildArgs["SourceLicense"] = $SourceLicense }
if ($RiskLevel -ne "") { $buildArgs["RiskLevel"] = $RiskLevel }
if ($RedistributionClass -ne "") { $buildArgs["RedistributionClass"] = $RedistributionClass }
if ($AttributionRequired -ne "") { $buildArgs["AttributionRequired"] = $AttributionRequired }
if ($SourceNotes -ne "") { $buildArgs["SourceNotes"] = $SourceNotes }
if ($PinyinOverrides -ne "") { $buildArgs["PinyinOverrides"] = $PinyinOverrides }
if ($QueryPathLmCorpusDir -ne "") {
    $buildArgs["QueryPathLmCorpusDir"] = $QueryPathLmCorpusDir
    $buildArgs["OutputLmTransitionSc"] = "data/generated/dict_lm_transition_sc.txt"
    $buildArgs["OutputLmTransitionTc"] = "data/generated/dict_lm_transition_tc.txt"
    $lmTransitionSc = Join-Path $Root "data\generated\dict_lm_transition_sc.txt"
    $lmTransitionTc = Join-Path $Root "data\generated\dict_lm_transition_tc.txt"
    if (Test-Path -LiteralPath $lmTransitionSc) {
        $buildArgs["LmTransitionBaseSc"] = "data/generated/dict_lm_transition_sc.txt"
    }
    if (Test-Path -LiteralPath $lmTransitionTc) {
        $buildArgs["LmTransitionBaseTc"] = "data/generated/dict_lm_transition_tc.txt"
    }
}
if ($LmTransitionExactPairsOnly) {
    $buildArgs["LmTransitionExactPairsOnly"] = $true
}

& $buildScript @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw "Build step failed with exit code $LASTEXITCODE"
}

# Always produce dedicated Unihan dictionaries from lexicon pipeline
# so IME can import single-character data without maintaining an
# independent Unihan transform chain.
$unihanBuildArgs = @{
    Root = $Root
    Profile = "unihan_single"
    MinHanzi = 1
    MaxEntries = 0
    OutputSc = "data/generated/dict_unihan_sc.txt"
    OutputTc = "data/generated/dict_unihan_tc.txt"
    SupportDictSc = "data/generated/dict_clean_sc.txt"
    SupportDictTc = "data/generated/dict_clean_tc.txt"
    Manifest = "manifests/sources.unihan.generated.yml"
    Report = "reports/unihan_build_report.md"
}
if ($PinyinOverrides -ne "") { $unihanBuildArgs["PinyinOverrides"] = $PinyinOverrides }

Write-Host "Building dedicated lexicon Unihan outputs (dict_unihan_sc/tc)..."
& $buildScript @unihanBuildArgs
if ($LASTEXITCODE -ne 0) {
    throw "Unihan build step failed with exit code $LASTEXITCODE"
}

if (-not $SkipReadmeSnapshot) {
    Write-Host "Updating README dictionary snapshot from generated file row counts..."
    Invoke-PythonScript -ScriptPath $readmeSnapshotScript -ScriptArgs @(
        "--root", $Root
    )
}

if (-not $SkipRegression) {
    $dictSc = Join-Path $Root "data\generated\dict_clean_sc.txt"
    $dictTc = Join-Path $Root "data\generated\dict_clean_tc.txt"
    $dictUnihanSc = Join-Path $Root "data\generated\dict_unihan_sc.txt"
    $dictUnihanTc = Join-Path $Root "data\generated\dict_unihan_tc.txt"
    $samplesSc = Join-Path $Root "manifests\regression_samples.sc.tsv"
    $samplesTc = Join-Path $Root "manifests\regression_samples.tc.tsv"

    if (-not (Test-Path -LiteralPath $dictSc)) { throw "Missing generated file: $dictSc" }
    if (-not (Test-Path -LiteralPath $dictTc)) { throw "Missing generated file: $dictTc" }
    if (-not (Test-Path -LiteralPath $dictUnihanSc)) { throw "Missing generated file: $dictUnihanSc" }
    if (-not (Test-Path -LiteralPath $dictUnihanTc)) { throw "Missing generated file: $dictUnihanTc" }
    if (-not (Test-Path -LiteralPath $samplesSc)) { throw "Missing sample file: $samplesSc" }
    if (-not (Test-Path -LiteralPath $samplesTc)) { throw "Missing sample file: $samplesTc" }

    Write-Host "Running regression validation (SC)..."
    Invoke-PythonScript -ScriptPath $validateScript -ScriptArgs @(
        "--dict", $dictSc,
        "--dict", $dictUnihanSc,
        "--samples", $samplesSc,
        "--default-rank", "$DefaultRank",
        "--preview-top", "$PreviewTop"
    )

    Write-Host "Running regression validation (TC)..."
    Invoke-PythonScript -ScriptPath $validateScript -ScriptArgs @(
        "--dict", $dictTc,
        "--dict", $dictUnihanTc,
        "--samples", $samplesTc,
        "--default-rank", "$DefaultRank",
        "--preview-top", "$PreviewTop"
    )
}

Write-Host "rebuild_all completed."
