@echo off
REM ============================================================================
REM SETUP SCRIPT - Cai dat Gemini AI cho FasTrack ERP
REM ============================================================================

echo.
echo ========================================
echo Cai dat Gemini AI cho FasTrack ERP
echo ========================================
echo.

REM Kiem tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
	echo Loi: Python chua duoc cai dat!
	echo Tai Python tu: https://www.python.org
	pause
	exit /b 1
)

echo [✓] Python da cai dat
echo.

REM Cai dat dependencies
echo [*] Dang cai dat cac thu vien can thiet...
pip install -r requirements.txt
if %errorlevel% neq 0 (
	echo Loi: Khong the cai dat dependencies!
	pause
	exit /b 1
)

echo.
echo [✓] Cai dat thanh cong!
echo.
echo ========================================
echo Cau hinh Gemini API
echo ========================================
echo.
echo De su dung tinh nang Trợ ly AI:
echo.
echo 1. Truy cap: https://aistudio.google.com/app/apikey
echo 2. Dang nhap bang tai khoan Google
echo 3. Nhan 'Create API Key' va sao chep API key
echo 4. Mo ung dung FasTrack ERP
echo 5. Nhap menu 'Tro ly AI' va dien API key
echo.
echo ========================================
echo.
pause
