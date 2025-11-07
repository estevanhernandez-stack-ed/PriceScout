@echo off
REM ====================================================================
REM Price Scout Deployment Folder Preparation Script
REM ====================================================================
REM This script creates a deployment-ready folder with all necessary files
REM ====================================================================

echo.
echo ========================================
echo   Price Scout Deployment Preparation
echo ========================================
echo.

REM Set the deployment folder name
set DEPLOY_FOLDER=deployment_pricescout_v2
set TIMESTAMP=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%

echo Creating deployment folder: %DEPLOY_FOLDER%
echo.

REM Remove old deployment folder if it exists
if exist "%DEPLOY_FOLDER%" (
    echo Removing old deployment folder...
    rmdir /s /q "%DEPLOY_FOLDER%"
)

REM Create main deployment folder structure
mkdir "%DEPLOY_FOLDER%"
mkdir "%DEPLOY_FOLDER%\app"
mkdir "%DEPLOY_FOLDER%\app\modes"
mkdir "%DEPLOY_FOLDER%\app\assets"
mkdir "%DEPLOY_FOLDER%\app\resources"
mkdir "%DEPLOY_FOLDER%\config"

echo [1/6] Copying app files...
REM Copy main app directory files
xcopy /Y /Q "app\*.py" "%DEPLOY_FOLDER%\app\"
xcopy /Y /Q "app\*.json" "%DEPLOY_FOLDER%\app\"
xcopy /Y /Q "app\*.png" "%DEPLOY_FOLDER%\app\"
xcopy /Y /Q "app\*.txt" "%DEPLOY_FOLDER%\app\"

echo [2/6] Copying app modes...
REM Copy modes directory
xcopy /Y /Q "app\modes\*.py" "%DEPLOY_FOLDER%\app\modes\"

echo [3/6] Copying assets and resources...
REM Copy assets if they exist
if exist "app\assets\*" (
    xcopy /Y /Q /E "app\assets\*" "%DEPLOY_FOLDER%\app\assets\"
)

REM Copy resources if they exist
if exist "app\resources\*" (
    xcopy /Y /Q /E "app\resources\*" "%DEPLOY_FOLDER%\app\resources\"
)

echo [4/6] Copying root level files...
REM Copy requirements.txt
if exist "requirements.txt" copy /Y "requirements.txt" "%DEPLOY_FOLDER%\"
if exist "requirements_frozen.txt" copy /Y "requirements_frozen.txt" "%DEPLOY_FOLDER%\"

REM Copy other important files
if exist "role_permissions.json" copy /Y "role_permissions.json" "%DEPLOY_FOLDER%\"
if exist "example_users.json" copy /Y "example_users.json" "%DEPLOY_FOLDER%\"
if exist "VERSION" copy /Y "VERSION" "%DEPLOY_FOLDER%\"
if exist "README.md" copy /Y "README.md" "%DEPLOY_FOLDER%\"

REM Copy scheduler service if it exists
if exist "scheduler_service.py" copy /Y "scheduler_service.py" "%DEPLOY_FOLDER%\"

echo [5/6] Creating configuration files...

REM Create systemd service file
echo [Unit] > "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo Description=Price Scout v2 Streamlit Application >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo After=network.target >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo. >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo [Service] >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo User=root >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo WorkingDirectory=/root/pricescout-v2/app >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo ExecStart=/usr/local/bin/streamlit run price_scout_app.py --server.port=8502 --server.headless=true >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo Restart=always >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo RestartSec=10 >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo. >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo [Install] >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"
echo WantedBy=multi-user.target >> "%DEPLOY_FOLDER%\config\pricescout-v2.service"

REM Create Nginx configuration file
echo server { > "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo     # Subdomain for Price Scout v2 >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo     server_name v2.marketpricescout.com; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo. >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo     location / { >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo         # Proxy to the Streamlit app on port 8502 >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo         proxy_pass http://localhost:8502; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo         proxy_http_version 1.1; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo         proxy_set_header Host $host; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo         proxy_set_header Upgrade $http_upgrade; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo         proxy_set_header Connection "upgrade"; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo         proxy_read_timeout 86400; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo     } >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo. >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo     # Certbot will add SSL configuration here >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo     listen 80; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo     listen [::]:80; >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"
echo } >> "%DEPLOY_FOLDER%\config\pricescout-v2.conf"

echo [6/6] Creating deployment instructions...

REM Create deployment instructions
echo ========================================== > "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo   PRICE SCOUT V2 DEPLOYMENT INSTRUCTIONS >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo Droplet IP: 134.199.207.21 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo App Name: pricescout-v2 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo Port: 8502 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo Subdomain: v2.marketpricescout.com >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo STEP 1: UPLOAD FILES TO DROPLET >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 1. Create the directory on your droplet: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    ssh root@134.199.207.21 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    mkdir -p /root/pricescout-v2/app >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    exit >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 2. Upload the files using SCP: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    scp -r %DEPLOY_FOLDER%\app\* root@134.199.207.21:/root/pricescout-v2/app/ >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    scp %DEPLOY_FOLDER%\requirements*.txt root@134.199.207.21:/root/pricescout-v2/ >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    scp %DEPLOY_FOLDER%\*.json root@134.199.207.21:/root/pricescout-v2/ 2^>nul >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo STEP 2: INSTALL DEPENDENCIES ON DROPLET >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo SSH into your droplet and run: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    ssh root@134.199.207.21 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    cd /root/pricescout-v2 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    pip3 install -r requirements.txt >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    playwright install chromium >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    playwright install-deps chromium >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo STEP 3: CONFIGURE SYSTEMD SERVICE >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 1. Upload and install the service file: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    scp %DEPLOY_FOLDER%\config\pricescout-v2.service root@134.199.207.21:/etc/systemd/system/ >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 2. On the droplet, enable and start the service: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo systemctl daemon-reload >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo systemctl enable pricescout-v2 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo systemctl start pricescout-v2 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo systemctl status pricescout-v2 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo STEP 4: CONFIGURE NGINX >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 1. Upload the Nginx configuration: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    scp %DEPLOY_FOLDER%\config\pricescout-v2.conf root@134.199.207.21:/etc/nginx/sites-available/v2.marketpricescout.com >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 2. On the droplet, enable the site: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo ln -s /etc/nginx/sites-available/v2.marketpricescout.com /etc/nginx/sites-enabled/ >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo nginx -t >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo systemctl restart nginx >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo STEP 5: ADD DNS RECORD >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo Go to your DNS provider and add: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    Type: A Record >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    Host: v2 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    Value: 134.199.207.21 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    TTL: 3600 (or default) >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo Wait 5-10 minutes for DNS propagation. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo STEP 6: ENABLE SSL WITH CERTBOT >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo After DNS propagates, on the droplet run: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo certbot --nginx -d v2.marketpricescout.com >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo Follow the prompts to complete SSL setup. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo VERIFICATION >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 1. Check service status: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo systemctl status pricescout-v2 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 2. Check if app is responding on port 8502: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    curl http://localhost:8502 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo 3. Visit https://v2.marketpricescout.com in your browser >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo TROUBLESHOOTING >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo View service logs: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo journalctl -u pricescout-v2 -f >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo Restart service: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo systemctl restart pricescout-v2 >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo Check Nginx error logs: >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo    sudo tail -f /var/log/nginx/error.log >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"
echo. >> "%DEPLOY_FOLDER%\DEPLOYMENT_INSTRUCTIONS.txt"

REM Create a quick reference file
echo ========================================== > "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   QUICK COMMAND REFERENCE >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo ========================================== >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo. >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo Upload all files at once: >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   scp -r %DEPLOY_FOLDER%\app\* root@134.199.207.21:/root/pricescout-v2/app/ >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   scp %DEPLOY_FOLDER%\*.txt root@134.199.207.21:/root/pricescout-v2/ >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   scp %DEPLOY_FOLDER%\config\pricescout-v2.service root@134.199.207.21:/etc/systemd/system/ >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   scp %DEPLOY_FOLDER%\config\pricescout-v2.conf root@134.199.207.21:/etc/nginx/sites-available/v2.marketpricescout.com >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo. >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo On droplet - Complete setup: >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   cd /root/pricescout-v2 ^&^& pip3 install -r requirements.txt ^&^& playwright install chromium ^&^& playwright install-deps chromium >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   sudo systemctl daemon-reload ^&^& sudo systemctl enable pricescout-v2 ^&^& sudo systemctl start pricescout-v2 >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   sudo ln -s /etc/nginx/sites-available/v2.marketpricescout.com /etc/nginx/sites-enabled/ >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   sudo nginx -t ^&^& sudo systemctl restart nginx >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo   sudo certbot --nginx -d v2.marketpricescout.com >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"
echo. >> "%DEPLOY_FOLDER%\QUICK_COMMANDS.txt"

echo.
echo ========================================
echo   DEPLOYMENT FOLDER CREATED SUCCESSFULLY!
echo ========================================
echo.
echo Folder location: %CD%\%DEPLOY_FOLDER%
echo.
echo Next steps:
echo   1. Review the files in the deployment folder
echo   2. Read DEPLOYMENT_INSTRUCTIONS.txt for detailed steps
echo   3. Use QUICK_COMMANDS.txt for copy-paste commands
echo.
echo Configuration details:
echo   - App name: pricescout-v2
echo   - Port: 8502
echo   - Subdomain: v2.marketpricescout.com
echo   - Service file: config\pricescout-v2.service
echo   - Nginx config: config\pricescout-v2.conf
echo.
pause
