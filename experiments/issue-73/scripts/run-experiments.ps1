[CmdletBinding()]
param(
    [string]$LudiiJar = 'C:\Users\verti\Ludii-1.3.14.jar',
    [ValidateRange(1,16)][int]$Parallelism = 1,
    [ValidateRange(1,20)][int]$BatchSize = 5,
    [switch]$Smoke,
    [ValidateRange(1,3)][int]$SmokeGames = 1,
    [switch]$Resume
)
$ErrorActionPreference='Stop'
$scriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$issue=[IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo=[IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config=Get-Content -Raw (Join-Path $issue 'config.json')|ConvertFrom-Json
if(-not $Smoke -and $config.runtime_freeze.status -ne 'frozen') { throw 'Production generation is blocked until the operational-only smoke decision is frozen in config.json' }
$results=Join-Path $issue $(if($Smoke){'results-smoke'}else{'results'})
$raw=Join-Path $results 'raw-runner';$trialRoot=Join-Path $results 'trials'
New-Item -ItemType Directory -Force -Path $raw,$trialRoot|Out-Null
$runner=Join-Path $scriptDir 'Heitan7x7Experiment.java';$replay=Join-Path $scriptDir 'Heitan7x7Replay.java';$game=Join-Path $repo $config.game
$tasks=@()
foreach($experiment in $config.experiments){
    $count=if($Smoke){$SmokeGames}else{[int]$experiment.games}
    $seedBase=[long]$experiment.seed_first + $(if($Smoke){9000000}else{0})
    $trials=Join-Path $trialRoot $experiment.id;New-Item -ItemType Directory -Force -Path $trials|Out-Null
    $existing=@()
    if($Resume){$existing=@(Get-ChildItem $raw -Filter "$($experiment.id)-*.csv" -File -ErrorAction SilentlyContinue|ForEach-Object{Import-Csv $_.FullName});if(@($existing.game_index|Sort-Object -Unique).Count-ne$existing.Count){throw "Duplicate existing indices: $($experiment.id)"}}
    else{Get-ChildItem $trials -Filter '*.trl' -File -ErrorAction SilentlyContinue|Remove-Item -Force;Get-ChildItem $raw -Filter "$($experiment.id)-*.csv" -File -ErrorAction SilentlyContinue|Remove-Item -Force}
    $missing=@(1..$count|Where-Object{$_ -notin @($existing.game_index|ForEach-Object{[int]$_})})
    if($missing.Count){
        if($Resume){foreach($number in $missing){$tasks+=[pscustomobject]@{experiment=$experiment;games=1;seed=$seedBase+$number-1;offset=$number-1;raw=Join-Path $raw ("{0}-resume-{1:D4}.csv"-f $experiment.id,$number);trials=$trials}}}
        else{for($start=1;$start-le$count;$start+=$BatchSize){$size=[Math]::Min($BatchSize,$count-$start+1);$tasks+=[pscustomobject]@{experiment=$experiment;games=$size;seed=$seedBase+$start-1;offset=$start-1;raw=Join-Path $raw ("{0}-batch-{1:D3}.csv"-f $experiment.id,[int](($start-1)/$BatchSize+1));trials=$trials}}}
    }
}
$pending=[Collections.Queue]::new();$tasks|ForEach-Object{$pending.Enqueue($_)};$running=@();$started=[DateTime]::UtcNow
while($pending.Count-or$running.Count){
    while($pending.Count-and$running.Count-lt$Parallelism){$task=$pending.Dequeue();$e=$task.experiment;$arguments=@('-cp',$LudiiJar,$runner,$game,$e.id,$e.agent,$task.games,$task.seed,$e.iteration_limit,$task.raw,$task.trials,$repo,$task.offset);$process=Start-Process -FilePath java -ArgumentList $arguments -NoNewWindow -PassThru;$running+=[pscustomobject]@{process=$process;task=$task}}
    do{Start-Sleep -Milliseconds 250;$done=@($running|Where-Object{$_.process.HasExited})}while(-not$done.Count)
    foreach($item in $done){if($item.process.ExitCode){throw "Experiment process $($item.process.Id) exited $($item.process.ExitCode)"}}
    $ids=@($done.process.Id);$running=@($running|Where-Object{$_.process.Id-notin$ids})
}
$allRows=@();$conditionRuntime=@()
foreach($experiment in $config.experiments){
    $count=if($Smoke){$SmokeGames}else{[int]$experiment.games};$seedBase=[long]$experiment.seed_first+$(if($Smoke){9000000}else{0});$rows=@(Get-ChildItem $raw -Filter "$($experiment.id)-*.csv" -File|ForEach-Object{Import-Csv $_.FullName})
    if($rows.Count-ne$count){throw "Unexpected file-row count for $($experiment.id): $($rows.Count)"}
    if((Compare-Object (1..$count) @($rows.game_index|ForEach-Object{[int]$_}|Sort-Object)).Count){throw "Index gap: $($experiment.id)"}
    if((Compare-Object ($seedBase..($seedBase+$count-1)) @($rows.seed|ForEach-Object{[long]$_}|Sort-Object)).Count){throw "Seed gap: $($experiment.id)"}
    if(@($rows|Where-Object{$_.completed-ne'true'-or$_.end_type-ne'NaturalEnd'-or[int]$_.moves-ne144-or[int]$_.turns-ne48-or[int]$_.p1_total_pieces-ne72-or[int]$_.p2_total_pieces-ne72}).Count){throw "Structural generation validation failed: $($experiment.id)"}
    $allRows+=$rows;$conditionRuntime+=@{experiment_id=$experiment.id;games=$rows.Count;elapsed_seconds=[Math]::Round(($rows.elapsed_seconds|ForEach-Object{[double]$_}|Measure-Object -Sum).Sum,3);mean_seconds=[Math]::Round(($rows.elapsed_seconds|ForEach-Object{[double]$_}|Measure-Object -Average).Average,3);exit_status='success';file_count=@(Get-ChildItem $raw -Filter "$($experiment.id)-*.csv" -File).Count;trial_count=@(Get-ChildItem (Join-Path $trialRoot $experiment.id) -Filter '*.trl' -File).Count}
}
if(@($allRows.seed|Sort-Object -Unique).Count-ne$allRows.Count){throw 'Duplicate seeds'}
if($Smoke){
    $check=Join-Path $results 'replay-check';New-Item -ItemType Directory -Force -Path $check|Out-Null;$append=$false
    foreach($experiment in $config.experiments){& java -cp $LudiiJar $replay $game $experiment.id $experiment.iteration_limit (Join-Path $trialRoot $experiment.id) (Join-Path $check 'games.csv') (Join-Path $check 'placements.csv') (Join-Path $check 'point-turn-states.csv') (Join-Path $check 'regional-turn-states.csv') (Join-Path $check 'regional-opportunities.csv') (Join-Path $check 'objective-turn-snapshots.csv') (Join-Path $check 'objective-placement-effects.csv') $append.ToString().ToLowerInvariant();if($LASTEXITCODE){throw "Smoke replay failed: $($experiment.id)"};$append=$true}
    foreach($entry in $conditionRuntime){$entry.legal_replay_status='success'}
}
$environment=[ordered]@{schema_version=1;source_issue=73;smoke=$Smoke.IsPresent;information_policy=if($Smoke){'operational-only; outcomes and analysis metrics not inspected'}else{'production'};generated_at_utc=[DateTime]::UtcNow.ToString('o');wall_elapsed_seconds=[Math]::Round(([DateTime]::UtcNow-$started).TotalSeconds,3);games=$allRows.Count;parallelism=$Parallelism;batch_size=$BatchSize;ludii_version=$config.ludii_version;ludii_jar_sha256=(Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant();game_sha256=(Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant();runner_sha256=(Get-FileHash $runner -Algorithm SHA256).Hash.ToLowerInvariant();condition_runtime=$conditionRuntime}
$environment|ConvertTo-Json -Depth 6|Set-Content (Join-Path $results 'environment-run.json') -Encoding UTF8
Write-Host "Generated $($allRows.Count) games; only operational status was emitted by this command"

