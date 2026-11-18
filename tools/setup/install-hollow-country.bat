@echo off
rem Hollow Country guided server install: a dry run first; it changes nothing until you say yes.
setlocal
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
set "HCPY="
where py >nul 2>nul && set "HCPY=py -3"
if not defined HCPY where python >nul 2>nul && set "HCPY=python"
if not defined HCPY (
  echo Python 3 was not found. Install it from python.org with "Add python.exe to PATH" ticked, then run this again.
  if not defined HC_NO_PAUSE pause
  exit /b 2
)
%HCPY% -m tools.setup.friend_install %*
set "HCCODE=%ERRORLEVEL%"
echo.
if not defined HC_NO_PAUSE pause
exit /b %HCCODE%
