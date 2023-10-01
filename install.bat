@echo off

REM Create a virtual environment named "venv"
python -m venv venv

REM Activate the virtual environment
call venv\Scripts\activate

REM Update pip

python -m pip install --upgrade pip

REM Install the necessary libraries
pip install npyscreen
pip install ultralytics
pip install tqdm
pip install opencv-python
pip install yt_dlp
pip install requests
pip install windows-curses

REM Replace this line with the relevant torch version from this site https://pytorch.org/get-started/locally/
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu118/torch_nightly.html

echo All necessary libraries have been installed!