#ifndef AppVersion
  #error AppVersion is required
#endif
#define AppName "MacroNet Transport"

[Setup]
AppId={{E867E23E-D3AD-4BE1-B249-ABF8243EAC60}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Héctor Alonso Benítez García
AppPublisherURL=https://github.com/VanLinux/macronet-transport
AppSupportURL=mailto:prof.benitezgh@gmail.com
DefaultDirName={localappdata}\Programs\MacroNet Transport
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\dist\installer
OutputBaseFilename=MacroNet-Transport-{#AppVersion}-Windows-x64-Setup
SetupIconFile=..\..\build\windows\MacroNet.ico
UninstallDisplayIcon={app}\MacroNet.exe
LicenseFile=..\..\LICENSE
InfoAfterFile=LEEME.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#AppName} (incluye SUMO)

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\..\dist\MacroNet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MacroNet Transport"; Filename: "{app}\MacroNet.exe"; WorkingDir: "{userdocs}"
Name: "{autodesktop}\MacroNet Transport"; Filename: "{app}\MacroNet.exe"; WorkingDir: "{userdocs}"
Name: "{group}\Desinstalar MacroNet Transport"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\MacroNet.exe"; Description: "Abrir MacroNet Transport"; Flags: nowait postinstall skipifsilent

