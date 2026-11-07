$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$pidFile = Join-Path $projectRoot '.server-pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Output 'Khong co phien chay nen duoc ghi nhan.'; exit }
$serverPid = 0
if (-not [int]::TryParse((Get-Content -LiteralPath $pidFile -Raw).Trim(), [ref]$serverPid)) { throw 'PID khong hop le.' }
$serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid"
if ($serverProcess -and $serverProcess.CommandLine -like ('*' + $projectRoot.Replace('\','/') + '/server.py*')) { Stop-Process -Id $serverPid; Write-Output 'Da dung chatbot.' }
elseif ($serverProcess) { throw 'Tien trinh khong khop chatbot; khong dung tien trinh nay.' }
else { Write-Output 'Chatbot da dung.' }
