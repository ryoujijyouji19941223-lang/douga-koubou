@echo off
cd /d "%~dp0"
echo 配信の道具を入れます。数分かかります。
echo.
set AGAIN=0
if exist "%ProgramFiles%\obs-studio\bin\64bit\obs64.exe" goto check_py
echo [1/3] OBS（配信・録画のソフト）を入れています
winget install -e --id OBSProject.OBSStudio --accept-package-agreements --accept-source-agreements
set AGAIN=1
:check_py
where py >nul 2>nul
if not errorlevel 1 goto check_first
echo [2/3] Python を入れています
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
set AGAIN=1
:check_first
if "%AGAIN%"=="1" goto again
if exist "%APPDATA%\obs-studio\basic" goto setup
echo.
echo OBS を一回開くで。最初に出てくる質問（自動構成ウィザード）は
echo 「録画のために最適化」を選んで、あとは「次へ」でええ。終わったら OBS を閉じて、
echo もう一回この「はじめに一回だけ.bat」をダブルクリックしてな。
pushd "%ProgramFiles%\obs-studio\bin\64bit"
start "" obs64.exe
popd
goto end
:setup
echo [3/3] OBS に配信工房の画面を入れています
py -3 "しくみ\setup.py"
goto end
:again
echo.
echo 途中まで入れた。このウィンドウを閉じて、もう一回「はじめに一回だけ.bat」をダブルクリックしてな。
:end
echo.
pause
