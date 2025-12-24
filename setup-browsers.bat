@echo off
echo ========================================
echo Light Scraper - Browser Setup
echo ========================================
echo.
echo This will install required browsers for web scraping.
echo This is a one-time setup (approx. 100 MB download).
echo.
pause

echo Installing Chromium browser...
playwright install chromium

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Browsers installed.
    echo You can now use Light Scraper.
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERROR: Installation failed.
    echo Please contact support.
    echo ========================================
)

echo.
pause
