<#
  setup-key.ps1 - one-time per-laptop setup of the OpenAI key for AI Home Tutor.

  Stores the key as a USER environment variable via setx. The key is NEVER
  written to a file, baked into the image, or committed to git. Docker Compose
  reads it at run time through ${OPENAI_API_KEY}. Re-run any time to rotate.

  Usage:  pwsh -File setup-key.ps1      (then open a new terminal, docker compose up -d)
#>

Write-Host "AI Home Tutor - OpenAI key setup" -ForegroundColor Cyan
Write-Host "Stored as a user environment variable. Not written to any file, image, or git." -ForegroundColor DarkGray
Write-Host ""

# Read the key without displaying it on screen.
$secure = Read-Host "Paste your OpenAI API key (input hidden)" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if ($null -eq $key) { $key = "" }
$key = $key.Trim()

if ($key.Length -lt 20) {
    Write-Host "No valid key entered - nothing changed." -ForegroundColor Red
    exit 1
}

# Persist for future terminals, and set it for this session too.
setx OPENAI_API_KEY "$key" | Out-Null
$env:OPENAI_API_KEY = $key

$proxy = Read-Host "Is this laptop behind a corporate proxy that intercepts HTTPS? (y/N)"
if ($proxy -match '^(y|yes)$') {
    setx OPENAI_INSECURE_SKIP_VERIFY "1" | Out-Null
    $env:OPENAI_INSECURE_SKIP_VERIFY = "1"
    Write-Host "  -> OPENAI_INSECURE_SKIP_VERIFY=1 (dev-only; prefer OPENAI_CA_BUNDLE for a real fix)." -ForegroundColor Yellow
}

$masked = "{0}...{1} (len {2})" -f $key.Substring(0, [Math]::Min(7, $key.Length)), $key.Substring([Math]::Max(0, $key.Length - 4)), $key.Length
Write-Host ""
Write-Host "Key stored for your user account: $masked" -ForegroundColor Green
Write-Host "Next: open a NEW terminal where docker-compose.yml is, then run:" -ForegroundColor Green
Write-Host "    docker compose up -d" -ForegroundColor Green
