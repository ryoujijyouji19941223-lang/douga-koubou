@echo off
cd /d "%~dp0"
echo 動画づくりの道具を入れます。数分かかります。
echo.
set AGAIN=0
where py >nul 2>nul
if errorlevel 1 goto install_py
goto check_ff
:install_py
echo [1/3] Python を入れています
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
set AGAIN=1
:check_ff
where ffmpeg >nul 2>nul
if errorlevel 1 goto install_ff
goto pillow
:install_ff
echo [2/3] ffmpeg を入れています
winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
set AGAIN=1
:pillow
if "%AGAIN%"=="1" goto again
echo [3/3] 絵を描く道具を入れています
py -3 -m pip install --upgrade pillow
echo.
echo 準備できた。あとは VOICEVOX を入れて、開いておけば OK。
goto end
:again
echo.
echo 途中まで入れた。このウィンドウを閉じて、もう一回「はじめに一回だけ.bat」をダブルクリックしてな。
:end
echo.
pause
