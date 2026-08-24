[CmdletBinding()]
param([string]$LudiiJar = $env:LUDII_JAR)
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($LudiiJar)) { throw 'Pass -LudiiJar or set the LUDII_JAR environment variable.' }
$LudiiJar = [IO.Path]::GetFullPath($LudiiJar)
if (-not (Test-Path -LiteralPath $LudiiJar -PathType Leaf)) { throw "Ludii JAR not found: $LudiiJar" }
$scriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path;$issue=[IO.Path]::GetFullPath((Join-Path $scriptDir '..'));$repo=[IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config=Get-Content -Raw (Join-Path $issue 'config.json')|ConvertFrom-Json;$results=Join-Path $issue 'results';$raw=Join-Path $results 'raw';New-Item -ItemType Directory -Force -Path $raw|Out-Null
$games=Join-Path $raw 'games.csv';$placements=Join-Path $raw 'placements.csv';$states=Join-Path $raw 'turn-states.csv';$runner=Join-Path $scriptDir 'HeitanScaleReplay.java';$game=Join-Path $repo $config.game
$datasets=@();foreach($item in $config.experiments){$datasets += [pscustomobject]@{board='6x6';id=$item.id;iterations=$item.iteration_limit;trials=Join-Path $results ('trials\'+$item.id)}};foreach($item in $config.comparison_sources){$datasets += [pscustomobject]@{board=$item.board;id=$item.id;iterations=$item.iteration_limit;trials=Join-Path $repo $item.trial_root}}
$started=[DateTime]::UtcNow
for($i=0;$i -lt $datasets.Count;$i++){$d=$datasets[$i];& java -cp $LudiiJar $runner $game $d.board $d.id $d.iterations $d.trials $games $placements $states ($i -gt 0).ToString().ToLowerInvariant();if($LASTEXITCODE){throw "Replay failed: $($d.id)"}}
& node --test (Join-Path $scriptDir 'analyze-scale.test.mjs');if($LASTEXITCODE){throw 'Analysis tests failed'}
& node (Join-Path $scriptDir 'analyze-scale.mjs');if($LASTEXITCODE){throw 'Analysis failed'}
$environment=[ordered]@{schema_version=1;generated_at_utc=[DateTime]::UtcNow.ToString('o');elapsed_seconds=[Math]::Round(([DateTime]::UtcNow-$started).TotalSeconds,3);ludii_version=$config.ludii_version;ludii_jar_sha256=(Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant();config_sha256=(Get-FileHash (Join-Path $issue 'config.json') -Algorithm SHA256).Hash.ToLowerInvariant();game_sha256=(Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant();replay_sha256=(Get-FileHash $runner -Algorithm SHA256).Hash.ToLowerInvariant();analysis_sha256=(Get-FileHash (Join-Path $scriptDir 'analyze-scale.mjs') -Algorithm SHA256).Hash.ToLowerInvariant();git_commit=(& git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse HEAD).Trim();java=(& java --version|Select-Object -First 1);node=(& node --version)}
$environment|ConvertTo-Json -Depth 4|Set-Content (Join-Path $results 'environment.json') -Encoding UTF8
