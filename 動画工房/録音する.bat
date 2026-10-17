@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 "しくみ\rokuon.py"
goto end
:try_python
where python >nul 2>nul
if errorlevel 1 goto nopy
python "しくみ\rokuon.py"
goto end
:nopy
echo Python が入ってへん。先に「はじめに一回だけ.bat」をダブルクリックしてな。
:end
echo.
pause
