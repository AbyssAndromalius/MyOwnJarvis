@echo off
echo ========================================
echo   Assistant Personnel Local - Client
echo ========================================
echo.

REM Check if config.yaml exists
if not exist "config.yaml" (
    echo WARNING: config.yaml not found!
    echo Creating default config.yaml...
    echo.
    
    (
        echo server:
        echo   host: "127.0.0.1"
        echo   port: 10090
        echo.
        echo orchestrator:
        echo   url: "http://localhost:10080"
        echo   timeout_seconds: 60
        echo.
        echo session:
        echo   max_history: 20
        echo.
        echo tts:
        echo   enabled: true
        echo   voice_preference:
        echo     - "Microsoft Aria Online (Natural) - English (United States)"
        echo     - "Microsoft Guy Online (Natural) - English (United States)"
    ) > config.yaml
    
    echo config.yaml created!
    echo.
)

REM Check if executable exists
if not exist "assistant-client.exe" (
    echo Building the application...
    go build -o assistant-client.exe
    if errorlevel 1 (
        echo.
        echo ERROR: Build failed!
        echo Make sure Go 1.22+ is installed and available in PATH.
        pause
        exit /b 1
    )
    echo Build successful!
    echo.
)

echo Starting the client...
echo.
echo The interface will be available at: http://localhost:10090
echo Open this URL in Microsoft Edge for best experience.
echo.
echo Press Ctrl+C to stop the server.
echo.

assistant-client.exe

pause
