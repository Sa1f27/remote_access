@echo off
echo Remote Desktop Application Setup
echo ================================

echo.
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)

@REM echo.
@REM echo [2/4] Installing system audio dependencies...
@REM choco install portaudio -y
@REM if %errorlevel% neq 0 (
@REM     echo WARNING: PortAudio installation failed. PyAudio may not work properly.
@REM     echo Please install PortAudio manually or use conda: conda install pyaudio
@REM )

echo.
echo [3/4] Creating SSL certificate for HTTPS...
if not exist "server.crt" (
    echo Creating self-signed certificate...
    openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    if %errorlevel% neq 0 (
        echo WARNING: SSL certificate creation failed. 
        echo The server will run on HTTP instead of HTTPS.
        echo For production use, please create proper SSL certificates.
    )
)

echo.
echo [4/4] Getting system UUID for allowed.json...
for /f "skip=1 tokens=*" %%i in ('wmic csproduct get uuid ^| findstr /r /v "^$"') do (
    set UUID=%%i
    goto :uuid_found
)
:uuid_found
set UUID=%UUID: =%
echo Your system UUID is: %UUID%
echo.
echo Please add this UUID to allowed.json on the server to authorize this client.

echo.
echo Setup completed successfully!
echo.
echo To start the server:
echo   python server.py --cert server.crt --key server.key
echo.
echo To start the client:
echo   python client.py wss://192.168.48.201:5444/ws
echo.
echo Note: Replace '192.168.48.201' with the actual server IP/domain if it changes
pause
