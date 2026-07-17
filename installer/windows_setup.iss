; =============================================================================
; ISRA Chatbot — Inno Setup 6 Windows Installer Script
; Produces: MachineAI_Chatbot_Setup.exe
; Target: Windows 10 (all builds, 64-bit) and Windows 11
; =============================================================================

#define MyAppName      "ISRA Vision Chatbot"
#define MyAppVersion   "2.0.0"
#define MyAppPublisher "ISRA Vision"
#define MyAppExeName   "IsraChatbot.exe"

[Setup]
; NOTE: Use {{ to produce a literal { in Inno Setup
AppId={{8B2F3C4D-1A2B-4E5F-9C0D-3E4F5A6B7C8D}}
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
; NOTE: SolidCompression must be 'no' when DiskSpanning is enabled
SolidCompression=no
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
; Windows 10 minimum (build 10240 = RTM)
MinVersion=10.0.10240
; 64-bit only
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
SetupMutex=ISRAVisionChatbot_Setup
; Allow installers larger than 2 GB (splits into .exe + .bin companion files)
DiskSpanningEnabled=yes
DiskSliceSize=2100000000

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist\IsraChatbot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "Launch the ISRA Vision AI Chatbot"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "Launch the ISRA Vision AI Chatbot"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Uncomment to wipe user data on uninstall:
; Type: filesandordirs; Name: "{localappdata}\ISRAVision\ISRAChatbot"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not Is64BitInstallMode() then
  begin
    MsgBox('This application requires a 64-bit version of Windows 10 or later.' + #13#10 +
           'Please upgrade your system and try again.', mbError, MB_OK);
    Result := False;
  end;
end;
