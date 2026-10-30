@echo off
setlocal EnableExtensions
chcp 65001 >nul
pushd "%~dp0" || goto invalid_folder

REM Install into a project-local environment, not the user's global Python.
if exist ".venv\Scripts\python.exe" goto check_library

where py >nul 2>nul
if not errorlevel 1 goto launcher_py
where python >nul 2>nul
if errorlevel 1 goto no_python
set "PY_LAUNCHER=python"
goto create_venv

:launcher_py
set "PY_LAUNCHER=py -3"

:create_venv
echo Dang tao moi truong Python rieng (.venv)...
%PY_LAUNCHER% -m venv ".venv"
if errorlevel 1 goto venv_failed

:check_library
".venv\Scripts\python.exe" -c "import cv2, numpy; from pyzbar.pyzbar import decode" >nul 2>nul
if not errorlevel 1 goto run_app

echo Dang cai thu vien can thiet (chi can Internet lan dau)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_failed
".venv\Scripts\python.exe" -c "import cv2, numpy; from pyzbar.pyzbar import decode" >nul 2>nul
if errorlevel 1 goto install_failed

:run_app
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto runtime_failed
popd
exit /b 0

:no_python
echo Chua tim thay Python 3.10+. Cai tu https://www.python.org/downloads/
echo Khi cai, bat tuy chon Add Python to PATH.
goto failed

:venv_failed
echo Tao .venv that bai. Kiem tra Python va quyen ghi thu muc.
goto failed

:install_failed
echo Khong cai duoc thu vien. Kiem tra Internet, Python va thu lai.
echo Thu cong: ".venv\Scripts\python.exe" -m pip install -r requirements.txt
goto failed

:runtime_failed
echo Ung dung da dung do loi. Xem dong thong bao phia tren.
goto failed

:invalid_folder
echo Khong truy cap duoc thu muc chua ung dung.
pause
exit /b 1

:failed
pause
popd
exit /b 1
