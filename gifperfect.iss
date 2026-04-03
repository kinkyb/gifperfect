[Setup]
AppName=GIF Perfect
AppVersion=1.1.6
AppVerName=GIF Perfect 1.1.6
AppPublisher=GIF Perfect
AppPublisherURL=https://gifperfect.com
AppSupportURL=https://gifperfect.com
AppUpdatesURL=https://gifperfect.com
DefaultDirName={autopf}\GifPerfect
DefaultGroupName=GIF Perfect
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=GifPerfect-setup
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Install without admin if possible, offer elevation dialog if needed
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\GifPerfect\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\GIF Perfect"; Filename: "{app}\GifPerfect.exe"
Name: "{group}\{cm:UninstallProgram,GIF Perfect}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\GIF Perfect"; Filename: "{app}\GifPerfect.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GifPerfect.exe"; Description: "{cm:LaunchProgram,GIF Perfect}"; Flags: nowait postinstall skipifsilent
