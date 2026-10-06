# Windows-Internetfreigabe (ICS) auf den Hotspot-Adapter legen – wie es der Mobile Hotspot beim Start tut.
# Wird beim Nachbauen aufgerufen und im Test erneut, wenn AluPC „den Hotspot startet“ (nach der Port-53-Übernahme).
param([string]$Private = '')
$ErrorActionPreference = 'Stop'
if (-not $Private) {
  $lb = Get-NetAdapter | Where-Object InterfaceDescription -like '*Loopback*' | Select-Object -First 1
  $Private = "vEthernet ($($lb.Name))"
}
$pubIdx = (Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Where-Object { (Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue).Name -ne $Private } |
  Sort-Object RouteMetric | Select-Object -First 1).InterfaceIndex
$pub = Get-NetAdapter -InterfaceIndex $pubIdx
$m = New-Object -ComObject HNetCfg.HNetShare
foreach ($c in $m.EnumEveryConnection) {  # erst aus (falls noch eingetragen), dann neu an
  $n = $m.NetConnectionProps.Invoke($c).Name
  if ($n -eq $pub.Name -or $n -eq $Private) { $m.INetSharingConfigurationForINetConnection.Invoke($c).DisableSharing() }
}
foreach ($c in $m.EnumEveryConnection) {
  $n = $m.NetConnectionProps.Invoke($c).Name
  if ($n -eq $pub.Name) { $m.INetSharingConfigurationForINetConnection.Invoke($c).EnableSharing(0) }
  if ($n -eq $Private) { $m.INetSharingConfigurationForINetConnection.Invoke($c).EnableSharing(1) }
}
for ($i = 0; $i -lt 30 -and -not (Get-NetIPAddress -IPAddress 192.168.137.1 -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
"Freigabe: $Private → Internet über $($pub.Name)"
