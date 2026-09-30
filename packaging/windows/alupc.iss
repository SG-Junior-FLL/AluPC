; Inno-Setup-Skript für den Windows-Installer von AluPC.
; Wird von GitHub Actions gebaut (siehe .github/workflows/build.yml).

#ifndef AppVersion
  #define AppVersion "0.71.0"
#endif

[Setup]
AppId={{6E2B8C3A-4F1D-4B8E-9A57-3C1D2E7F0A11}
AppName=AluPC
AppVersion={#AppVersion}
AppPublisher=AluPC
DefaultDirName={autopf}\AluPC
DefaultGroupName=AluPC
OutputDir=..\..\dist
OutputBaseFilename=AluPC-Setup-{#AppVersion}
SetupIconFile=alupc.ico
UninstallDisplayIcon={app}\AluPC.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Symbol auf dem Desktop anlegen"; Flags: unchecked
Name: "handy"; Description: "AirPlay-Empfang mitinstallieren: uxplay-windows (Community-Paket mit UxPlay) und Bonjour – aus dem Internet über winget"; GroupDescription: "iPhone auf Monitor 2:"

[Files]
Source: "..\..\dist\AluPC\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\AluPC"; Filename: "{app}\AluPC.exe"
Name: "{group}\AluPC deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AluPC"; Filename: "{app}\AluPC.exe"; Tasks: desktopicon

[Run]
Filename: "{cmd}"; Parameters: "/C winget install --id Apple.Bonjour -e --silent --accept-source-agreements --accept-package-agreements"; StatusMsg: "Bonjour (AirPlay) wird installiert …"; Flags: runhidden waituntilterminated; Tasks: handy
Filename: "{cmd}"; Parameters: "/C winget install --id leapbtw.uxplay -e --silent --accept-source-agreements --accept-package-agreements"; StatusMsg: "AirPlay-Empfänger (uxplay-windows) wird installiert …"; Flags: runhidden waituntilterminated; Tasks: handy
; Firewall: Handy-Steuerung (8765…8774) und AirPlay – nur private Netzwerke (braucht Adminrechte, sonst übersprungen)
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""AluPC Handy"" dir=in action=allow protocol=TCP localport=8765-8774 profile=private,domain"; StatusMsg: "Firewall wird eingerichtet …"; Flags: runhidden waituntilterminated; Check: IsAdminInstallMode
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""AluPC AirPlay"" dir=in action=allow protocol=TCP localport=7000,7001,7100 profile=any"; Flags: runhidden waituntilterminated; Check: IsAdminInstallMode
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""AluPC AirPlay"" dir=in action=allow protocol=UDP localport=5353,6000,6001,7011 profile=any"; Flags: runhidden waituntilterminated; Check: IsAdminInstallMode
Filename: "{app}\AluPC.exe"; Description: "AluPC jetzt starten"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v AluPC /f"; Flags: runhidden; RunOnceId: "RemoveAutostart"
; Anmeldung mit Fingerabdruckmodul: Anmeldebaustein bei Windows abmelden, gespeichertes (verschlüsseltes) Passwort löschen
Filename: "{cmd}"; Parameters: "/C reg delete ""HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\Credential Providers\{{82F9D550-26AE-40CC-B8F7-F9805D8AD0EF}"" /f & reg delete ""HKLM\SOFTWARE\Classes\CLSID\{{82F9D550-26AE-40CC-B8F7-F9805D8AD0EF}"" /f & del /f /q ""%ProgramData%\AluPC\fingerprint-windows.cfg"" ""%ProgramData%\AluPC\fingerprint-*.slots"" & reg delete HKLM\SOFTWARE\AluPC /f"; Flags: runhidden; RunOnceId: "RemoveFingerprintLogin"; Check: IsAdminInstallMode
; Vorauswahl „Fingerabdruck“ auf dem Sperrbildschirm zurücknehmen (nur wenn sie von AluPC stammt)
Filename: "{cmd}"; Parameters: "/C reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\System /v DefaultCredentialProvider | find /i ""{{82F9D550-26AE-40CC-B8F7-F9805D8AD0EF}"" && reg delete HKLM\SOFTWARE\Policies\Microsoft\Windows\System /v DefaultCredentialProvider /f"; Flags: runhidden; RunOnceId: "RemoveFingerprintDefault"; Check: IsAdminInstallMode
