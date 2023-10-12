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
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu118/torch_nightly.html
pip install tqdm
pip install opencv-python
pip install yt_dlp
pip install requests
pip install streamlink
pip install windows-curses

echo All necessary libraries have been installed!