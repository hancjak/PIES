; Inno Setup skript pro PIES – per-user instalace (bez admin práv).
; Verze se předává z buildu:  ISCC.exe /DMyAppVersion=v13.8 installer\PIES.iss

#define MyAppName "PIES"
#define MyAppExeName "PIES_System.exe"
#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif

[Setup]
AppId={{B4F2A1C7-6E2D-4E2A-9F3B-1A2B3C4D5E6F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Jakub Hanc
DefaultDirName={localappdata}\Programs\PIES
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=PIES_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Korektně zavře běžící aplikaci přes Restart Manager místo chyby "soubor je používán"
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "desktopicon"; Description: "Vytvořit zástupce na ploše"; GroupDescription: "Zástupci:"

[Files]
Source: "..\dist\PIES_System.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\PIES"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\PIES"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Po instalaci (i tiché) znovu spustí aplikaci
Filename: "{app}\{#MyAppExeName}"; Description: "Spustit PIES"; Flags: nowait postinstall
