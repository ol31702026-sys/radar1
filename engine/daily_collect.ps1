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
  "SOSTAV LENTY (daily_target=10, poryadok strogiy): pozicii 1-4 - NOVOSTI Claude Code iz oficialnykh i avtoritetnykh istochnikov; pozicii 5-10 - KEYSY avtomatizacii v MSB (osnova radara). Dve chasti zhivut po RAZNYM pravilam i imeyut RAZNYY format details - ne putat. " +
  "CHAST A - NOVOSTI Claude Code (pozicii 1-4, svezhest 14 dney, NE 90). Istochniki tolko takie: oficialnyy changelog https://code.claude.com/docs/en/changelog (glavnyy), https://code.claude.com/docs/en/whats-new, anonsy Anthropic (anthropic.com/news, claude.com/blog); avtoritetnye izdaniya (InfoQ, The Verge, Ars Technica, TechCrunch, ZDNet) kogda pishut o znachimykh izmeneniyakh Claude Code; tekhnicheskie razbory na Habr/vc.ru TOLKO so ssylkoy na pervoistochnik. Snachala idi napryamuyu v changelog i whats-new, poiskom dobiray ostalnoe. NE berem v novosti: chuzhie MCP-servery, skilly i plaginy s GitHub, podborki '10 fishek', kursy, slukhi i utechki, posty bez fakta izmeneniya produkta. Format details novosti - rovno TRI bloka s pustoy strokoy mezhdu nimi: **Chto novogo.** (chto konkretno izmenilos: versiya, komanda, nastroyka) / **Zachem vam.** (chem polezno na zadachakh chitatelya - avtomatizaciya, magazin, dokumenty; ili chestno 'pryamogo primeneniya net, no znat polezno potomu chto...') / **Kak poprobovat.** (kak vklyuchit ili proverit u sebya: komanda, punkt nastroek, ssylka; esli ne vykacheno ili nuzhen platnyy tarif - tak i pishem). title novosti = 'Claude Code <versiya ili tema>: <chto poyavilos>'; tegi obyazatelno vklyuchayut novosti-claude. " +
  "CHAST B - KEYSY avtomatizacii (pozicii 5-10, svezhest 90 dney). Pravilo otbora - kak vyshe (4 obyazatelnykh veshchi). Sdelay SHIROKIY fan-out po zaprosam iz queries.md - i russkoyazychnym (vc.ru, habr.com, dzen, pikabu), i angloyazychnym (reddit r/smallbusiness, indiehackers, HN). PRIORITET processam blizkim k chitatelyu: internet-magaziny i marketpleysy, obrabotka zayavok i klientskikh obrashcheniy, otchety i dokumenty, sklad i logistika. Format details keysa - strukturnaya kartochka s blokami **Biznes.** / **Process.** / **Bylo.** / **Sdelali.** / **Stalo.** / **Instrumenty.** / **Kak povtorit.** / **Podvokh.** (kazhdyy blok s novoy stroki, pustaya stroka mezhdu blokami). title keysa = '<Biznes>: <chto sdelali> - <rezultat>'. " +
  "KRITICHNO PRO ZAPIS FAYLOV: instrumenty Write i Edit v etom headless-rezhime ZABLOKIROVANY - popytka ikh ispolzovat privodit k vechnomu ozhidaniyu razresheniya i sryvu vsego sbora (provereno 18.08). Zapisyvay VSE fayly (data/finds/<today>.json i data/digests/<today>.md) TOLKO cherez Bash s python3: naprimer cherez heredoc: python3 - <<EOF, dalee import json i json.dump v nuzhnyy put, zatem EOF. Chtenie faylov (Read) rabotaet normalno. " +
  "1) Zapusti skill collect-finds s argumentom $Slug. On prochitaet radars/$Slug/prompts/queries.md (poiskovye zaprosy dlya oboikh chastey), prompts/profile.md (SOSTAV LENTY, pravila otbora, oba formata kartochek) i radar.config.json (daily_target=10, taxonomy). Prover daty i rabochie ssylki cherez WebFetch, dedupliciruy protiv VSEKH proshlykh data/finds/*.json po source_url. " +
  "Esli novostey menshe 4 ili keysov menshe 6 - voz'mi skolko est i otmet pochemu. NE dobivay ni odnu chast obzorami, listiklami i reklamoy - eto glavnoe trebovanie polzovatelya. Luchshe 2 novosti i 5 keysov, chem 10 pozitsiy s musorom. " +
  "summary lyuboy nakhodki = 1-2 predlozheniya suti. Esli dannykh dlya bloka net v istochnike - napishi 'v istochnike ne ukazano', NE vydumyvay. " +
  "Zapishi data/finds/<today>.json i data/digests/<today>.md (telo kazhdoy nakhodki v daydzheste = ee details). " +
  "2) Peresoberi indeks: zapusti python engine/build_manifest.py (esli upadet - ne blokiruysya). " +
  "3) Zakommit izmenennye fayly v radars/$Slug/data/ i manifest.json cherez git i zapush v origin master. Soobshchenie kommita: 'Keysy avtomatizacii za <today> (avto, lokalnoe raspisanie)'. Esli za segodnya nakhodok net vovse - NE delay pustoy kommit. " +
  "4) V kontse vyvedi odnu itogovuyu stroku: skolko novostey i skolko keysov, kakie processy, i byl li push. " +
  "Ne vydumyvay novosti i keysy, ne podstavlyay nesushchestvuyushchie ssylki. Ne kommit sekrety."

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
