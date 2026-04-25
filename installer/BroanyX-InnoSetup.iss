; BroanyX Browser — Inno Setup Script
; ======================================
; Download Inno Setup free: https://jrsoftware.org/isdl.php
; Then right-click this file → "Compile" OR run:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\BroanyX-InnoSetup.iss
;
; Output: dist\BroanyX-Setup.exe

#define AppName      "BroanyX Browser"
#define AppVersion   "1.0.0"
#define AppPublisher "BroanyX"
#define AppURL       "https://github.com/Broanyx/BroanyX-browser"
#define AppExeName   "BroanyX.exe"
#define SourceDir    "..\dist\BroanyX"

[Setup]
AppId={{B8A3C2D4-7F6E-4A1B-9C5D-3E2F8A0B1D4E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=BroanyX-Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Ask user if they want a desktop icon
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Copy everything from the PyInstaller output folder
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start menu
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

; Desktop shortcut (only if user checked the box)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch after install
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
