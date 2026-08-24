[CmdletBinding()]
param(
    [string]$LudiiJar = $env:LUDII_JAR,
    [switch]$KeepPointStates
)
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($LudiiJar)) { throw 'Pass -LudiiJar or set the LUDII_JAR environment variable.' }
$LudiiJar = [IO.Path]::GetFullPath($LudiiJar)
if (-not (Test-Path -LiteralPath $LudiiJar -PathType Leaf)) { throw "Ludii JAR not found: $LudiiJar" }
$scriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$issue=[IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo=[IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config=Get-Content -Raw (Join-Path $issue 'config.json')|ConvertFrom-Json
if($config.runtime_freeze.status-ne'frozen'){throw 'Runtime sample sizes are not frozen'}
$results=Join-Path $issue 'results';$raw=Join-Path $results 'raw';New-Item -ItemType Directory -Force -Path $raw|Out-Null
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $scriptDir 'New-TrialSources.ps1')
if($LASTEXITCODE){throw 'Trial-source manifest generation failed'}
$paths=[ordered]@{games=Join-Path $raw 'games.csv';placements=Join-Path $raw 'placements.csv';points=Join-Path $raw 'point-turn-states.csv';states=Join-Path $raw 'regional-turn-states.csv';opportunities=Join-Path $raw 'regional-opportunities.csv';snapshots=Join-Path $raw 'objective-turn-snapshots.csv';effects=Join-Path $raw 'objective-placement-effects.csv'}
$replay=Join-Path $scriptDir 'Heitan7x7Replay.java';$game=Join-Path $repo $config.game;$started=[DateTime]::UtcNow;$append=$false
Push-Location $issue
try{
    foreach($experiment in $config.reused_72_experiments){$trials=Join-Path $repo "experiments/issue-73/results/trials/$($experiment.id)";& java -cp $LudiiJar $replay $game $experiment.id 72 $experiment.iteration_limit $trials $paths.games $paths.placements $paths.points $paths.states $paths.opportunities $paths.snapshots $paths.effects $append.ToString().ToLowerInvariant();if($LASTEXITCODE){throw "Reused replay failed: $($experiment.id)"};$append=$true}
    foreach($experiment in $config.experiments){$trials=Join-Path $results "trials\$($experiment.id)";& java -cp $LudiiJar $replay $game $experiment.id $experiment.piece_budget $experiment.iteration_limit $trials $paths.games $paths.placements $paths.points $paths.states $paths.opportunities $paths.snapshots $paths.effects $append.ToString().ToLowerInvariant();if($LASTEXITCODE){throw "Replay failed: $($experiment.id)"};$append=$true}
}finally{Pop-Location}
$gameRows=@(Import-Csv $paths.games);$manifest=@(Import-Csv (Join-Path $results 'trial-sources.csv'))
$gameKeys=@($gameRows|ForEach-Object{"$($_.board)|$($_.experiment_id)|$([int]$_.game_index)"}|Sort-Object);$manifestKeys=@($manifest|ForEach-Object{"$($_.board)|$($_.experiment_id)|$([int]$_.game_index)"}|Sort-Object)
if((Compare-Object $gameKeys $manifestKeys).Count){throw 'Replay keys differ from manifest'}
& node --test (Join-Path $scriptDir 'analyze-7x7-scale.test.mjs');if($LASTEXITCODE){throw 'Analysis tests failed'}
& node (Join-Path $scriptDir 'analyze-7x7-scale.mjs');if($LASTEXITCODE){throw 'Analysis failed'}
$pointZip=Join-Path $raw 'point-turn-states.csv.zip'
if((Get-Item $paths.points).Length-ge95MB){if(Test-Path $pointZip){Remove-Item -Force $pointZip};Compress-Archive -Path $paths.points -DestinationPath $pointZip -CompressionLevel Optimal;if(-not$KeepPointStates){Remove-Item -Force $paths.points}}
$environment=[ordered]@{schema_version=1;source_issue=77;generated_at_utc=[DateTime]::UtcNow.ToString('o');elapsed_seconds=[Math]::Round(([DateTime]::UtcNow-$started).TotalSeconds,3);games=$gameRows.Count;ludii_version=$config.ludii_version;ludii_jar_sha256=(Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant();config_sha256=(Get-FileHash (Join-Path $issue 'config.json') -Algorithm SHA256).Hash.ToLowerInvariant();preregistration_sha256=(Get-FileHash (Join-Path $issue 'README.md') -Algorithm SHA256).Hash.ToLowerInvariant();game_sha256=(Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant();runner_sha256=(Get-FileHash (Join-Path $scriptDir 'Heitan7x7Experiment.java') -Algorithm SHA256).Hash.ToLowerInvariant();replay_sha256=(Get-FileHash $replay -Algorithm SHA256).Hash.ToLowerInvariant();analysis_sha256=(Get-FileHash (Join-Path $scriptDir 'analyze-7x7-scale.mjs') -Algorithm SHA256).Hash.ToLowerInvariant();tests_sha256=(Get-FileHash (Join-Path $scriptDir 'analyze-7x7-scale.test.mjs') -Algorithm SHA256).Hash.ToLowerInvariant();trial_sources_sha256=(Get-FileHash (Join-Path $results 'trial-sources.csv') -Algorithm SHA256).Hash.ToLowerInvariant();point_states_zip_sha256=if(Test-Path $pointZip){(Get-FileHash $pointZip -Algorithm SHA256).Hash.ToLowerInvariant()}else{$null};git_commit=(& git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse HEAD).Trim();java=(& java --version|Select-Object -First 1);node=(& node --version)}
$environment|ConvertTo-Json -Depth 5|Set-Content (Join-Path $results 'environment.json') -Encoding UTF8
Write-Host "Replayed, validated, and analyzed $($gameRows.Count) Issue 77 games"
