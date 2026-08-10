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

# --- local secrets (API keys) ---
# Loads radars/<slug>/.secrets.ps1 if present (gitignored): sets $env:YOUTUBE_API_KEY,
# and optionally $env:REDDIT_CLIENT_ID / $env:REDDIT_CLIENT_SECRET. Without it the
# fetch_* scripts below just skip their source - never fatal.
$secretsFile = Join-Path $ProjectDir "radars\$Slug\.secrets.ps1"
if (Test-Path $secretsFile) { . $secretsFile }

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
$prompt = "Vypolni ezhednevnyy sbor nakhodok dlya radara $Slug strogo po shagam, bez lishnikh voprosov. " +
  "TEMA RADARA (smenena 14.07.2026): REALNYE KEYSY AVTOMATIZACII PROCESSOV v MALOM i SREDNEM BIZNESE. " +
  "ZHESTKOE PRAVILO OTBORA: kazhdaya nakhodka obyazana soderzhat 4 veshchi - (1) chto za biznes (hot' bez nazvaniya, no konkretno: kofeynya na 2 tochki, optovik stroymaterialov, studiya iz 4 chelovek); (2) kakoy process avtomatizirovali; (3) BYLO/STALO s ciframi (chasy v nedelyu, srok, dengi, oshibki); (4) chem sdelano. Instrumenty: II (Claude, ChatGPT, agenty) v prioritete, no polnopravno berem botov, no-code (n8n, Make, Zapier), skripty, integracii, 1C - vazhen rezultat dlya biznesa. " +
  "ZAPRESHCHENO brat: obzory i reytingi instrumentov, listikly 'N sposobov avtomatizirovat', reklamnye stranicy vendorov i integratorov, gaidy 'kak nastroit X' bez vnedreniya, repozitorii MCP-serverov i skillov, katalogi instrumentov, korporativnye enterprise-vnedreniya za milliony. Tolko istorii, gde konkretnyy biznes chto-to vnedril i poluchil izmerimyy rezultat. " +
  "1) Zapusti skill collect-finds s argumentom $Slug. On prochitaet radars/$Slug/prompts/queries.md (poiskovye zaprosy), prompts/profile.md (PRAVILO OTBORA, vesa tegov, FORMAT KARTOCHKI) i radar.config.json (daily_target=8, freshness_days=90, taxonomy). Sdelay SHIROKIY fan-out po zaprosam iz queries.md - i russkoyazychnym (vc.ru, habr.com, dzen, pikabu), i angloyazychnym (reddit r/smallbusiness, indiehackers, HN). Prover daty i rabochie ssylki cherez WebFetch, dedupliciruy protiv VSEKH proshlykh data/finds/*.json po source_url. " +
  "PRIORITET processam blizkim k chitatelyu: internet-magaziny i marketpleysy, obrabotka zayavok i klientskikh obrashcheniy, otchety i dokumenty, sklad i logistika - ikh stav vyshe v spiske. " +
  "Otberi do daily_target (8) nastoyashchikh keysov. Esli kachestvennykh menshe 8 - voz'mi skolko est i otmet pochemu (NE dobivay obzorami i listiklami - eto glavnoe trebovanie polzovatelya). " +
  "FORMAT kazhdoy nakhodki - strogo kak zadano v prompts/profile.md, sekciya 'Format nakhodki': title = '<Biznes>: <chto sdelali> - <rezultat>'; summary = 1-2 predlozheniya s glavnoy cifroy; details = strukturnaya kartochka s blokami **Biznes.** / **Process.** / **Bylo.** / **Sdelali.** / **Stalo.** / **Instrumenty.** / **Kak povtorit.** / **Podvokh.** (kazhdyy blok s novoy stroki, pustaya stroka mezhdu blokami). Esli dannykh dlya bloka net v istochnike - napishi 'v istochnike ne ukazano', NE vydumyvay. " +
  "Zapishi data/finds/<today>.json i data/digests/<today>.md (telo kazhdoy nakhodki v daydzheste = ee details). " +
  "2) Peresoberi indeks: zapusti python engine/build_manifest.py (esli upadet - ne blokiruysya). " +
  "3) Zakommit izmenennye fayly v radars/$Slug/data/ i manifest.json cherez git i zapush v origin master. Soobshchenie kommita: 'Keysy avtomatizacii za <today> (avto, lokalnoe raspisanie)'. Esli za segodnya nakhodok net vovse - NE delay pustoy kommit. " +
  "4) V kontse vyvedi odnu itogovuyu stroku: skolko keysov, kakie processy, i byl li push. " +
  "Ne vydumyvay keysy i ne podstavlyay nesushchestvuyushchie ssylki. Ne kommit sekrety."

# --- pre-collect: direct feed scripts (YouTube Data API, Reddit OAuth) ---
# Run BEFORE claude so the day's finds file already holds these candidates; the
# collect-finds skill then dedups its WebSearch results against them. Each script
# is best-effort: missing key / IP block / error is logged, never blocks the run.
$today = Get-Date -Format "yyyy-MM-dd"
function RunFeed([string]$name, [string]$script) {
  $py = Join-Path $ProjectDir $script
  if (-not (Test-Path $py)) { Log "feed ${name}: script not found ($script), skip"; return }
  Log "feed ${name}: python $script $Slug --write --today $today"
  & python $py $Slug --write --today $today 2>&1 | ForEach-Object { Log ("  ${name}> " + $_) }
}
# DISABLED 14.07.2026 with the theme switch (Claude Code news -> SMB automation cases).
# fetch_sources.py / fetch_youtube.py pull dev-tool feeds (HN, GitHub, Dev.to) that are
# noise for the new theme: they produced tool repos and reviews, never real business cases.
# The collect-finds skill now works from prompts/queries.md (WebSearch) alone.
# To re-enable for a dev-oriented radar, restore the RunFeed calls below.
Log "pre-collect feeds: disabled for this theme (SMB automation cases) - WebSearch only"

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
