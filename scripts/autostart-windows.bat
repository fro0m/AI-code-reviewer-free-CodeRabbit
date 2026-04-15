@echo off
REM Code Scanner Autostart Management - Windows (Task Scheduler)
REM Usage: autostart-windows.bat [install|remove|status] "<cli_command>"
REM Example: autostart-windows.bat install "C:\path\to\project1 -c C:\path\to\config1 C:\path\to\project2 -c C:\path\to\config2"

setlocal enabledelayedexpansion

set "TASK_NAME=CodeScanner"
set "SCRIPT_DIR=%~dp0"

if "%~1"=="" goto :usage
if "%~1"=="install" goto :install
if "%~1"=="remove" goto :remove
if "%~1"=="status" goto :status
goto :usage

:usage
echo Code Scanner Autostart Management - Windows
echo.
echo Usage: %~nx0 ^<command^> "<cli_command>"
echo.
echo Commands:
echo   install ^<cli_command^>  Install autostart task with full CLI command
echo   remove                      Remove autostart task
echo   status                      Check task status
echo.
echo Examples:
echo   %~nx0 install "C:\path\to\project1 -c C:\path\to\config1 C:\path\to\project2 -c C:\path\to\config2"
echo   %~nx0 remove
echo   %~nx0 status
exit /b 1

:install
if "%~2"=="" (
    echo [ERROR] Missing CLI command argument
    goto :usage
)

set "CLI_ARGS=%~2"

REM Reinstall app to ensure latest version
echo [INFO] Reinstalling code-scanner to ensure latest version...
where uv >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Using uv to reinstall...
    uv pip install --upgrade code-scanner 2>nul || (
        uv pip install --upgrade -e . 2>nul || (
            echo [WARNING] uv reinstall skipped
        )
    )
) else (
    where pip >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] Using pip to reinstall...
        pip install --upgrade code-scanner 2>nul || (
            pip install --upgrade -e . 2>nul || (
                echo [WARNING] pip reinstall skipped
            )
        )
    ) else (
        echo [WARNING] No package manager found. Please manually run: pip install --upgrade code-scanner
    )
)

REM Find code-scanner
set "SCANNER_CMD="
where code-scanner >nul 2>&1 && set "SCANNER_CMD=code-scanner"
if "%SCANNER_CMD%"=="" (
    where uv >nul 2>&1 && set "SCANNER_CMD=uv run code-scanner"
)
if "%SCANNER_CMD%"=="" (
    echo [ERROR] Could not find code-scanner or uv. Please install code-scanner first.
    exit /b 1
)

echo [INFO] Testing code-scanner launch...
echo [INFO] Command: %SCANNER_CMD% %CLI_ARGS%
echo.

REM Test launch - run for 5 seconds and capture output
set "TEST_OUTPUT=%TEMP%\code-scanner-test.txt"
start /b cmd /c ""%SCANNER_CMD%" %CLI_ARGS% 2>&1" > "%TEST_OUTPUT%" 2>&1
timeout /t 5 /nobreak >nul 2>&1

REM Kill any running code-scanner processes from test
taskkill /f /im code-scanner.exe >nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq code-scanner*" >nul 2>&1

REM Display output
if exist "%TEST_OUTPUT%" (
    type "%TEST_OUTPUT%"
    echo.

    REM Check for success indicators
    findstr /i "Scanner running Scanner loop started Scanner thread started" "%TEST_OUTPUT%" >nul 2>&1
    if not errorlevel 1 (
        echo [SUCCESS] Test launch succeeded - scanner started correctly.
        del "%TEST_OUTPUT%" >nul 2>&1
        goto :test_passed
    )

    REM Check for error indicators
    findstr /i "error failed exception traceback could not cannot refused" "%TEST_OUTPUT%" >nul 2>&1
    if not errorlevel 1 (
        echo [ERROR] Test launch failed. Please fix the issues above and try again.
        del "%TEST_OUTPUT%" >nul 2>&1
        exit /b 1
    )

    del "%TEST_OUTPUT%" >nul 2>&1
)

REM No clear success or failure - ask user
echo [WARNING] Could not automatically verify launch success.
echo [WARNING] Please check the output above and ensure code-scanner starts correctly.
set /p "RESPONSE=Continue with installation? (y/N): "
if /i not "%RESPONSE%"=="y" (
    echo [ERROR] Installation cancelled.
    exit /b 1
)

:test_passed

REM Check for existing task
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Found existing autostart task.
    REM Try to read current command from wrapper script
    set "CURRENT_WRAPPER=%USERPROFILE%\.code-scanner\launch-wrapper.bat"
    if exist "!CURRENT_WRAPPER!" (
        echo.
        echo   Current: 
        REM Show last line of wrapper script (the actual command)
        for /f "usebackq delims=" %%a in ("!CURRENT_WRAPPER!") do set "CURRENT_CMD=%%a"
        echo   !CURRENT_CMD!
        echo   New:     %SCANNER_CMD% %CLI_ARGS%
        echo.
    )
    set /p "REPLACE=Replace existing configuration? (y/N): "
    if /i not "!REPLACE!"=="y" (
        echo [INFO] Installation cancelled.
        exit /b 0
    )
    echo [INFO] Removing existing task...
    schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
)

REM Create wrapper script with 60-second delay
set "HOME_DIR=%USERPROFILE%\.code-scanner"
if not exist "%HOME_DIR%" mkdir "%HOME_DIR%"

set "WRAPPER_SCRIPT=%HOME_DIR%\launch-wrapper.bat"
(
    echo @echo off
    echo REM Code Scanner launch wrapper with startup delay
    echo timeout /t 60 /nobreak ^>nul
    echo %SCANNER_CMD% %CLI_ARGS%
) > "%WRAPPER_SCRIPT%"

REM Create scheduled task to run at logon
echo [INFO] Creating scheduled task...
schtasks /create /tn "%TASK_NAME%" /tr "\"%WRAPPER_SCRIPT%\"" /sc onlogon /rl highest /f

if errorlevel 1 (
    echo [ERROR] Failed to create scheduled task.
    exit /b 1
)

echo [SUCCESS] Code Scanner autostart installed successfully!
echo.
echo [INFO] Useful commands:
echo   schtasks /query /tn "%TASK_NAME%"         # Check status
echo   schtasks /run /tn "%TASK_NAME%"           # Start manually
echo   schtasks /end /tn "%TASK_NAME%"           # Stop task
echo   schtasks /delete /tn "%TASK_NAME%" /f     # Remove task
exit /b 0

:remove
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] No autostart task found.
    exit /b 0
)

echo [INFO] Ending task if running...
schtasks /end /tn "%TASK_NAME%" >nul 2>&1

echo [INFO] Removing scheduled task...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

echo [INFO] Removing wrapper script...
del "%USERPROFILE%\.code-scanner\launch-wrapper.bat" >nul 2>&1

echo [SUCCESS] Code Scanner autostart removed.
exit /b 0

:status
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] No autostart task configured.
    exit /b 0
)

echo [INFO] Scheduled task status:
schtasks /query /tn "%TASK_NAME%" /v /fo list
exit /b 0
