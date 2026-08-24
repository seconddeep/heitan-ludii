[CmdletBinding()]
param(
    [string]$LudiiJar = $env:LUDII_JAR,
    [ValidateRange(1,16)][int]$Parallelism = 1,
    [ValidateRange(1,20)][int]$BatchSize = 5,
    [switch]$Smoke,
    [ValidateRange(1,10)][int]$SmokeGames = 2,
    [switch]$Resume
)
$ErrorActionPreference='Stop'
if ([string]::IsNullOrWhiteSpace($LudiiJar)) { throw 'Pass -LudiiJar or set the LUDII_JAR environment variable.' }
$LudiiJar = [IO.Path]::GetFullPath($LudiiJar)
if (-not (Test-Path -LiteralPath $LudiiJar -PathType Leaf)) { throw "Ludii JAR not found: $LudiiJar" }
$scriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$issue=[IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo=[IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config=Get-Content -Raw (Join-Path $issue 'config.json')|ConvertFrom-Json
$results=Join-Path $issue $(if($Smoke){'results-smoke'}else{'results'})
$raw=Join-Path $results 'raw';$trialRoot=Join-Path $results 'trials'
New-Item -ItemType Directory -Force -Path $raw,$trialRoot|Out-Null
$runner=Join-Path $scriptDir 'Heitan3x3Experiment.java';$game=Join-Path $repo $config.game
$tasks=@()
foreach($experiment in $config.experiments){
    $count=if($Smoke){$SmokeGames}else{[int]$experiment.games}
    $trials=Join-Path $trialRoot $experiment.id;New-Item -ItemType Directory -Force -Path $trials|Out-Null
    $existing=@()
    if($Resume){$existing=@(Get-ChildItem $raw -Filter "$($experiment.id)-*.csv" -File -ErrorAction SilentlyContinue|ForEach-Object{Import-Csv $_.FullName});if(@($existing.game_index|Sort-Object -Unique).Count-ne$existing.Count){throw "Duplicate existing indices: $($experiment.id)"}}
    else{Get-ChildItem $trials -Filter '*.trl' -File -ErrorAction SilentlyContinue|Remove-Item -Force;Get-ChildItem $raw -Filter "$($experiment.id)-*.csv" -File -ErrorAction SilentlyContinue|Remove-Item -Force}
    $missing=@(1..$count|Where-Object{$_ -notin @($existing.game_index|ForEach-Object{[int]$_})})
    if($missing.Count){
        if($Resume){foreach($number in $missing){$tasks+=[pscustomobject]@{experiment=$experiment;games=1;seed=[long]$experiment.seed_first+$number-1;offset=$number-1;raw=Join-Path $raw ("{0}-resume-{1:D4}.csv"-f $experiment.id,$number);trials=$trials}}}
        else{for($start=1;$start-le$count;$start+=$BatchSize){$size=[Math]::Min($BatchSize,$count-$start+1);$tasks+=[pscustomobject]@{experiment=$experiment;games=$size;seed=[long]$experiment.seed_first+$start-1;offset=$start-1;raw=Join-Path $raw ("{0}-batch-{1:D3}.csv"-f $experiment.id,[int](($start-1)/$BatchSize+1));trials=$trials}}}
    }
}
$pending=[Collections.Queue]::new();$tasks|ForEach-Object{$pending.Enqueue($_)};$running=@();$started=[DateTime]::UtcNow
while($pending.Count-or$running.Count){
    while($pending.Count-and$running.Count-lt$Parallelism){$task=$pending.Dequeue();$e=$task.experiment;$arguments=@('-cp',$LudiiJar,$runner,$game,$e.id,$e.agent,$task.games,$task.seed,$e.iteration_limit,$task.raw,$task.trials,$repo,$task.offset);$process=Start-Process -FilePath java -ArgumentList $arguments -NoNewWindow -PassThru;$running+=[pscustomobject]@{process=$process;task=$task}}
    do{Start-Sleep -Milliseconds 250;$done=@($running|Where-Object{$_.process.HasExited})}while(-not$done.Count)
    foreach($item in $done){if($item.process.ExitCode){throw "Experiment process $($item.process.Id) exited $($item.process.ExitCode)"}}
    $ids=@($done.process.Id);$running=@($running|Where-Object{$_.process.Id-notin$ids})
}
$allRows=@()
foreach($experiment in $config.experiments){
    $count=if($Smoke){$SmokeGames}else{[int]$experiment.games};$rows=@(Get-ChildItem $raw -Filter "$($experiment.id)-*.csv" -File|ForEach-Object{Import-Csv $_.FullName});if($rows.Count-ne$count){throw "Unexpected count for $($experiment.id): $($rows.Count)"}
    $expectedIndices=1..$count;$expectedSeeds=[long]$experiment.seed_first..([long]$experiment.seed_first+$count-1)
    if((Compare-Object $expectedIndices @($rows.game_index|ForEach-Object{[int]$_}|Sort-Object)).Count){throw "Index gap: $($experiment.id)"};if((Compare-Object $expectedSeeds @($rows.seed|ForEach-Object{[long]$_}|Sort-Object)).Count){throw "Seed gap: $($experiment.id)"}
    if(@($rows|Where-Object{$_.completed-ne'true'-or$_.end_type-ne'NaturalEnd'-or[int]$_.moves-ne54-or[int]$_.turns-ne18}).Count){throw "Invalid game: $($experiment.id)"};$allRows+=$rows
}
if(@($allRows.seed|Sort-Object -Unique).Count-ne$allRows.Count){throw 'Duplicate seeds'}
$conditionRuntime=@($allRows|Group-Object experiment_id|ForEach-Object{[ordered]@{experiment_id=$_.Name;games=$_.Count;elapsed_seconds=[Math]::Round(($_.Group.elapsed_seconds|ForEach-Object{[double]$_}|Measure-Object -Sum).Sum,3);mean_seconds=[Math]::Round(($_.Group.elapsed_seconds|ForEach-Object{[double]$_}|Measure-Object -Average).Average,3)}})
$environment=[ordered]@{schema_version=1;source_issue=62;smoke=$Smoke.IsPresent;generated_at_utc=[DateTime]::UtcNow.ToString('o');wall_elapsed_seconds=[Math]::Round(([DateTime]::UtcNow-$started).TotalSeconds,3);games=$allRows.Count;parallelism=$Parallelism;batch_size=$BatchSize;ludii_version=$config.ludii_version;ludii_jar_sha256=(Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant();game_sha256=(Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant();runner_sha256=(Get-FileHash $runner -Algorithm SHA256).Hash.ToLowerInvariant();condition_runtime=$conditionRuntime}
$environment|ConvertTo-Json -Depth 6|Set-Content (Join-Path $results 'environment-run.json') -Encoding UTF8
Write-Host "Generated and validated $($allRows.Count) Issue 62 games"
