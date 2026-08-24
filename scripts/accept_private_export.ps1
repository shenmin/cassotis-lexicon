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
        if (($parts.Count -ne 3) -and ($parts.Count -ne 4)) {
            throw "Invalid column count at ${Path}:$lineNo"
        }
        if (($parts.Count -eq 4) -and ($parts[3].Trim() -ne 'no_contains')) {
            throw "Invalid dictionary scope at ${Path}:$lineNo -> $($parts[3].Trim())"
        }

        $pinyin = $parts[0].Trim()
        $weightText = $parts[2].Trim()

        if ($pinyin -notmatch "^[a-z]+(?:'[a-z]+)*$") {
            throw "Invalid pinyin at ${Path}:$lineNo -> $pinyin"
        }

        $weight = 0
        if (-not [int]::TryParse($weightText, [ref]$weight)) {
            throw "Invalid weight at ${Path}:$lineNo -> $weightText"
        }
    }
}

function Test-TransitionCompletionFile {
    param([string]$Path)

    $lineNo = 0
    $prefixCounts = @{}
    $seenRows = @{}
    Get-Content -Encoding utf8 $Path | ForEach-Object {
        $lineNo++
        $line = $_.Trim()
        if ($line -eq '') { return }

        $parts = $line -split "`t"
        if ($parts.Count -ne 5) {
            throw "Invalid transition-completion column count at ${Path}:$lineNo"
        }

        $typedPrefix = $parts[0].Trim()
        $fullPinyin = $parts[1].Trim()
        $compactFullPinyin = $fullPinyin.Replace("'", '')
        $text = $parts[2].Trim()
        $pathParts = $parts[3].Trim() -split '\|'
        $evidence = 0
        if (($typedPrefix -notmatch '^[a-z]+$') -or
            ($fullPinyin -notmatch "^[a-z]+(?:'[a-z]+)*$") -or
            (-not $compactFullPinyin.StartsWith($typedPrefix)) -or
            ($compactFullPinyin.Length -le $typedPrefix.Length)) {
            throw "Invalid transition-completion pinyin at ${Path}:$lineNo"
        }
        $rowKey = "$typedPrefix`0$fullPinyin`0$text`0$($parts[3].Trim())"
        if ($seenRows.ContainsKey($rowKey)) {
            throw "Duplicate transition-completion row at ${Path}:$lineNo -> $typedPrefix"
        }
        $seenRows[$rowKey] = $true

        $prefixCount = 1
        if ($prefixCounts.ContainsKey($typedPrefix)) {
            $prefixCount = [int]$prefixCounts[$typedPrefix] + 1
        }
        if ($prefixCount -gt 6) {
            throw "Too many transition-completion rows at ${Path}:$lineNo -> $typedPrefix"
        }
        $prefixCounts[$typedPrefix] = $prefixCount
        if (($text -eq '') -or ($pathParts.Count -ne 2) -or
            (($pathParts -join '') -ne $text)) {
            throw "Invalid transition-completion path at ${Path}:$lineNo"
        }
        if ((-not [int]::TryParse($parts[4].Trim(), [ref]$evidence)) -or
            ($evidence -le 0)) {
            throw "Invalid transition-completion evidence at ${Path}:$lineNo"
        }
    }
}

function Test-LongCompletionFile {
    param([string]$Path)

    $lineNo = 0
    $anchorCounts = @{}
    $seenRows = @{}
    Get-Content -Encoding utf8 $Path | ForEach-Object {
        $lineNo++
        $line = $_.Trim()
        if ($line -eq '') { return }

        $parts = $line -split "`t"
        if ($parts.Count -ne 6) {
            throw "Invalid long-completion column count at ${Path}:$lineNo"
        }

        $anchorPath = $parts[0].Trim()
        $suffixPinyin = $parts[1].Trim()
        $suffixText = $parts[2].Trim()
        $suffixPath = $parts[3].Trim()
        $anchorParts = $anchorPath -split '\|'
        $suffixParts = $suffixPath -split '\|'
        $emptyAnchorParts = @($anchorParts | Where-Object {
            [string]::IsNullOrWhiteSpace($_)
        })
        $emptySuffixParts = @($suffixParts | Where-Object {
            [string]::IsNullOrWhiteSpace($_)
        })
        $evidence = 0
        $sourceCount = 0
        if (($anchorPath -eq '') -or ($suffixText -eq '') -or
            ($emptyAnchorParts.Count -gt 0) -or
            ($emptySuffixParts.Count -gt 0) -or
            ($anchorParts.Count -lt 1) -or ($anchorParts.Count -gt 3) -or
            ($suffixParts.Count -lt 1) -or ($suffixParts.Count -gt 3) -or
            (($suffixParts -join '') -ne $suffixText) -or
            ($suffixPinyin -notmatch "^[a-z]+(?:'[a-z]+){0,5}$")) {
            throw "Invalid long-completion path at ${Path}:$lineNo"
        }
        if ((-not [int]::TryParse($parts[4].Trim(), [ref]$evidence)) -or
            ($evidence -le 0) -or
            (-not [int]::TryParse($parts[5].Trim(), [ref]$sourceCount)) -or
            ($sourceCount -lt 5)) {
            throw "Invalid long-completion evidence at ${Path}:$lineNo"
        }

        $rowKey = "$anchorPath`0$suffixPinyin`0$suffixText"
        if ($seenRows.ContainsKey($rowKey)) {
            throw "Duplicate long-completion row at ${Path}:$lineNo"
        }
        $seenRows[$rowKey] = $true
        $anchorCount = 1
        if ($anchorCounts.ContainsKey($anchorPath)) {
            $anchorCount = [int]$anchorCounts[$anchorPath] + 1
        }
        if ($anchorCount -gt 8) {
            throw "Too many long-completion rows at ${Path}:$lineNo -> $anchorPath"
        }
        $anchorCounts[$anchorPath] = $anchorCount
    }
}

function Test-CompletionCompetitionFile {
    param([string]$Path)

    $lineNo = 0
    $seenKeys = @{}
    Get-Content -Encoding utf8 $Path | ForEach-Object {
        $lineNo++
        $line = $_.Trim()
        if ($line -eq '') { return }

        $parts = $line -split "`t"
        if ($parts.Count -ne 8) {
            throw "Invalid completion-competition column count at ${Path}:$lineNo"
        }

        $contextWidth = -1
        $evidence = 0
        $occurrenceCount = 0
        $sourceCount = 0
        $contextSuffix = $parts[1].Trim()
        $typedPrefix = $parts[2].Trim()
        $fullPinyin = $parts[3].Trim()
        $compactFullPinyin = $fullPinyin.Replace("'", '')
        $text = $parts[4].Trim()
        if ((-not [int]::TryParse($parts[0].Trim(), [ref]$contextWidth)) -or
            ($contextWidth -lt 0) -or ($contextWidth -gt 4) -or
            (($contextWidth -eq 0) -and ($contextSuffix -ne '')) -or
            (($contextWidth -gt 0) -and ($contextSuffix -eq '')) -or
            ($typedPrefix -notmatch '^[a-z]+$') -or
            ($fullPinyin -notmatch "^[a-z]+(?:'[a-z]+)*$") -or
            (-not $compactFullPinyin.StartsWith($typedPrefix)) -or
            ($compactFullPinyin.Length -le $typedPrefix.Length) -or
            ($text -eq '') -or
            (-not [int]::TryParse($parts[5].Trim(), [ref]$evidence)) -or
            ($evidence -le 0) -or
            (-not [int]::TryParse($parts[6].Trim(), [ref]$occurrenceCount)) -or
            ($occurrenceCount -le 0) -or
            (-not [int]::TryParse($parts[7].Trim(), [ref]$sourceCount)) -or
            ($sourceCount -le 0) -or ($sourceCount -gt 16)) {
            throw "Invalid completion-competition row at ${Path}:$lineNo"
        }

        $key = "$contextWidth`0$contextSuffix`0$typedPrefix`0$fullPinyin`0$text"
        if ($seenKeys.ContainsKey($key)) {
            throw "Duplicate completion-competition row at ${Path}:$lineNo"
        }
        $seenKeys[$key] = $true
    }
}

function Test-CompletionPairAuditFile {
    param([string]$Path)

    $lineNo = 0
    $seenKeys = @{}
    Get-Content -Encoding utf8 $Path | ForEach-Object {
        $lineNo++
        $line = $_.TrimEnd()
        if ($line -eq '') { return }

        $parts = $line -split "`t"
        if ($parts.Count -ne 13) {
            throw "Invalid completion-pair-audit column count at ${Path}:$lineNo"
        }

        $contextWidth = -1
        $pairDecision = -2
        $keepCount = -1
        $switchCount = -1
        $keepSourceCount = -1
        $switchSourceCount = -1
        $confidence = -1
        $contextSuffix = $parts[1].Trim()
        $typedPrefix = $parts[2].Trim()
        $baselinePinyin = $parts[3].Trim()
        $baselineText = $parts[4].Trim()
        $challengerPinyin = $parts[5].Trim()
        $challengerText = $parts[6].Trim()
        if ((-not [int]::TryParse($parts[0].Trim(), [ref]$contextWidth)) -or
            ($contextWidth -lt 0) -or ($contextWidth -gt 4) -or
            (($contextWidth -eq 0) -and ($contextSuffix -ne '')) -or
            (($contextWidth -gt 0) -and ($contextSuffix -eq '')) -or
            ($typedPrefix -notmatch '^[a-z]+$') -or
            ($baselinePinyin -notmatch '^[a-z]+$') -or
            ($challengerPinyin -notmatch '^[a-z]+$') -or
            (-not $baselinePinyin.StartsWith($typedPrefix)) -or
            (-not $challengerPinyin.StartsWith($typedPrefix)) -or
            ($baselinePinyin.Length -le $typedPrefix.Length) -or
            ($challengerPinyin.Length -le $typedPrefix.Length) -or
            ($baselineText -eq '') -or ($challengerText -eq '') -or
            (-not [int]::TryParse($parts[7].Trim(), [ref]$pairDecision)) -or
            ($pairDecision -lt -1) -or ($pairDecision -gt 1) -or
            (-not [int]::TryParse($parts[8].Trim(), [ref]$keepCount)) -or
            ($keepCount -lt 0) -or
            (-not [int]::TryParse($parts[9].Trim(), [ref]$switchCount)) -or
            ($switchCount -lt 0) -or (($keepCount + $switchCount) -le 0) -or
            (-not [int]::TryParse($parts[10].Trim(), [ref]$keepSourceCount)) -or
            ($keepSourceCount -lt 0) -or ($keepSourceCount -gt 16) -or
            (-not [int]::TryParse($parts[11].Trim(), [ref]$switchSourceCount)) -or
            ($switchSourceCount -lt 0) -or ($switchSourceCount -gt 16) -or
            (-not [int]::TryParse($parts[12].Trim(), [ref]$confidence)) -or
            ($confidence -lt 0) -or ($confidence -gt 1000)) {
            throw "Invalid completion-pair-audit row at ${Path}:$lineNo"
        }

        $key = "$contextWidth`0$contextSuffix`0$typedPrefix`0$baselinePinyin`0$baselineText`0$challengerPinyin`0$challengerText"
        if ($seenKeys.ContainsKey($key)) {
            throw "Duplicate completion-pair-audit row at ${Path}:$lineNo"
        }
        $seenKeys[$key] = $true
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
        if ($pinyin -notmatch "^[a-z]+(?:'[a-z]+)*$") {
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
    'data\generated\dict_transition_completion_sc.txt',
    'data\generated\dict_transition_completion_tc.txt',
    'data\generated\dict_long_completion_sc.txt',
    'data\generated\dict_long_completion_tc.txt',
    'data\generated\dict_completion_competition_sc.txt',
    'data\generated\dict_completion_competition_tc.txt',
    'data\generated\dict_completion_pair_audit_sc.txt',
    'data\generated\dict_completion_pair_audit_tc.txt',
    'data\generated\dict_unihan_sc.txt',
    'data\generated\dict_unihan_tc.txt',
    'manifests\sources.public.yml',
    'manifests\profiles.public.yml',
    'manifests\pinyin_overrides.tsv',
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
Test-TransitionCompletionFile (Join-Path $Root 'data\generated\dict_transition_completion_sc.txt')
Test-TransitionCompletionFile (Join-Path $Root 'data\generated\dict_transition_completion_tc.txt')
Test-LongCompletionFile (Join-Path $Root 'data\generated\dict_long_completion_sc.txt')
Test-LongCompletionFile (Join-Path $Root 'data\generated\dict_long_completion_tc.txt')
Test-CompletionCompetitionFile (Join-Path $Root 'data\generated\dict_completion_competition_sc.txt')
Test-CompletionCompetitionFile (Join-Path $Root 'data\generated\dict_completion_competition_tc.txt')
Test-CompletionPairAuditFile (Join-Path $Root 'data\generated\dict_completion_pair_audit_sc.txt')
Test-CompletionPairAuditFile (Join-Path $Root 'data\generated\dict_completion_pair_audit_tc.txt')
Test-DictFile (Join-Path $Root 'data\generated\dict_unihan_sc.txt')
Test-DictFile (Join-Path $Root 'data\generated\dict_unihan_tc.txt')
Test-PinyinOverrideFile (Join-Path $Root 'manifests\pinyin_overrides.tsv')
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
