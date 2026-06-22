@echo off
echo === Face Recognition Setup (Windows) ===
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.9-3.13 from https://www.python.org
    pause
    exit /b 1
)

echo Installing dependencies (InsightFace, ONNX Runtime, OpenCV)...
pip install -r requirements.txt

echo.
echo Setup complete!
echo.
echo Quick start:
echo   1) Put photos in  photos\PersonName\*.jpg   then run:  python enroll.py
echo      (or capture from webcam:  python add_face.py "Name" --save-photos)
echo   2) Live recognition:        python recognize.py
echo   3) Recognize a photo:       python recognize_image.py somephoto.jpg
echo   4) Manage the database:     python manage_db.py --list
echo.
pause
