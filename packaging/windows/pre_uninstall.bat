@echo off
setlocal
REM ProFiles pre-uninstall: remove the PATH entry this install added.
REM Runs after InstallInitialize and before RemoveFiles, so %~dp0 is still
REM valid and only the PATH registry value is touched - never .profiles
REM configs, logs or any other user data.
REM
REM Env vars exported by the Briefcase wrapper (run_pre_uninstall.bat):
REM   INSTALLER_UNATTENDED 1 = quiet uninstall (msiexec /x /qn), else 0
REM There is no scope flag: the script clears the entry from BOTH hives,
REM ignoring the one it cannot write in the current context (a per-user
REM uninstall fails to open HKLM - that is success, not an error).
REM %~dp0 is the _installer folder inside the (still present) install dir.
REM
REM Design: docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md
REM (section 6.4). The uninstall must always succeed: this script always
REM exits 0 and logs; exact-match removal only (case-insensitive, trailing
REM backslash ignored) so no unrelated PATH entry is ever touched.

set "LOG=%~dp0path_setup.log"
>>"%LOG%" echo [%DATE% %TIME%] ProFiles pre-uninstall start (unattended=%INSTALLER_UNATTENDED%)

for %%I in ("%~dp0..") do set "INSTALL_DIR=%%~fI"
>>"%LOG%" echo Install dir: %INSTALL_DIR%

REM Same REG_EXPAND_SZ-safe edit as post_install: read with
REM DoNotExpandEnvironmentNames, filter out exactly the install dir entry,
REM write back as ExpandString, broadcast WM_SETTINGCHANGE (0x1a). The
REM '%'='% substitution doubles any apostrophes in the install dir.
>>"%LOG%" 2>&1 powershell -NoProfile -ExecutionPolicy Bypass -Command "$opt=[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames; $dir='%INSTALL_DIR:'=''%'.TrimEnd('\'); foreach($s in 'User','Machine'){ if($s -eq 'Machine'){$k='SYSTEM\CurrentControlSet\Control\Session Manager\Environment'; $r=[Microsoft.Win32.Registry]::LocalMachine}else{$k='Environment'; $r=[Microsoft.Win32.Registry]::CurrentUser}; try{$key=$r.OpenSubKey($k,$true)}catch{$key=$null}; if($key){ $old=[string]$key.GetValue('Path','',$opt); $p=@($old -split ';' | Where-Object {$_ -and ($_.TrimEnd('\') -ine $dir)}); $key.SetValue('Path', ($p -join ';'), [Microsoft.Win32.RegistryValueKind]::ExpandString); $key.Close() } }; Add-Type -MemberDefinition '[DllImport(\"user32.dll\", SetLastError=true, CharSet=CharSet.Auto)] public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);' -Name NativeMethods -Namespace ProFiles.Installer | Out-Null; $res=[UIntPtr]::Zero; [ProFiles.Installer.NativeMethods]::SendMessageTimeout([IntPtr]0xffff, 0x1a, [UIntPtr]::Zero, 'Environment', 2, 2000, [ref]$res) | Out-Null"
if errorlevel 1 >>"%LOG%" echo WARNING: PATH cleanup failed; uninstall continues.

exit /b 0
