@echo off
set "OBSDIR=%ProgramFiles%\obs-studio\bin\64bit"
if not exist "%OBSDIR%\obs64.exe" (
  echo OBS が見つからへん。先に「はじめに一回だけ.bat」をダブルクリックしてな。
  pause
  exit /b
)
if not exist "%APPDATA%\obs-studio\basic\scenes\配信工房.json" (
  echo まだ準備ができてへん。先に「はじめに一回だけ.bat」をダブルクリックしてな。
  pause
  exit /b
)
pushd "%OBSDIR%"
start "" obs64.exe --profile "配信工房" --collection "配信工房" --scene "待機中"
popd
