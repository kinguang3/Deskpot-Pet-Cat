; ============================================================================
;  GBC Nina 安装器脚本（Inno Setup 6）
;
;  前置步骤：先用 PyInstaller 构建出 dist\GBC.Nina.v0.1.2\ 目录
;      Remove-Item -Recurse -Force dist\GBC.Nina.v0.1.2, build
;      .\.venv\Scripts\python.exe -m PyInstaller --noconfirm GBC.Nina.v0.1.2.spec
;
;  编译（需先安装 Inno Setup 6.x）：
;      "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" GBC.Nina.installer.iss
;  或用 Inno Setup IDE 打开本文件后按 F9。
;  产物：dist\installer\GBC.Nina.v0.1.2-setup.exe
;
;  设计要点：
;  - 用户数据全部在 %APPDATA%\GBC Nina\，卸载默认**不删**，可由用户确认后再删
;  - 安装目录只读也能正常运行：程序已不再往安装目录写任何文件
;  - 便携模式：程序目录旁放 portable.txt，paths.py 据此把数据写在旁边
; ============================================================================

#define AppName "GBC Nina"
#define AppVersion "0.1.2"
#define AppPublisher "kinguang3"
#define AppURL "https://github.com/kinguang3/Deskpot-Pet-Cat"
#define AppExeName "GBC.Nina.v0.1.2.exe"
#define SourceDir "dist\GBC.Nina.v0.1.2"

[Setup]
AppId={{7C3A1F52-9B4E-4D8A-A6C1-2E5B8D0F3A47}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=auto
OutputDir=dist\installer
OutputBaseFilename=GBC.Nina.v{#AppVersion}-setup
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; 产物约 350MB，需要 LZMA2 实压缩
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0

[Languages]
Name: "chinese"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinese.WelcomeLabel1=安装 {#AppName} v{#AppVersion}
chinese.WelcomeLabel2=即将在你的电脑上安装桌宠程序。%n%n程序文件会放到 [INSTDIR]；%n你的配置与互动记忆单独存放在：%n%APPDATA%\GBC Nina%n%n卸载程序时默认保留这些数据。
chinese.FinalAbout=首次运行会弹出隐私协议，说明麦克风与云端转写的数据处理方式。%n语音功能默认关闭，需要你在「设置」里主动开启。
chinese.UninstallDataPrompt=是否同时删除 Nina 的配置与互动记忆？%n%n路径：%APPDATA%\GBC Nina%n%n选择「否」将保留这些数据。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"
Name: "startmenuicon"; Description: "创建开始菜单快捷方式"; GroupDescription: "附加任务:"; Flags: checkedonce
Name: "autostart"; Description: "开机自动启动 Nina"; GroupDescription: "附加任务:"; Flags: unchecked
Name: "portablemode"; Description: "便携模式（配置与记忆写在程序目录旁，适合放 U 盘）"; GroupDescription: "附加任务:"

[Files]
; PyInstaller onedir 产物整体拷贝
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{group}\项目主页"; Filename: "{#AppURL}"; Tasks: startmenuicon
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// 便携模式：程序目录旁放 portable.txt，src/utils/paths.py 会识别
procedure CurStepChanged(CurStep: TSetupStep);
var
  MarkerPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    MarkerPath := ExpandConstant('{app}\portable.txt');
    if WizardIsTaskSelected('portablemode') then
      SaveStringToFile(MarkerPath, 'portable mode', False)
    else if FileExists(MarkerPath) then
      DeleteFile(MarkerPath);  // 关掉便携模式时清理旧标记
  end;
end;

// 用户数据（%APPDATA%\GBC Nina）默认保留，仅在用户确认后删除。
// 放在 usPostUninstall：此时程序文件已删完，但用户数据目录还在，
// 可以先问再删，一次判断搞定。
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  RemoveData: Boolean;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  DataDir := ExpandConstant('{userappdata}\GBC Nina');
  if not DirExists(DataDir) then
    Exit;

  RemoveData := True;
  if not WizardSilent then
    RemoveData :=
      MsgBox(FMsg('chinese.UninstallDataPrompt'), mbConfirmation, MB_YESNO) = IDYES;

  if RemoveData then
  begin
    if DelTree(DataDir, True, True, True) then
      Log('User data removed: ' + DataDir)
    else
      Log('Failed to remove user data: ' + DataDir);
  end
  else
    Log('User data kept: ' + DataDir);
end;
