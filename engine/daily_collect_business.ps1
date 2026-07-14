# daily_collect_business.ps1 - daily local collection for the business-hits radar.
# Isolated twin of daily_collect.ps1 so the working claude-code pipeline is untouched.
# Launched by Windows Task Scheduler task 'RadarDailyCollectBusiness' at an OFFSET time
# from claude-code (which runs 00:00) to avoid concurrent git push races.
# ASCII-only prompt on purpose: powershell.exe reads UTF-8 over UNC paths as cp1251.
#
# Safe mode: --permission-mode acceptEdits + allow-list in .claude/settings.json
# (which now grants Write/Edit for radars/business-hits/data/**).

param(
  [string]$Slug = "business-hits",
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

# Headless prompt (translit ASCII). Self-contained: collect + git commit + push.
$prompt = "Vypolni ezhednevnyy sbor nakhodok dlya radara $Slug strogo po shagam, bez lishnikh voprosov. " +
  "TEMA (zhestko): konkretnye IMENOVANNYE biznesy, vystrelivshie v etom godu, s nizkim porogom vkhoda (start do 100k USD, bez krupnykh venchurnykh raundov), s ciframi vyruchki/MRR i istoriey rosta. Fokus - onlayn/cifrovoy, e-commerce, SaaS, infoprodukty, D2C. " +
  "ZHESTKOE PRAVILO OTBORA: berem TOLKO konkretnyy biznes s IMENEM - nazvanie biznesa/produkta + kto osnoval + vyruchka ili MRR (cifra) + kak imenno vyros. NELZYA: listikly 'N idey', obzory trendov, gaidy 'kak postroit', abstraktnye sovety. Tolko intervyu/otchety konkretnykh faunderov s ciframi. " +
  "1) Zapusti skill collect-finds s argumentom $Slug. On prochitaet radars/$Slug/prompts/queries.md i profile.md i radar.config.json (daily_target=15, freshness_days=90, taxonomy) i sdelaet SHIROKIY fan-out WebSearch po nim. Istochniki gde zhivut imenovannye istorii: indiehackers.com, news.ycombinator.com (Show HN / Launch HN s vyruchkoy), medium.com i starterstory.com founder stories, youtube intervyu faunderov, russkoyazychnye keysy (Forbes, vc.ru, Habr). Svezhest primerno 90 dney, prioritet svezhemu. Soberi pul kandidatov, prover daty i rabochie ssylki cherez WebFetch, deduplitsiruy protiv VSEKH proshlykh radars/$Slug/data/finds/*.json po source_url. Otberi do daily_target (15) kachestvennykh imenovannykh keysov; esli menshe - voz'mi skolko est, NE dobivay musorom (luchshe 8 nastoyashchikh chem 15 s listiklami). " +
  "Format kazhdoy nakhodki kak v sushchestvuyushchikh faylakh radars/$Slug/data/finds/: title s nazvaniem biznesa i cifroy, summary (kto osnoval / chto za biznes / vyruchka / za schet chego vyros), details (razbor keysa + glavnyy urok + 'Kak povtorit'), tegi iz taxonomy business-hits (obyazatelno case-study ili growth-story), obyazatelno rabochiy source_url na original, source_platform iz enum (hn/blog/youtube/reddit/other), author, published_at, confidence. Zapishi massiv v radars/$Slug/data/finds/<today>.json i (opcionalno) digest v radars/$Slug/data/digests/<today>.md. " +
  "2) Peresoberi indeks: python engine/build_manifest.py (esli upadet - ne blokiruysya). " +
  "3) Zakommit izmenennye fayly v radars/$Slug/data/ i manifest.json cherez git i zapush v origin master. Soobshchenie kommita: 'Biznesy za <today> (avto, lokalnoe raspisanie)'. Esli za segodnya nakhodok net vovse - NE delay pustoy kommit. " +
  "4) V kontse vyvedi odnu itogovuyu stroku: skolko nakhodok, razbivka po platformam, i byl li push. " +
  "Ne vydumyvay biznesy i ne podstavlyay nesushchestvuyushchie ssylki. Ne kommit sekrety."

Log "Running claude -p (headless, acceptEdits + allow-list from .claude/settings.json)..."

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

# Result check: any unpushed local commits? Retry push (with rebase in case the
# claude-code run pushed meanwhile).
Push-Location $ProjectDir
try {
  $head = git log -1 --format="%h %s" 2>$null
  Log "HEAD: $head"
  $ahead = git rev-list --count "@{u}..HEAD" 2>$null
  if ($ahead -and ([int]$ahead -gt 0)) {
    Log "WARNING: $ahead local commit(s) not pushed - pull --rebase then push."
    git pull --rebase origin master 2>&1 | ForEach-Object { Log ("  pull> " + $_) }
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
