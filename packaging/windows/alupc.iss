; Inno-Setup-Skript für den Windows-Installer von AluPC.
; Wird von GitHub Actions gebaut (siehe .github/workflows/build.yml).

#ifndef AppVersion
  #define AppVersion "0.14.1"
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

[Files]
Source: "..\..\dist\AluPC\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\AluPC"; Filename: "{app}\AluPC.exe"
Name: "{group}\AluPC deinstallieren"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AluPC"; Filename: "{app}\AluPC.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AluPC.exe"; Description: "AluPC jetzt starten"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v AluPC /f"; Flags: runhidden; RunOnceId: "RemoveAutostart"
