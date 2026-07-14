; =============================================================================
; ISRA Chatbot — Inno Setup 6 Windows Installer Script
; Produces: MachineAI_Chatbot_Setup.exe
; Target: Windows 10 (all builds), 64-bit
; =============================================================================

#define MyAppName      "ISRA Vision Chatbot"
#define MyAppVersion   "2.0.0"
#define MyAppPublisher "ISRA Vision"
#define MyAppExeName   "IsraChatbot.exe"
#define MyAppID        "{8B2F3C4D-1A2B-4E5F-9C0D-3E4F5A6B7C8D}"

[Setup]
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
; Windows 10 minimum (build 10240 = RTM). All builds of Win10 and Win11 are supported.
MinVersion=10.0.10240
; 64-bit only (Ollama and PyTorch require x64)
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
; Show a friendly message on unsupported OS
SetupMutex={#MyAppID}_Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Main application files
Source: "..\dist\IsraChatbot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "Launch the ISRA Vision AI Chatbot"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "Launch the ISRA Vision AI Chatbot"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Launch after install (nowait = non-blocking, so installer exits cleanly)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user data directory on uninstall (optional — comment out to keep user data)
; Type: filesandordirs; Name: "{localappdata}\ISRAVision\ISRAChatbot"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Friendly error if somehow running on wrong arch
  if not Is64BitInstallMode() then
  begin
    MsgBox('This application requires a 64-bit version of Windows 10 or later.', mbError, MB_OK);
    Result := False;
  end;
end;
