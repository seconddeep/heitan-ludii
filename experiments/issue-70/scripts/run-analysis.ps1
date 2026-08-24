[CmdletBinding()]
param([string]$LudiiJar = $env:LUDII_JAR)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($LudiiJar)) { throw 'Pass -LudiiJar or set the LUDII_JAR environment variable.' }
$LudiiJar = [IO.Path]::GetFullPath($LudiiJar)
if (-not (Test-Path -LiteralPath $LudiiJar -PathType Leaf)) { throw "Ludii JAR not found: $LudiiJar" }
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$issue = [IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo = [IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config = Get-Content -Raw (Join-Path $issue 'config.json') | ConvertFrom-Json
$sourceConfig = Get-Content -Raw (Join-Path $repo 'experiments\issue-65\config.json') | ConvertFrom-Json
$results = Join-Path $issue 'results'
$raw = Join-Path $results 'raw'
New-Item -ItemType Directory -Force -Path $raw | Out-Null
$turns = Join-Path $raw 'objective-turn-snapshots.csv'
$effects = Join-Path $raw 'objective-placement-effects.csv'
$replay = Join-Path $scriptDir 'HeitanLateGameReplay.java'
$game = Join-Path $repo $config.game
$started = [DateTime]::UtcNow

Push-Location $issue
try {
    for ($i = 0; $i -lt $sourceConfig.analysis_sources.Count; $i++) {
        $source = $sourceConfig.analysis_sources[$i]
        & java -cp $LudiiJar $replay $game $source.board $source.id $source.iteration_limit (Join-Path $repo $source.trial_root) $turns $effects ($i -gt 0).ToString().ToLowerInvariant()
        if ($LASTEXITCODE) { throw "Late-game replay failed: $($source.board)/$($source.id)" }
    }
} finally { Pop-Location }

& node --test (Join-Path $scriptDir 'analyze-front-selection.test.mjs')
if ($LASTEXITCODE) { throw 'Analysis tests failed' }
& node (Join-Path $scriptDir 'analyze-front-selection.mjs')
if ($LASTEXITCODE) { throw 'Analysis failed' }

$analysis = Get-Content -Raw (Join-Path $results 'analysis.json') | ConvertFrom-Json
$environment = [ordered]@{
    schema_version = 1
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    elapsed_seconds = [Math]::Round(([DateTime]::UtcNow - $started).TotalSeconds, 3)
    games = $analysis.validation.games
    ludii_version = $config.ludii_version
    ludii_jar_sha256 = (Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant()
    config_sha256 = (Get-FileHash (Join-Path $issue 'config.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    preregistration_sha256 = (Get-FileHash (Join-Path $issue 'README.md') -Algorithm SHA256).Hash.ToLowerInvariant()
    replay_sha256 = (Get-FileHash $replay -Algorithm SHA256).Hash.ToLowerInvariant()
    analysis_sha256 = (Get-FileHash (Join-Path $scriptDir 'analyze-front-selection.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    tests_sha256 = (Get-FileHash (Join-Path $scriptDir 'analyze-front-selection.test.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    git_commit = (& git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse HEAD).Trim()
    java = (& java --version | Select-Object -First 1)
    node = (& node --version)
}
$environment | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $results 'environment.json') -Encoding UTF8
Write-Host "Analyzed $($analysis.validation.games) games"
