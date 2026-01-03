
# Code Scanner Service Auto-Start for Windows

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("Enable", "Disable", "Status")]
    [string]$Action
)

$TaskName = "CodeScannerService"

if ($Action -eq "Enable") {
    $PythonPath = (Get-Command python).Source
    if (-not $PythonPath) {
        Write-Error "Python not found in PATH"
        exit 1
    }
    
    $WorkDir = Get-Location
    
    # Trigger on Logon
    $Trigger = New-ScheduledTaskTrigger -AtLogon
    # Small delay to ensure network is up
    $Trigger.Delay = 'PT10S' 

    # Action: uv run code-scanner service
    # Ideally use python -m ..., assuming deps installed in venv
    # But using uv run is safer if we are in dev env.
    
    # To be robust, let's find uv
    $UvPath = (Get-Command uv).Source
    if ($UvPath) {
        $ActionInfo = New-ScheduledTaskAction -Execute $UvPath -Argument "run code-scanner service" -WorkingDirectory $WorkDir
    } else {
        # Fallback to python directly if uv not found (e.g. installed package)
        $ActionInfo = New-ScheduledTaskAction -Execute $PythonPath -Argument "-m code_scanner service" -WorkingDirectory $WorkDir
    }

    Register-ScheduledTask -TaskName $TaskName -Trigger $Trigger -Action $ActionInfo -Description "Code Scanner Background Service" -Force
    
    Write-Host "Code Scanner service enabled and started."
    Write-Host "Use 'code-scanner add <path>' to start monitoring projects."
}
elseif ($Action -eq "Disable") {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Code Scanner service disabled."
}
elseif ($Action -eq "Status") {
    Get-ScheduledTask | Where-Object { $_.TaskName -eq $TaskName }
}
