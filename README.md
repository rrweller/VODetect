# VODetect

VODetect is a powerful tool designed to download videos from YouTube and Twitch VODs, and then process them using a pretrained YOLOv8 model to detect objects. This project is an experimental excerise in using ChatGPT to code a complex program, and as such it has been nearly 100% written by ChatGPT. Due to this, do not expect the code to be pretty or entirely bug-free. If you encounter a bug feel free to open an issue, but I cannot guarantee it will be resolved. For those who wish to tackle the challenge of repairing/improving the code themselves, feel free to fork this.

## Features

- **Video Downloading**: Easily download videos from YouTube or Twitch VODs.
- **Object Detection**: Uses a pretrained YOLOv8 model to detect and identify objects within the videos.
- **Batch Processing**: Process multiple videos in a directory with ease.
- **Custom Configuration**: Adjust settings and parameters via a configuration file.
- **Cross-Platform**: Works on both Windows and Linux.

## Installation

### Prerequisites

- Python 3.10 or higher
- Virtual Environment (recommended)

### Installation

1. Clone the repository:
``https://github.com/rrweller/VODetect``

2. Visit https://pytorch.org/get-started/locally/ and copy the correct installation command *THIS IS VERY IMPORTANT AS TORCH IS A PAIN*

3. Edit the install.bat or install.sh file and replace ``pip install torch`` with the install command you copied

5. Run the ``install.bat`` or ``install.sh`` file

6. Create a folder named "model" and place your YOLO .pt model file into that directory

7. If you intend on using the Twitch functionality, edit ``request_oauth.py`` and add your CLIENT ID and CLIENT SECRET. Run this script and copy the OAUTH key it provides you

8. Rename ``exampleconfig.json`` to ``config.json`` and open it

9. Paste your OAUTH key into the config file, specify the name of your YOLO model file, and modify any other values you desire. Refer to the description of these settings below

10. Run ``run.bat`` or ``run.sh``
