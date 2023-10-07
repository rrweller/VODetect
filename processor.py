import os
import threading
import twitch_downloader
import youtube_downloader
import inference
import time
import queue  # Import the queue module
import cv2
import subprocess
import json

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

MAX_INFERENCE_THREADS = config["processor"]["MAX_INFERENCE_THREADS"]
TARGET_SIZE = tuple(config["folder_processing"]["VIDEO_RESOLUTION"])
FOLDER_RESIZE = config["folder_processing"]["RESIZE_VIDEOS"]

# This semaphore will limit the number of active threads
semaphore = threading.Semaphore(MAX_INFERENCE_THREADS)
print_lock = threading.Lock()
waiting_for_inference = queue.Queue()


def run_inference(video_file, position=0):
    directory = os.path.dirname(video_file)  # Extract the directory from the video_file path
    try:
        inference.main(video_file, position, input_directory=directory)
    finally:
        semaphore.release()

def inference_worker():
    position = 1
    while True:
        video_file = waiting_for_inference.get()
        if video_file is None:
            # Sentinel value to exit the thread
            break
        semaphore.acquire()
        threading.Thread(target=run_inference, args=(video_file, position)).start()
        position += 1

def process_folder(folder_path, common_size=TARGET_SIZE):
    # Check if the folder exists
    if not os.path.exists(folder_path):
        print("Folder does not exist.")
        return

    # Create the tmp folder if it doesn't exist
    tmp_folder = os.path.join(folder_path, 'tmp')
    if not os.path.exists(tmp_folder):
        os.makedirs(tmp_folder)

    # Enqueue all video files in the folder
    video_files = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv'))]

    # Resize videos and save them to the tmp folder
    if FOLDER_RESIZE:
        for video_file in video_files:
            video_name = os.path.basename(video_file)
            resized_video_path = os.path.join(tmp_folder, video_name)
            if not os.path.exists(resized_video_path):  # Avoid re-resizing
                print(f"Resizing video {video_name} to {common_size}...")
                resize_video(video_file, resized_video_path, common_size)
            print(f"Enqueued video: {resized_video_path}")
            waiting_for_inference.put(resized_video_path)
    else:
        for video_file in video_files:
            print(f"Enqueued video: {video_file}")
            waiting_for_inference.put(video_file)

    # Start the inference worker thread
    threading.Thread(target=inference_worker).start()

    # Put sentinel values for each inference worker thread to signal them to exit after all videos are processed
    for _ in range(MAX_INFERENCE_THREADS):
        waiting_for_inference.put(None)

def resize_video(video_path, output_path, target_size):
    width, height = target_size
    cmd = [
        'ffmpeg', 
        '-i', video_path, 
        '-vf', f'scale={width}:{height}', 
        '-c:a', 'copy',  # Do not transcode audio
        output_path
    ]
    subprocess.run(cmd, check=True)

def check_and_resize_videos(directory, target_size):
    for filename in os.listdir(directory):
        if filename.endswith(".mp4"):
            video_path = os.path.join(directory, filename)
            cap = cv2.VideoCapture(video_path)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if (width, height) != target_size:
                print(f"Resizing video {filename} to {target_size}...")
                resize_video(video_path, video_path, target_size)  # overwrite original video with resized one
