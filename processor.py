import os
import threading
import twitch_downloader
import twitch_autodownloader
import youtube_downloader
import inference
import time
import queue
import cv2
import subprocess
import json

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

MAX_INFERENCE_THREADS = config["processor"]["MAX_INFERENCE_THREADS"]
TARGET_SIZE = tuple(config["folder_processing"]["VIDEO_RESOLUTION"])
FOLDER_RESIZE = config["folder_processing"]["RESIZE_VIDEOS"]
TWITCH_OUTPUT_DIR = "vods"
channel_flags = {}
#channel_status = {}
STOP_MONITORING = False
STOP_INFERENCE = False

# This semaphore will limit the number of active threads
semaphore = threading.Semaphore(MAX_INFERENCE_THREADS)
print_lock = threading.Lock()
waiting_for_inference = queue.Queue()

channel_names = config["twitch_autodownloader"]["channels"]
channel_status = {channel: 'offline' for channel in channel_names}

def run_inference(video_file, position=0):
    directory = os.path.dirname(video_file)  # Extract the directory from the video_file path
    try:
        inference.main(video_file, position, input_directory=directory)
    finally:
        print(f"Releasing semaphore for {video_file}.")
        #get channel name from video_file
        base_name = os.path.basename(video_file)
        channel_name = base_name.split('_')[0]
        set_channel_status(channel_name, "offline")
        print(f"Set {channel_name} status to offline because inference was complete.")
        semaphore.release()

def inference_worker():
    global channel_status
    #print("Inference worker started.")
    position = 1
    while True:
        video_file = waiting_for_inference.get()
        
        if STOP_INFERENCE or video_file is None:  # Check the flag here
            #print("Inference worker exiting.")
            #get channel name from video_file
            #channel_name = video_file.split('_')[0]
            #set_channel_status(channel_name, "offline")
            #print(f"Set {channel_name} status to offline because inference was complete.")
            break
            
        print(f"Starting inference on {video_file}.")
        print("Trying to acquire semaphore.")
        semaphore.acquire()
        threading.Thread(target=run_inference, args=(video_file, position)).start()
        position += 1

def get_twitch_channels_status():
    global STOP_MONITORING, channel_status
    
    if STOP_MONITORING:
        print("Stopping channel monitoring.")
        for channel in channel_names:
            set_channel_status(channel, "offline")
        return channel_status
    
    for channel in channel_names:
        status = twitch_autodownloader.check_channel_status(channel, channel_status[channel])
        channel_status[channel] = status

    return channel_status

def set_channel_status(channel, status):
    global channel_status
    channel_status[channel] = status

def monitor_channels(form):
    global channel_flags
    while not form.stop_thread:
        print("Checking channel statuses...")
        channel_status = get_twitch_channels_status()
        for channel, status in channel_status.items():

            # If channel is live and not currently being downloaded
            if status == "online" and not channel_flags.get(channel, False):
                print(f"Starting download for {channel}")
                channel_flags[channel] = True
                thread = threading.Thread(target=start_live_download, args=(channel,))
                thread.start()
                form.threads.append(thread)

            # If channel was live but is now offline
            elif status == "offline" and channel_flags.get(channel, False):
                print(f"Stopping download for {channel}")
                channel_flags[channel] = False
                twitch_autodownloader.stop_download(channel)  # Stop only the download for this specific channel

                # Explicitly start inference here
                output_path = twitch_autodownloader.generate_output_path(channel)  # Assuming this function generates the same path as before
                if not STOP_INFERENCE and output_path:  # Check the flag and if output_path is not None
                    waiting_for_inference.put(output_path)
                    set_channel_status(channel, "inference")
                    print(f"Explicitly set {channel} status to {channel_status[channel]}.")
                    print(f"Explicitly added {output_path} to the inference queue.")

        time.sleep(config["twitch_autodownloader"]["CHECK_INTERVAL"])
        
        if form.stop_thread:
            print("Stopping channel monitoring thread.")
            break

def start_live_download(channel):
    try:
        output_path = twitch_autodownloader.download_stream(channel)
        if output_path:
            if not STOP_INFERENCE:  # Check the flag here
                # Add the downloaded video to the queue for inference
                waiting_for_inference.put(output_path)
                set_channel_status(channel, "inference")
                print(f"Set {channel} status to {channel_status[channel]}.")
                print(f"Added {output_path} to the inference queue.")
    finally:
        # Update the flag when the download is finished
        channel_flags[channel] = False

def stop_all_downloads():
    for channel in channel_flags.keys():
        twitch_autodownloader.stop_download(channel)

def stop_all_processing():
    global STOP_MONITORING
    STOP_MONITORING = True
    for _ in range(MAX_INFERENCE_THREADS):
        waiting_for_inference.put(None)

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