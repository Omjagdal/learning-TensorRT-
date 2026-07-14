; =============================================================================
; ISRA Chatbot — Inno Setup 6 Windows Installer Script
; =============================================================================
; Produces: MachineAI_Chatbot_Setup.exe
;
; To compile:
;   1. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
;   2. Open this file in the Inno Setup IDE, or run:
;      iscc installer\windows_setup.iss
;
; This script expects the following to already exist (built by build_windows_exe.bat):
;   dist\IsraChatbot\          <-- PyInstaller output folder
; =============================================================================

#define MyAppName      "ISRA Vision Chatbot"
#define MyAppVersion   "2.0.0"
#define MyAppPublisher "ISRA Vision"
#define MyAppExeName   "IsraChatbot.exe"
#define MyAppID        "{8B2F3C4D-1A2B-4E5F-9C0D-3E4F5A6B7C8D}"

[Setup]
; Unique app identifier — do NOT change after first release
AppId={#MyAppID}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=..\dist\installer
OutputBaseFilename=MachineAI_Chatbot_Setup
SetupIconFile=..\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
; Show a welcome page with the app name
WizardSmallImageFile=..\icon.ico
; Minimum Windows 10
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Copy the entire PyInstaller output folder
Source: "..\dist\IsraChatbot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Desktop shortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon; \
    Comment: "Launch the ISRA Vision AI Chatbot"
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\{#MyAppExeName}"; \
    Comment: "Launch the ISRA Vision AI Chatbot"
; Uninstall from Start Menu
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Launch the app after install (optional)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user data created by the app on uninstall (optional — comment out to preserve data)
; Type: filesandordirs; Name: "{localappdata}\ISRAVision\ISRAChatbot"
