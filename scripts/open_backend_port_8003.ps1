# Run in PowerShell as Administrator once so phones on the same WiFi can reach Docker-mapped port 8003.
# Docker publishes backend as host TCP 8003 -> container 8000.

$ruleName = "kAIzen - Backend TCP 8003 (dev)"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Firewall rule already exists: $ruleName"
    exit 0
}

New-NetFirewallRule -DisplayName $ruleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort 8003 `
    -Profile Private, Domain `
    -Description "Allows LAN access to FastAPI backend (Docker 8003:8000) for Flutter device testing."

Write-Host "Created inbound rule for TCP 8003 on Private/Domain profiles."
Write-Host "If the phone still cannot connect, confirm PC IPv4 (ipconfig) matches DEFAULT_LAN_HOST in app_config / dart-define."
