param(
    [Parameter(Mandatory = $true)][string]$Label,
    [string]$RepoRoot = "C:\Users\Iran\Desktop\temce"
)

Set-Location $RepoRoot

$outDir = Join-Path $RepoRoot "AUDIT_REPORTS\MODULAR_TEMCE\_snapshots"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = Join-Path $outDir "$Label.txt"

$now = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
$branch = git rev-parse --abbrev-ref HEAD 2>$null
$head = git rev-parse HEAD 2>$null
$por = @(git status --porcelain=v1 2>$null)

$staged = @($por | Where-Object { $_.Length -ge 2 -and $_.Substring(0, 1) -ne ' ' -and $_.Substring(0, 1) -ne '?' })
$unstaged = @($por | Where-Object { $_.Length -ge 2 -and $_.Substring(1, 1) -ne ' ' -and $_.Substring(0, 1) -ne '?' })
$untracked = @($por | Where-Object { $_.StartsWith('??') })

$keyFiles = @(
    "apps/worker/app.py",
    "apps/worker/__main__.py",
    "apps/worker/consumer.py",
    "apps/scheduler/app.py",
    "Dockerfile.worker",
    "Dockerfile.scheduler",
    "jobs/job_dispatcher.py",
    "jobs/queue_consumer.py",
    "jobs/queue_publisher.py",
    "jobs/registry.py"
)

$lines = @()
$lines += "SNAPSHOT $Label"
$lines += "captured_at=$now"
$lines += "repo_root=$RepoRoot"
$lines += "branch=$branch"
$lines += "head=$head"
$lines += "status_entries=$($por.Count)"
$lines += "staged=$($staged.Count)"
$lines += "unstaged=$($unstaged.Count)"
$lines += "untracked=$($untracked.Count)"
$lines += ""
$lines += "[key_file_sha256]"
foreach ($f in $keyFiles) {
    $p = Join-Path $RepoRoot $f
    if (Test-Path -LiteralPath $p) {
        $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
        $lines += "$f $h"
    }
    else {
        $lines += "$f MISSING"
    }
}
$lines += ""
$lines += "[porcelain]"
$lines += $por

$lines -join "`r`n" | Set-Content -LiteralPath $outFile -Encoding UTF8
Write-Output "WROTE $outFile"
Write-Output "branch=$branch head=$head staged=$($staged.Count) unstaged=$($unstaged.Count) untracked=$($untracked.Count)"
