#!/bin/bash

# Create a virtual environment named "venv"
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

python -m pip install --upgrade pip

# Install the necessary libraries
pip3 install npyscreen
pip3 install ultralytics
pip3 install tqdm
pip3 install opencv-python
pip3 install yt_dlp
pip3 install requests

# Replace this line with the relevant torch version from this site https://pytorch.org/get-started/locally/
pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu118/torch_nightly.html

echo "All necessary libraries have been installed!"
