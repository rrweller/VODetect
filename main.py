import os
import threading
import twitch_downloader
import youtube_downloader
import inference
import npyscreen
import time
from queue import Queue
import cv2
import subprocess

MAX_INFERENCE_THREADS = 4  # User can change this value as needed

# This semaphore will limit the number of active threads
semaphore = threading.Semaphore(MAX_INFERENCE_THREADS)
print_lock = threading.Lock()

# Create a queue to hold videos waiting for inference
waiting_for_inference = Queue()

# User-defined target size for folder processing
TARGET_SIZE = (1920, 1080)

def run_inference(video_file, position=0):
    directory = os.path.dirname(video_file)  # Extract the directory from the video_file path
    try:
        inference.main(video_file, position, input_directory=directory)
    finally:
        semaphore.release()
        
def inference_worker():
    position = 2
    while True:
        video_file = waiting_for_inference.get()
        if video_file is None:
            # Sentinel value to exit the thread
            break
        semaphore.acquire()
        threading.Thread(target=run_inference, args=(video_file, position)).start()
        position += 1

def process_folder(folder_path, common_size=(1920, 1080)):
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
    for video_file in video_files:
        video_name = os.path.basename(video_file)
        resized_video_path = os.path.join(tmp_folder, video_name)
        if not os.path.exists(resized_video_path):  # Avoid re-resizing
            print(f"Resizing video {video_name} to {common_size}...")
            resize_video(video_file, resized_video_path, common_size)
        print(f"Enqueued video: {resized_video_path}")
        waiting_for_inference.put(resized_video_path)

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

class App(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm("MAIN", MainMenuForm, name="Main Menu")
        self.addForm("TWITCH", TwitchForm, name="Twitch Menu")
        self.addForm("YOUTUBE", YouTubeForm, name="YouTube Menu")
        self.addForm("FOLDERPROCESS", FolderProcessForm, name="Folder Process Menu")

class MainMenuForm(npyscreen.ActionForm):
    def create(self):
        self.source = self.add(npyscreen.TitleSelectOne, max_height=5, name="Choose Process Source", values=["Twitch", "YouTube", "Folder Process"], scroll_exit=True)

    def on_ok(self):
        if self.source.value[0] == 0:  # Twitch
            self.parentApp.switchForm('TWITCH')
        elif self.source.value[0] == 1:  # YouTube
            self.parentApp.switchForm('YOUTUBE')
        elif self.source.value[0] == 2:  # Folder Process
            self.parentApp.switchForm('FOLDERPROCESS')
        else:
            self.parentApp.setNextForm(None)
    
    def on_cancel(self):
        self.parentApp.setNextForm(None)

class TwitchForm(npyscreen.ActionForm):
    def create(self):
        self.channel_name = self.add(npyscreen.TitleText, name="Enter Twitch Channel Name:")
        self.vods = self.add(npyscreen.MultiSelect, name="VODs", values=[], scroll_exit=True)
        self.loaded_vod_count = 0
        self.selected_vod_ids = []  # List to store all selected VOD IDs

    def on_ok(self):
        if not self.vods.values:
            self.load_vods()
        else:
            if len(self.vods.values) - 1 in self.vods.value:  # "Load 10 More" selected
                # Save the currently selected vods
                selected_vods = [self.vods.values[i] for i in self.vods.value if i != len(self.vods.values) - 1]
                all_vods = twitch_downloader.get_latest_vods(self.channel_name.value, num_vods=self.loaded_vod_count)
                self.selected_vod_ids.extend([vod_id for title, vod_id in all_vods if title in selected_vods])
                
                # Load the next set of vods
                self.load_vods()
            else:
                # Retrieve the VOD IDs for the selected titles
                selected_vods = [self.vods.values[i] for i in self.vods.value]
                all_vods = twitch_downloader.get_latest_vods(self.channel_name.value, num_vods=self.loaded_vod_count)
                self.selected_vod_ids.extend([vod_id for title, vod_id in all_vods if title in selected_vods])
                
                # Start the download and inference processes
                self.start_download_and_inference()

    def load_vods(self):
        # Load the next set of vods
        channel_vods = twitch_downloader.get_latest_vods(self.channel_name.value, num_vods=10)
        vod_titles = [vod[0] for vod in channel_vods] + ["Load 10 More"]
        
        # Clear previous selections
        self.vods.value = []
        
        self.vods.values = vod_titles
        self.loaded_vod_count += 10
        self.vods.display()

    def start_download_and_inference(self):
        # Start the inference worker thread
        threading.Thread(target=inference_worker).start()

        def download_and_infer():
            for vod_id in self.selected_vod_ids:
                with print_lock:
                    vod_file = twitch_downloader.download_single_vod(self.channel_name.value, vod_id)
                # Add the downloaded vod to the queue for inference
                waiting_for_inference.put(vod_file)
            # Put sentinel values for each inference worker thread to signal them to exit
            for _ in range(MAX_INFERENCE_THREADS):
                waiting_for_inference.put(None)

        threading.Thread(target=download_and_infer).start()
        self.parentApp.switchForm(None)

    def on_cancel(self):
        self.parentApp.switchForm('MAIN')


class YouTubeForm(npyscreen.ActionForm):
    def create(self):
        self.channel_name = self.add(npyscreen.TitleText, name="Enter YouTube Channel Name:")
        self.videos = self.add(npyscreen.MultiSelect, name="Videos", values=[], scroll_exit=True)
        self.loaded_video_count = 0
        self.selected_video_urls = []  # List to store all selected video URLs

    def on_ok(self):
        if not self.videos.values:
            self.load_videos()
        else:
            if len(self.videos.values) - 1 in self.videos.value:  # "Load 10 More" selected
                # Save the currently selected videos
                selected_videos = [self.videos.values[i] for i in self.videos.value if i != len(self.videos.values) - 1]
                all_videos = youtube_downloader.get_latest_videos(self.channel_name.value, start=self.loaded_video_count - 20, count=20)
                self.selected_video_urls.extend([url for title, url in all_videos if title in selected_videos])
                
                # Load the next set of videos
                self.load_videos()
            else:
                # Retrieve the video URLs for the selected video titles
                selected_videos = [self.videos.values[i] for i in self.videos.value]
                all_videos = youtube_downloader.get_latest_videos(self.channel_name.value, start=self.loaded_video_count - 20, count=20)
                self.selected_video_urls.extend([url for title, url in all_videos if title in selected_videos])
                
                # Start the download and inference processes
                self.start_download_and_inference()

    def load_videos(self):
        # Load the next set of videos
        channel_videos = youtube_downloader.get_latest_videos(self.channel_name.value, start=self.loaded_video_count, count=20)
        video_titles = [video[0] for video in channel_videos] + ["Load 20 More"]
        
        # Clear previous selections
        self.videos.value = []
        
        self.videos.values = video_titles
        self.loaded_video_count += 20
        self.videos.display()

    def start_download_and_inference(self):
        # Start the inference worker thread
        threading.Thread(target=inference_worker).start()

        def download_and_infer():
            for url in self.selected_video_urls:
                with print_lock:
                    video_file = youtube_downloader.download_video(url)
                # Add the downloaded video to the queue for inference
                waiting_for_inference.put(video_file)
            # Put sentinel values for each inference worker thread to signal them to exit
            for _ in range(MAX_INFERENCE_THREADS):
                waiting_for_inference.put(None)

        threading.Thread(target=download_and_infer).start()
        self.parentApp.switchForm(None)

    def on_cancel(self):
        self.parentApp.switchForm('MAIN')
        
class FolderProcessForm(npyscreen.ActionForm):
    def create(self):
        self.folder_name = self.add(npyscreen.TitleText, name="Enter Folder Name:")

    def on_ok(self):
        if os.path.exists(self.folder_name.value):
            process_folder(self.folder_name.value)
            self.parentApp.switchForm(None)
        else:
            npyscreen.notify_confirm("Invalid folder path. Please enter a valid folder.", title="Error", wrap=True)

    def on_cancel(self):
        self.parentApp.switchForm('MAIN')

def main():
    app = App()
    app.run()

if __name__ == "__main__":
    main()