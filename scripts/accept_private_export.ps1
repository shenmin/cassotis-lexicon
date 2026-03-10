param(
    [string]$Root = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = Split-Path -Parent $PSScriptRoot
}

function Assert-File {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required file missing: $Path"
    }
}

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

function Test-DictFile {
    param([string]$Path)

    $lineNo = 0
    Get-Content -Encoding utf8 $Path | ForEach-Object {
        $lineNo++
        $line = $_.Trim()
        if ($line -eq '') { return }

        $parts = $line -split "`t"
        if ($parts.Count -ne 3) {
            throw "Invalid column count at ${Path}:$lineNo"
        }

        $pinyin = $parts[0].Trim()
        $weightText = $parts[2].Trim()

        if ($pinyin -notmatch '^[a-z]+$') {
            throw "Invalid pinyin at ${Path}:$lineNo -> $pinyin"
        }

        $weight = 0
        if (-not [int]::TryParse($weightText, [ref]$weight)) {
            throw "Invalid weight at ${Path}:$lineNo -> $weightText"
        }
    }
}

function Test-PinyinOverrideFile {
    param([string]$Path)

    $lineNo = 0
    Get-Content -Encoding utf8 $Path | ForEach-Object {
        $lineNo++
        $line = $_.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) { return }

        $parts = $line -split "`t"
        if ($parts.Count -lt 2) {
            throw "Invalid override format at ${Path}:$lineNo"
        }

        $text = $parts[0].Trim()
        $pinyin = $parts[1].Trim()

        if ($text -notmatch '[\u3400-\u9fff]') {
            throw "Invalid override text at ${Path}:$lineNo -> $text"
        }
        if ($pinyin -notmatch '^[a-z]+$') {
            throw "Invalid override pinyin at ${Path}:$lineNo -> $pinyin"
        }
    }
}

function Assert-ManifestPolicy {
    param([string]$Path)

    $content = Get-Content -LiteralPath $Path -Raw -Encoding utf8
    $requiredPatterns = @(
        '(?m)^\s*risk_level:\s*\S+',
        '(?m)^\s*redistribution_class:\s*\S+',
        '(?m)^\s*attribution_required:\s*(true|false)\s*$'
    )
    foreach ($pattern in $requiredPatterns) {
        if (-not [regex]::IsMatch($content, $pattern)) {
            throw "Missing required manifest field in $Path (pattern: $pattern)"
        }
    }

    $profileMatch = [regex]::Match($content, '(?m)^profile:\s*(\S+)')
    if ($profileMatch.Success -and $profileMatch.Groups[1].Value -eq 'clean_permissive') {
        $licenseMatch = [regex]::Match($content, '(?m)^\s*license:\s*(.+)$')
        if (-not $licenseMatch.Success) {
            throw "Missing license field for clean_permissive profile in $Path"
        }
        $licenseText = $licenseMatch.Groups[1].Value.Trim().ToLowerInvariant()
        $forbiddenTokens = @('by-sa', 'gpl', 'lgpl', 'agpl', 'gfdl', 'copyleft')
        foreach ($token in $forbiddenTokens) {
            if ($licenseText.Contains($token)) {
                throw "clean_permissive profile rejects copyleft/share-alike license marker: $token"
            }
        }

        if (-not [regex]::IsMatch($content, '(?m)^\s*redistribution_class:\s*permissive\s*$')) {
            throw "clean_permissive profile requires redistribution_class: permissive"
        }
        if (-not [regex]::IsMatch($content, '(?m)^\s*risk_level:\s*low\s*$')) {
            throw "clean_permissive profile requires risk_level: low"
        }
    }
}

$required = @(
    'data\generated\dict_clean_sc.txt',
    'data\generated\dict_clean_tc.txt',
    'data\generated\dict_query_path_prior_sc.txt',
    'data\generated\dict_query_path_prior_tc.txt',
    'data\generated\dict_unihan_sc.txt',
    'data\generated\dict_unihan_tc.txt',
    'manifests\sources.public.yml',
    'manifests\profiles.public.yml',
    'manifests\pinyin_overrides.clean_permissive.tsv',
    'manifests\regression_samples.sc.tsv',
    'manifests\regression_samples.tc.tsv',
    'attribution\ATTRIBUTION.md',
    'rebuild_all.ps1'
)

foreach ($rel in $required) {
    Assert-File (Join-Path $Root $rel)
}

$forbiddenExt = @('.doc', '.docx', '.pdf', '.epub', '.mobi', '.zip', '.rar', '.7z')
Get-ChildItem -LiteralPath $Root -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($Root.Length).TrimStart('\\')

    if ($rel -like 'corpus\\raw\\*') {
        throw "Forbidden raw corpus file found: $rel"
    }

    if ($rel -like 'data\\cache\\*') {
        throw "Forbidden downloaded raw source file found: $rel"
    }

    if ($forbiddenExt -contains $_.Extension.ToLowerInvariant()) {
        throw "Forbidden binary/document file found: $rel"
    }
}

Test-DictFile (Join-Path $Root 'data\generated\dict_clean_sc.txt')
Test-DictFile (Join-Path $Root 'data\generated\dict_clean_tc.txt')
Test-DictFile (Join-Path $Root 'data\generated\dict_query_path_prior_sc.txt')
Test-DictFile (Join-Path $Root 'data\generated\dict_query_path_prior_tc.txt')
Test-DictFile (Join-Path $Root 'data\generated\dict_unihan_sc.txt')
Test-DictFile (Join-Path $Root 'data\generated\dict_unihan_tc.txt')
Test-PinyinOverrideFile (Join-Path $Root 'manifests\pinyin_overrides.clean_permissive.tsv')
Assert-ManifestPolicy (Join-Path $Root 'manifests\sources.public.yml')

$pythonCmd = @(Get-PythonCommand)
$regressionScript = Join-Path $Root 'scripts\validate_regression_samples.py'
Assert-File $regressionScript

$scDict = Join-Path $Root 'data\generated\dict_clean_sc.txt'
$tcDict = Join-Path $Root 'data\generated\dict_clean_tc.txt'
$scUnihanDict = Join-Path $Root 'data\generated\dict_unihan_sc.txt'
$tcUnihanDict = Join-Path $Root 'data\generated\dict_unihan_tc.txt'
$scSamples = Join-Path $Root 'manifests\regression_samples.sc.tsv'
$tcSamples = Join-Path $Root 'manifests\regression_samples.tc.tsv'

$runArgsPrefix = @()
if ($pythonCmd.Count -gt 1) {
    $runArgsPrefix += $pythonCmd[1..($pythonCmd.Count - 1)]
}

$scArgs = @($regressionScript, '--dict', $scDict, '--dict', $scUnihanDict, '--samples', $scSamples)
& $pythonCmd[0] @runArgsPrefix @scArgs
if ($LASTEXITCODE -ne 0) {
    throw "SC regression sample validation failed."
}

$tcArgs = @($regressionScript, '--dict', $tcDict, '--dict', $tcUnihanDict, '--samples', $tcSamples)
& $pythonCmd[0] @runArgsPrefix @tcArgs
if ($LASTEXITCODE -ne 0) {
    throw "TC regression sample validation failed."
}

Write-Host 'Public export validation passed.'
