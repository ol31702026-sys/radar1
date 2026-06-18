# daily_collect.ps1 - daily local Radar finds collection via headless Claude Code.
# Launched by Windows Task Scheduler (see engine/SCHEDULE.md). Writes logs to data/logs/.
# ASCII-only on purpose: powershell.exe reads UTF-8 over UNC paths as cp1251 and breaks on Cyrillic.
#
# What it does:
#   1. claude -p runs the collect-finds skill for the radar
#   2. that same run commits and pushes the result to origin
#   3. everything is logged to a dated file - no silent failures
#
# Safe mode: --permission-mode acceptEdits + allow-list in .claude/settings.json.
# No bypassPermissions: actions outside the allow-list are blocked, not silently run.

param(
  [string]$Slug = "claude-code",
  [string]$ProjectDir = "\\wsl.localhost\Ubuntu\home\oleg\projects\useful_Claude",
  [string]$ClaudeExe = "C:\Users\user\.local\bin\claude.exe"
)

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

# --- log ---
$logDir = Join-Path $ProjectDir "radars\$Slug\data\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logFile = Join-Path $logDir "collect_$stamp.log"

function Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  $line | Tee-Object -FilePath $logFile -Append
}

Log "=== Start daily collection: radar=$Slug ==="
Log "ProjectDir=$ProjectDir"

if (-not (Test-Path $ClaudeExe)) { Log "ERROR: claude.exe not found at $ClaudeExe"; exit 1 }
if (-not (Test-Path $ProjectDir)) { Log "ERROR: project dir not reachable $ProjectDir"; exit 1 }

# Headless prompt. Self-contained: collect + git commit + push. Russian text is fine
# inside the prompt string because it is piped to claude via stdin (UTF-8), not parsed by PowerShell.
$prompt = "Vypolni ezhednevnyy sbor nakhodok dlya radara $Slug strogo po shagam, bez lishnikh voprosov: " +
  "1) Zapusti skill collect-finds s argumentom $Slug. VAZHNO pro OKHVAT: sdelay SHIROKIY fan-out - 20+ raznykh WebSearch-zaprosov pod raznye temy taxonomy (subagents, hooks, mcp, skills, slash-commands, workflows, automation, ci-cd, testing, refactoring, prompting, cost-tokens, ide-integration, case-study) I pod svezhest (release notes, changelog, whats new, June 2026, this week). Soberi pul 40-60 kandidatov, prover daty cherez WebFetch, dedupliciruy protiv vsekh proshlykh data/finds/*.json po source_url, otberi do daily_target (15) svezhikh nedubliruyushchikh. Zaydi na agregatory: releasebot.io, code.claude.com/docs changelog i whats-new, claudelog. Esli kachestvennykh menshe 15 - voz'mi skolko est i otmet pochemu (NE dobivay musorom). Posledniye 2 pozicii - keysy (case-study). Zapishi data/finds/<today>.json i data/digests/<today>.md (Anons + Rasshifrovka). " +
  "2) Peresoberi indeks: zapusti python engine/build_manifest.py (esli upadet - ne blokiruysya). " +
  "3) Zakommit izmenennye fayly v radars/$Slug/data/ cherez git i zapush v origin master. Soobshchenie kommita: 'Nakhodki za <today> (avto, lokalnoe raspisanie)'. Esli za segodnya nakhodok net vovse - NE delay pustoy kommit. " +
  "4) V kontse vyvedi odnu itogovuyu stroku: skolko nakhodok, razbivka po platformam, i byl li push. " +
  "Ne vydumyvay nakhodki i ne podstavlyay nesushchestvuyushchie ssylki. Ne kommit sekrety."

Log "Running claude -p (headless, acceptEdits + allow-list from .claude/settings.json)..."

# stdin redirected via pipe (otherwise claude waits 3s for input).
# Working dir = ProjectDir so the project .claude/settings.json allow-list is picked up.
$claudeLog = Join-Path $logDir "claude_out_$stamp.log"
Push-Location $ProjectDir
try {
  $prompt | & $ClaudeExe -p --permission-mode acceptEdits 2>&1 |
    Tee-Object -FilePath $claudeLog -Append |
    ForEach-Object { Log ("  cc> " + $_) }
}
finally {
  Pop-Location
}

$code = $LASTEXITCODE
Log "claude exited with code $code"

# Result check: any unpushed local commits?
Push-Location $ProjectDir
try {
  $head = git log -1 --format="%h %s" 2>$null
  Log "HEAD: $head"
  $ahead = git rev-list --count "@{u}..HEAD" 2>$null
  if ($ahead -and ([int]$ahead -gt 0)) {
    Log "WARNING: $ahead local commit(s) not pushed - retrying push."
    git push origin master 2>&1 | ForEach-Object { Log ("  push> " + $_) }
  }
  else {
    Log "In sync with origin: OK (nothing to push)."
  }
}
finally {
  Pop-Location
}

Log "=== Done (exit $code) ==="
exit $code
