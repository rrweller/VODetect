@echo off
cd venv\Scripts
call activate
cd ..\..
start /wait python ui.py
