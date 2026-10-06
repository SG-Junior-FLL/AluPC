# Windows-CI: einen „Mobilen Hotspot“ nachbauen, ohne WLAN-Karte.
# Loopback-Adapter → transparentes Docker-Netz darauf (das „Handy“ ist später ein Windows-Container darin)
# → Windows-Internetfreigabe (ICS, derselbe Dienst wie beim Mobilen Hotspot) auf diesen Adapter:
#    der PC bekommt 192.168.137.1, der Windows-DNS lauscht auf 0.0.0.0:53, NAT ins Internet läuft.
$ErrorActionPreference = 'Stop'
for ($i = 0; $i -lt 3 -and -not (Get-Command devcon64.exe -ErrorAction SilentlyContinue); $i++) {
  choco install devcon.portable -y --no-progress | Out-Null  # Download klappt nicht immer beim ersten Mal
  if (-not (Get-Command devcon64.exe -ErrorAction SilentlyContinue)) { Start-Sleep 10 }
}
devcon64.exe install "$env:windir\inf\netloop.inf" '*msloop' | Out-Null
Start-Sleep 5
$lb = Get-NetAdapter | Where-Object InterfaceDescription -like '*Loopback*' | Select-Object -First 1
docker network create -d transparent --subnet=192.168.137.0/24 --gateway=192.168.137.1 `
  -o com.docker.network.windowsshim.interface="$($lb.Name)" hotspot | Out-Null
Start-Sleep 8
$priv = Get-NetAdapter | Where-Object { $_.Name -eq "vEthernet ($($lb.Name))" } | Select-Object -First 1
$pubIdx = (Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Sort-Object RouteMetric | Select-Object -First 1).InterfaceIndex
$pub = Get-NetAdapter -InterfaceIndex $pubIdx
$m = New-Object -ComObject HNetCfg.HNetShare
foreach ($c in $m.EnumEveryConnection) {
  $n = $m.NetConnectionProps.Invoke($c).Name
  if ($n -eq $pub.Name) { $m.INetSharingConfigurationForINetConnection.Invoke($c).EnableSharing(0) }
  if ($n -eq $priv.Name) { $m.INetSharingConfigurationForINetConnection.Invoke($c).EnableSharing(1) }
}
for ($i = 0; $i -lt 30 -and -not (Get-NetIPAddress -IPAddress 192.168.137.1 -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
$dns = Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue | Where-Object LocalAddress -eq '0.0.0.0'
"Hotspot nachgebaut: $($priv.Name) = 192.168.137.1, Internet über $($pub.Name), Windows-DNS: $(if ($dns) {'0.0.0.0:53'} else {'?'})"
if (-not (Get-NetIPAddress -IPAddress 192.168.137.1 -ErrorAction SilentlyContinue)) { throw 'ICS gab keine 192.168.137.1' }
