@echo off
setlocal
REM ProFiles post-install: add the install dir to PATH when the user asked
REM for it on the Install Options page. Runs before InstallFinalize,
REM elevated for per-machine installs, fresh installs only (NOT Installed).
REM
REM Env vars exported by the Briefcase wrapper (run_post_install.bat):
REM   ALLUSERS            1 = per-machine, 0 = per-user
REM   INSTALLER_PATH      path of the MSI being installed
REM   INSTALLER_UNATTENDED 1 = quiet install (msiexec /qn), else 0
REM   OPTION_ADD_TO_PATH  1 = checkbox checked (default), 0 = unchecked
REM %~dp0 is the _installer folder inside the install dir.
REM
REM Design: docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md
REM (section 6.3). Never fails the install for a PATH convenience: the
REM wrapper uses Return="check", so this script always exits 0 and logs.

set "LOG=%~dp0path_setup.log"
> "%LOG%" echo [%DATE% %TIME%] ProFiles post-install start
>>"%LOG%" echo OPTION_ADD_TO_PATH=%OPTION_ADD_TO_PATH% ALLUSERS=%ALLUSERS% UNATTENDED=%INSTALLER_UNATTENDED%

if not "%OPTION_ADD_TO_PATH%"=="1" (
    >>"%LOG%" echo Skipping PATH modification: option not selected.
    exit /b 0
)

REM Install dir = parent of this script's _installer folder; %%~fI resolves
REM the trailing ".." to an absolute path without a trailing backslash.
for %%I in ("%~dp0..") do set "INSTALL_DIR=%%~fI"
>>"%LOG%" echo Install dir: %INSTALL_DIR%

set "SCOPE=User"
if "%ALLUSERS%"=="1" set "SCOPE=Machine"

REM One PowerShell 5.1 shot: read PATH with DoNotExpandEnvironmentNames
REM (preserves REG_EXPAND_SZ content - naive tools would expand it), prepend
REM the install dir unless an identical entry (case-insensitive, trailing
REM backslash ignored) already exists, write back as ExpandString, then
REM broadcast WM_SETTINGCHANGE (0x1a) so running shells pick it up without
REM logging off. The ''='% substitution doubles any apostrophes in the
REM install dir so they cannot break the PowerShell single-quoted literal.
>>"%LOG%" 2>&1 powershell -NoProfile -ExecutionPolicy Bypass -Command "$opt=[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames; $k='Environment'; $r=[Microsoft.Win32.Registry]::CurrentUser; if('%SCOPE%' -eq 'Machine'){$k='SYSTEM\CurrentControlSet\Control\Session Manager\Environment'; $r=[Microsoft.Win32.Registry]::LocalMachine}; $key=$r.OpenSubKey($k,$true); $old=[string]$key.GetValue('Path','',$opt); $dir='%INSTALL_DIR:'=''%'.TrimEnd('\'); $rest=@($old -split ';' | Where-Object {$_ -and ($_.TrimEnd('\') -ine $dir)}); $key.SetValue('Path', (@($dir)+$rest) -join ';', [Microsoft.Win32.RegistryValueKind]::ExpandString); $key.Close(); Add-Type -MemberDefinition '[DllImport(\"user32.dll\", SetLastError=true, CharSet=CharSet.Auto)] public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);' -Name NativeMethods -Namespace ProFiles.Installer | Out-Null; $res=[UIntPtr]::Zero; [ProFiles.Installer.NativeMethods]::SendMessageTimeout([IntPtr]0xffff, 0x1a, [UIntPtr]::Zero, 'Environment', 2, 2000, [ref]$res) | Out-Null"
if errorlevel 1 >>"%LOG%" echo WARNING: PATH update failed; install continues.

exit /b 0
