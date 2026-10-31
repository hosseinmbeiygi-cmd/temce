Get-CimInstance Win32_Process -Filter "name='node.exe'" |
  Select-Object ProcessId, ParentProcessId, CreationDate, @{n='MB';e={[math]::Round($_.WorkingSetSize/1MB,1)}}, @{n='Cmd';e={ if ($_.CommandLine) { $_.CommandLine.Substring(0, [Math]::Min(180, $_.CommandLine.Length)) } }} |
  Format-List
