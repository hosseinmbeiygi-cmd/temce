Get-CimInstance Win32_Process -Filter "name='chrome.exe'" |
  Where-Object { $_.CommandLine -match 'ms-playwright|--headless' } |
  Select-Object ProcessId, @{n='Cmd';e={ if ($_.CommandLine) { $_.CommandLine.Substring(0, [Math]::Min(200, $_.CommandLine.Length)) } }} |
  Format-Table -AutoSize
Get-CimInstance Win32_OperatingSystem |
  Select-Object @{n='FreeGB';e={[math]::Round($_.FreePhysicalMemory/1MB,2)}}, @{n='TotalGB';e={[math]::Round($_.TotalVisibleMemorySize/1MB,2)}} |
  Format-List
