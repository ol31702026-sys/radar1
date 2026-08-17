# Helper: copies CLAUDE_CODE_OAUTH_TOKEN from the Windows user environment into the
# radar's gitignored .secrets.ps1, so headless collection works regardless of whether
# the scheduled process inherits the env var.
#
# Why: `setx` only affects NEW processes; anything inheriting an older environment
# (WSL interop, long-running shells) does not see it. daily_collect.ps1 dot-sources
# radars/<slug>/.secrets.ps1 on every run, so storing it there is deterministic.
#
# The token value is never printed. Run:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File <this> [-Slug claude-code]
param(
  [string]$Slug = "claude-code",
  [string]$ProjectDir = "\\wsl.localhost\Ubuntu\home\oleg\projects\useful_Claude"
)
$ErrorActionPreference = 'Stop'

$token = [Environment]::GetEnvironmentVariable('CLAUDE_CODE_OAUTH_TOKEN', 'User')
if (-not $token) {
  Write-Output 'ERROR: CLAUDE_CODE_OAUTH_TOKEN not found in user environment. Run: claude setup-token'
  exit 1
}

$secretsFile = Join-Path $ProjectDir "radars\$Slug\.secrets.ps1"
if (-not (Test-Path $secretsFile)) {
  New-Item -ItemType File -Path $secretsFile -Force | Out-Null
  Write-Output "created: radars/$Slug/.secrets.ps1"
}

$content = Get-Content $secretsFile -Raw -ErrorAction SilentlyContinue
if (-not $content) { $content = '' }

$line = '$env:CLAUDE_CODE_OAUTH_TOKEN = "' + $token + '"'

if ($content -match 'CLAUDE_CODE_OAUTH_TOKEN') {
  # replace the existing assignment line, keep everything else intact
  $updated = [regex]::Replace($content, '(?m)^\s*\$env:CLAUDE_CODE_OAUTH_TOKEN\s*=.*$', [System.Text.RegularExpressions.MatchEvaluator] { param($m) $line })
  Set-Content -Path $secretsFile -Value $updated -Encoding UTF8 -NoNewline
  Write-Output 'token line: UPDATED'
} else {
  Add-Content -Path $secretsFile -Value "`n# Long-lived OAuth token for headless collection (claude setup-token)"
  Add-Content -Path $secretsFile -Value $line
  Write-Output 'token line: ADDED'
}

# Verify without revealing the value
$check = Get-Content $secretsFile -Raw
if ($check -match '\$env:CLAUDE_CODE_OAUTH_TOKEN\s*=\s*"(sk-ant-oat01-[^"]+)"') {
  Write-Output ('verify: OK, len=' + $Matches[1].Length)
} else {
  Write-Output 'verify: FAILED - token line not found or malformed'
  exit 1
}
