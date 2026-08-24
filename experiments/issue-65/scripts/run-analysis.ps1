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
$results = Join-Path $issue 'results'
$raw = Join-Path $results 'raw'
New-Item -ItemType Directory -Force -Path $raw | Out-Null

& (Join-Path $scriptDir 'New-TrialSources.ps1')
if ($LASTEXITCODE) { throw 'Trial-source manifest generation failed' }

$games = Join-Path $raw 'games.csv'
$placements = Join-Path $raw 'placements.csv'
$states = Join-Path $raw 'regional-turn-states.csv'
$opportunities = Join-Path $raw 'regional-opportunities.csv'
$replay = Join-Path $scriptDir 'HeitanRegionalReplay.java'
$analysisScript = Join-Path $scriptDir 'analyze-regional-independence.mjs'
$game = Join-Path $repo $config.game
$started = [DateTime]::UtcNow

Push-Location $issue
try {
    for ($i = 0; $i -lt $config.analysis_sources.Count; $i++) {
        $source = $config.analysis_sources[$i]
        $trialRoot = Join-Path $repo $source.trial_root
        & java -cp $LudiiJar $replay $game $source.board $source.id $source.iteration_limit $trialRoot $games $placements $states $opportunities ($i -gt 0).ToString().ToLowerInvariant()
        if ($LASTEXITCODE) { throw "Replay failed: issue $($source.source_issue)/$($source.id)" }
    }
} finally {
    Pop-Location
}

$gameRows = @(Import-Csv $games)
$manifest = @(Import-Csv (Join-Path $results 'trial-sources.csv'))
$gameKeys = @($gameRows | ForEach-Object { "$($_.board)|$($_.experiment_id)|$([int]$_.game_index)" } | Sort-Object)
$manifestKeys = @($manifest | ForEach-Object { "$($_.board)|$($_.experiment_id)|$([int]$_.game_index)" } | Sort-Object)
if ((Compare-Object $gameKeys $manifestKeys).Count) { throw 'Replay keys differ from manifest' }
if (@($gameKeys | Group-Object | Where-Object Count -ne 1).Count) { throw 'Duplicate replay game keys' }

& node --test (Join-Path $scriptDir 'analyze-regional-independence.test.mjs')
if ($LASTEXITCODE) { throw 'Analysis tests failed' }
& node $analysisScript
if ($LASTEXITCODE) { throw 'Analysis failed' }

$environment = [ordered]@{
    schema_version = 1
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    elapsed_seconds = [Math]::Round(([DateTime]::UtcNow - $started).TotalSeconds, 3)
    games = $gameRows.Count
    ludii_version = $config.ludii_version
    ludii_jar_sha256 = (Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant()
    config_sha256 = (Get-FileHash (Join-Path $issue 'config.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    preregistration_sha256 = (Get-FileHash (Join-Path $issue 'README.md') -Algorithm SHA256).Hash.ToLowerInvariant()
    game_sha256 = (Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant()
    replay_sha256 = (Get-FileHash $replay -Algorithm SHA256).Hash.ToLowerInvariant()
    analysis_sha256 = (Get-FileHash $analysisScript -Algorithm SHA256).Hash.ToLowerInvariant()
    tests_sha256 = (Get-FileHash (Join-Path $scriptDir 'analyze-regional-independence.test.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    trial_sources_sha256 = (Get-FileHash (Join-Path $results 'trial-sources.csv') -Algorithm SHA256).Hash.ToLowerInvariant()
    git_commit = (& git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse HEAD).Trim()
    java = (& java --version | Select-Object -First 1)
    node = (& node --version)
}
$environment | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $results 'environment.json') -Encoding UTF8
Write-Host "Replayed and analyzed $($gameRows.Count) games"
