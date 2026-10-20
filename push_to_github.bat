@echo off
set "PATH=C:\Users\CHN\AppData\Local\Programs\Git\cmd;%PATH%"
cd /d "%~dp0"
echo ========================================================
echo Pushing WaCRM production release to GitHub
echo Remote: https://github.com/chntechconsulting-website/wacrm.git
echo Account: chnconsulting
echo ========================================================
echo.
git push -u origin main
echo.
pause
