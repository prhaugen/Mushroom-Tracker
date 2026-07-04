@echo off
start "Mushroom Tracker" /min "C:\Users\engin\AppData\Local\Python\pythoncore-3.14-64\python.exe" "C:\Mushroom Tracker\mushroom_app.py"
timeout /t 3 /nobreak >nul
start http://localhost:5000
