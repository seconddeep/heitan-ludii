[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$scriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$issue=[IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo=[IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config=Get-Content -Raw (Join-Path $issue 'config.json')|ConvertFrom-Json
$results=Join-Path $issue 'results';$raw=Join-Path $results 'raw-runner';$rows=@()
foreach($experiment in $config.experiments){
    $runnerRows=@(Get-ChildItem $raw -Filter "$($experiment.id)-*.csv" -File|ForEach-Object{Import-Csv $_.FullName})
    if($runnerRows.Count-ne[int]$experiment.games){throw "Runner row count mismatch: $($experiment.id)"}
    foreach($r in $runnerRows){$trial=Join-Path $repo $r.trial_file;if(-not(Test-Path $trial)){throw "Missing trial: $($r.trial_file)"};$rows+=[pscustomobject][ordered]@{source_issue=73;board='7x7';experiment_id=$r.experiment_id;search_level=$experiment.search_level;iteration_limit=[int]$r.iteration_limit;game_index=[int]$r.game_index;seed=[long]$r.seed;trial_file=$r.trial_file;trial_sha256=(Get-FileHash $trial -Algorithm SHA256).Hash.ToLowerInvariant()}}
}
if(@($rows.seed|Sort-Object -Unique).Count-ne$rows.Count){throw 'Duplicate manifest seeds'}
if(@($rows.trial_sha256|Sort-Object -Unique).Count-ne$rows.Count){throw 'Duplicate manifest trial hashes'}
if(@($rows|ForEach-Object{"$($_.board)|$($_.experiment_id)|$($_.game_index)"}|Sort-Object -Unique).Count-ne$rows.Count){throw 'Duplicate manifest game keys'}
$rows|Sort-Object experiment_id,game_index|Export-Csv (Join-Path $results 'trial-sources.csv') -NoTypeInformation -Encoding UTF8
Write-Host "Wrote $($rows.Count) production trial sources"
