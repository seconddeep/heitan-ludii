[CmdletBinding()]
param(
    [switch]$RefreshReplay,
    [string]$LudiiJar = 'C:\Users\verti\Ludii-1.3.14.jar'
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$issue = [IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo = [IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$configPath = Join-Path $issue 'config.json'
$config = Get-Content -Raw $configPath | ConvertFrom-Json
$results = Join-Path $issue 'results'
$started = [DateTime]::UtcNow
New-Item -ItemType Directory -Force -Path $results | Out-Null

if ($RefreshReplay) {
    & (Join-Path $repo 'experiments\issue-65\scripts\run-analysis.ps1') -LudiiJar $LudiiJar
    if ($LASTEXITCODE) { throw 'Issue 65 replay refresh failed' }
}

$sourceArtifacts = @()
foreach ($inputFile in $config.input_files) {
    $fullPath = Join-Path $repo $inputFile.path
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "Missing pinned input: $($inputFile.path)"
    }
    $actual = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $inputFile.sha256) {
        throw "Pinned input hash mismatch: $($inputFile.path)"
    }
    $sourceArtifacts += [ordered]@{
        path = $inputFile.path
        sha256 = $actual
        bytes = (Get-Item -LiteralPath $fullPath).Length
    }
}

& node --test (Join-Path $scriptDir 'analyze-dormant-fronts.test.mjs')
if ($LASTEXITCODE) { throw 'Analysis tests failed' }
& node (Join-Path $scriptDir 'analyze-dormant-fronts.mjs')
if ($LASTEXITCODE) { throw 'Analysis failed' }

$analysis = Get-Content -Raw (Join-Path $results 'analysis.json') | ConvertFrom-Json
$environment = [ordered]@{
    schema_version = 1
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    elapsed_seconds = [Math]::Round(([DateTime]::UtcNow - $started).TotalSeconds, 3)
    games = $analysis.validation.games
    primary_games = $analysis.primary_games
    source_issue = $config.source_issue
    replay_refreshed = [bool]$RefreshReplay
    ludii_version = $config.ludii_version
    config_sha256 = (Get-FileHash $configPath -Algorithm SHA256).Hash.ToLowerInvariant()
    preregistration_sha256 = (Get-FileHash (Join-Path $issue 'README.md') -Algorithm SHA256).Hash.ToLowerInvariant()
    analysis_sha256 = (Get-FileHash (Join-Path $scriptDir 'analyze-dormant-fronts.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    tests_sha256 = (Get-FileHash (Join-Path $scriptDir 'analyze-dormant-fronts.test.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    source_artifacts = $sourceArtifacts
    git_commit = (& git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse HEAD).Trim()
    node = (& node --version)
    java = if ($RefreshReplay) { (& java --version | Select-Object -First 1) } else { $null }
}
$environment | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $results 'environment.json') -Encoding UTF8
Write-Host "Analyzed $($analysis.validation.games) games and $($analysis.outputs.departure_cycles) departure cycles"
