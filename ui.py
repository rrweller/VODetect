import npyscreen
import processor
import twitch_downloader
import twitch_autodownloader
import youtube_downloader
import youtube_downloader_shorts
import threading
import os
import sys
import subprocess
from processor import channel_flags
import time

print_lock = threading.Lock()

class App(npyscreen.NPSAppManaged):
    def __init__(self, *args, **kwargs):
            super(App, self).__init__(*args, **kwargs)
            self.threads = []
    def onStart(self):
        npyscreen.setTheme(CustomColorTheme)
        self.addForm("MAIN", MainMenuForm, name="Main Menu")
        self.addForm("TWITCH", TwitchForm, name="Twitch Menu")
        self.addForm("YOUTUBE", YouTubeForm, name="YouTube Menu")
        self.addForm("FOLDERPROCESS", FolderProcessForm, name="Folder Process Menu")
        self.addForm("YOUTUBESHORTS", YouTubeShortsForm, name="YouTube Shorts Menu")  # New form for YouTube Shorts
        self.addForm("CHANNELNAME", ChannelNameForm, name="Channel Selection")
        self.addForm("NEWCHANNEL", NewChannelForm, name="New Channel Selection")
        self.addForm('NUMBERINPUT', NumberInputForm, name="Bulk Video Downloader (Clears any manually selected videos)")
        self.addForm("TWITCHAUTODOWNLOADER", TwitchAutoDownloaderForm, name="Twitch Auto-Downloader")

class MainMenuForm(npyscreen.ActionForm):
    def create(self):
        self.source = self.add(npyscreen.TitleSelectOne, max_height=6, name="Choose Process Source", values=["Twitch", "Twitch Auto Downloader", "YouTube", "YouTube Shorts", "Folder Process"], scroll_exit=True)

    def on_ok(self):
        if self.source.value[0] == 0:  # Twitch
            self.parentApp.getForm("CHANNELNAME").source = "Twitch"
            self.parentApp.switchForm('CHANNELNAME')
        elif self.source.value[0] == 1:  # Twitch Auto-downloader
            self.parentApp.switchForm('TWITCHAUTODOWNLOADER')
        elif self.source.value[0] == 2:  # YouTube
            self.parentApp.getForm("CHANNELNAME").source = "YouTube"
            self.parentApp.switchForm('CHANNELNAME')
        elif self.source.value[0] == 3:  # YouTube Shorts
            self.parentApp.getForm("CHANNELNAME").source = "YouTubeShorts"
            self.parentApp.switchForm('CHANNELNAME')
        elif self.source.value[0] == 4:  # Folder Process
            self.parentApp.switchForm('FOLDERPROCESS')
        else:
            self.parentApp.setNextForm(None)
    def on_cancel(self):
        self.parentApp.switchForm(None)

class ChannelNameForm(npyscreen.ActionForm):
    def create(self):
        self.channel_name = self.add(npyscreen.TitleText, name="Enter Channel Name:")
        self.source = None

    def on_ok(self):
        if self.source == "Twitch":
            twitch_form = self.parentApp.getForm("TWITCH")
            twitch_form.channel_name_value = self.channel_name.value
            self.parentApp.switchForm('TWITCH')
        elif self.source == "YouTube":
            youtube_form = self.parentApp.getForm("YOUTUBE")
            youtube_form.channel_name_value = self.channel_name.value
            self.parentApp.switchForm('YOUTUBE')
        elif self.source == "YouTubeShorts":
            shorts_form = self.parentApp.getForm("YOUTUBESHORTS")
            shorts_form.channel_name_value = self.channel_name.value
            self.parentApp.switchForm('YOUTUBESHORTS')
        else:
            self.parentApp.setNextForm(None)

    def on_cancel(self):
        self.parentApp.switchForm('MAIN')

class NewChannelForm(npyscreen.ActionPopup):
    def create(self):
        self.channel_name = self.add(npyscreen.TitleText, name="Enter another channel or press enter to start download:")

    def beforeEditing(self):
        self.channel_name.value = ""

class N_Button(npyscreen.ButtonPress):
    def __init__(self, *args, **keywords):
        self.target_form_id = keywords.pop('target_form_id', None)
        super(N_Button, self).__init__(*args, **keywords)

    def whenPressed(self):
        if self.target_form_id:
            app = self.parent.parentApp
            target_form = app.getForm(self.target_form_id)
            number_input_form = app.getForm('NUMBERINPUT')
            number_input_form.set_parent_form(target_form)
            number_input_form.edit()
        else:
            npyscreen.notify_confirm("Target form ID not set.", title="Error", wrap=True)

class NumberInputForm(npyscreen.ActionPopup):
    def create(self):
        self.number = self.add(npyscreen.TitleText, name="Enter number of videos to bulk download:", value="")
        self.parent_form_name = None

    def set_parent_form(self, form):
        self.parent_form_id = form.FORM_NAME

    def on_ok(self):
        if self.parent_form_id:
            parent_form = self.parentApp.getForm(self.parent_form_id)
            parent_form.download_n_videos(int(self.number.value))
        else:
            npyscreen.notify_confirm("Parent form not set.", title="Error", wrap=True)
        self.parentApp.switchForm(None)

#============== Twitch ==============
class TwitchForm(npyscreen.ActionForm):
    def create(self):
        self.channel_name_value = None
        self.vods = self.add(npyscreen.MultiSelect, name="VODs", values=[], scroll_exit=True)
        self.after_cursor = None
        self.loaded_vod_count = 0
        self.selected_vod_ids = []  # List to store all selected VOD IDs
        self.loaded_vods = []  # Initialize loaded_vods
        self.page_number = 1  # Initialize page number to 1
        self.page_display = self.add(npyscreen.Textfield, value=f"Page: {self.page_number}", editable=False, rely=-4)

    def beforeEditing(self):
        if self.channel_name_value:
            try:
                self.loaded_vods, self.after_cursor = self.load_vods()  # Handle the return value
            except Exception as e:
                npyscreen.notify_confirm(str(e), title='Error', wrap=True)

    def on_ok(self):
        if not self.vods.values:
            self.load_vods()
            return
        elif "Load 10 More" in [self.vods.values[i] for i in self.vods.value]:
            self.page_number += 1
            self.get_selected_vods()
            return
        else:
            # Retrieve the VOD IDs for the selected titles
            self.get_selected_vods()
            
            new_channel_form = self.parentApp.getForm("NEWCHANNEL")
            new_channel_form.channel_name.value = ""
            new_channel_form.edit()
            new_channel = new_channel_form.channel_name.value
            if new_channel:
                self.channel_name_value = new_channel
                self.loaded_vod_count = 0  # Reset the VOD counter
            else:
                self.start_download_and_inference()

    def load_vods(self):
        # Load the next set of vods
        channel_vods, self.after_cursor = twitch_downloader.get_latest_vods(self.channel_name_value, num_vods=10, after_cursor=self.after_cursor)
        vod_titles = [vod[0] for vod in channel_vods] + ["Load 10 More"]
        
        # Clear previous selections
        self.vods.value = []
        
        self.vods.values = vod_titles
        self.loaded_vod_count += 10
        self.vods.cursor_line = 0
        self.page_display.value = f"Page: {self.page_number}"
        self.page_display.display()
        self.vods.display()
        return channel_vods, self.after_cursor  # Return both values

    def get_selected_vods(self):
        selected_vods = [self.vods.values[i] for i in self.vods.value if i != len(self.vods.values) - 1]
        self.selected_vod_ids.extend([vod_id for title, vod_id in self.loaded_vods if title in selected_vods])

    def start_download_and_inference(self):
        # Start the inference worker thread
        threading.Thread(target=processor.inference_worker).start()

        def download_and_infer():
            print(f"VOD IDs to download: {self.selected_vod_ids}")  # Debug line
            for vod_id in self.selected_vod_ids:
                with print_lock:
                    vod_file = twitch_downloader.download_single_vod(self.channel_name_value, vod_id)
                # Add the downloaded vod to the queue for inference
                processor.waiting_for_inference.put(vod_file)
            # Put sentinel values for each inference worker thread to signal them to exit
            for _ in range(processor.MAX_INFERENCE_THREADS):
                processor.waiting_for_inference.put(None)

        threading.Thread(target=download_and_infer).start()
        self.parentApp.switchForm(None)

    def on_cancel(self):
        self.parentApp.switchForm('MAIN')

#============== Twitch Auto-downloader ==============
class TwitchAutoDownloaderForm(npyscreen.FormBaseNew):
    def create(self):
        self.threads = []  # List to keep track of all threads
        self.stop_thread = False  # Control attribute for the thread
        y, x = self.useable_space()
        self.channel_lines = []
        self.load_channels()
        self.stop_downloads_button = self.add(npyscreen.ButtonPress, name="Stop Downloads", rely=y-4)
        self.stop_downloads_button.whenPressed = self.on_stop_downloads
        self.exit_button = self.add(npyscreen.ButtonPress, name="Exit", rely=y-3)
        self.exit_button.whenPressed = self.on_exit

    def while_editing(self, *args, **keywords):
        # Start the channel monitoring thread only when the user is on this form
        threading.Thread(target=processor.inference_worker).start()
        if not hasattr(self, "monitoring_thread"):
            print("Starting channel monitoring thread.")
            self.monitoring_thread = threading.Thread(target=processor.monitor_channels, args=(self,))
            self.parentApp.threads.append(self.monitoring_thread)
            self.monitoring_thread.start()
        # Start a thread to periodically refresh the UI
        if not hasattr(self, "refresh_thread"):
            self.refresh_thread = threading.Thread(target=self.periodic_refresh)
            self.refresh_thread.start()

    def periodic_refresh(self):
        while not self.stop_thread:
            self.load_channels()
            time.sleep(1)  # Refresh every second, adjust as needed

    def load_channels(self):
        rely = 2  # Starting position 
        channel_status = processor.channel_status

        # Clear and update channel lines in the same loop
        for channel, status in channel_status.items():
            # Clear the line
            clear_str = " " * 50  # Assuming a width of 50 characters, adjust as needed
            self.add(npyscreen.Textfield, value=clear_str, rely=rely, editable=False)
            
            # Update the line
            display_str = f"{channel}: {status}"
            color = 'DEFAULT'  # Initialize to a default value

            if status == "offline":
                color = 'DANGER'
            elif status == "online":
                color = 'GOOD'
            elif status == "inference":
                color = 'WARNING'
                
            channel_line = self.add(npyscreen.Textfield, value=display_str, rely=rely, color=color, editable=False)
            self.channel_lines.append(channel_line)
            rely += 1  # Increment position for next line

        self.display()
 
    def on_stop_downloads(self):
        self.stop_thread = True
        processor.STOP_MONITORING = True
        self.parentApp.switchForm(None)
        for channel in processor.channel_flags.keys():
            try:
                twitch_autodownloader.stop_download(channel)
            except Exception as e:
                print(f"An error occurred while stopping the download for {channel}: {e}")
        print("Joining threads")
        for thread in self.threads:
            thread.join()  # Wait for the thread to complete
    
    def on_exit(self):
        self.stop_thread = True  # Signal the thread to stop
        processor.STOP_MONITORING = True
        processor.STOP_INFERENCE = True
        for channel in processor.channel_flags.keys():
            twitch_autodownloader.stop_download(channel)
        self.monitoring_thread.join()  # Wait for the monitoring thread to finish
        for _ in range(processor.MAX_INFERENCE_THREADS):
            processor.waiting_for_inference.put(None)
        for thread in self.threads:
            thread.join()  # Wait for each thread to finish
        self.parentApp.switchForm(None)

#============== Youtube ==============
class YouTubeForm(npyscreen.ActionForm):
    def create(self):
        self.channel_name_value = None
        self.videos = self.add(npyscreen.MultiSelect, name="Videos", values=[], scroll_exit=True, max_height=-4)
        self.loaded_video_count = 0
        self.selected_video_urls = []  # List to store all selected video URLs
        self.page_number = 1  # Initialize page number to 1
        self.page_display = self.add(npyscreen.Textfield, value=f"Page: {self.page_number}", editable=False, rely=-4)
        self.button = self.add(N_Button, name="Download Bulk", target_form_id="YOUTUBE")

    def beforeEditing(self):
        if self.channel_name_value:
            try:
                self.load_videos()  # Assuming load_videos now returns something you handle
            except Exception as e:
                npyscreen.notify_confirm(str(e), title='Error', wrap=True)

    def load_videos(self):
        # Load the next set of videos
        channel_videos = youtube_downloader.get_latest_videos(self.channel_name_value, start=self.loaded_video_count, count=20) # Updated line
        video_titles = [video[0] for video in channel_videos] + ["Load 20 More"]
        
        # Clear previous selections
        self.videos.value = []
        
        self.videos.values = video_titles
        self.loaded_video_count += 20
        self.videos.cursor_line = 0
        self.page_display.value = f"Page: {self.page_number}"
        self.page_display.display()
        self.videos.display()

    def get_selected_videos(self):
        selected_videos = [self.videos.values[i] for i in self.videos.value if i != len(self.videos.values) - 1]
        all_videos = youtube_downloader.get_latest_videos(self.channel_name_value, start=self.loaded_video_count - 20, count=20)
        self.selected_video_urls.extend([url for title, url in all_videos if title in selected_videos])
    
    def download_n_videos(self, n):
        self.selected_video_urls = []  # Clear previously selected videos
        all_videos = youtube_downloader.get_latest_videos(self.channel_name_value, start=0, count=n)
        self.selected_video_urls.extend([url for _, url in all_videos])
        self.start_download_and_inference()

    def start_download_and_inference(self):
        # Start the inference worker thread
        threading.Thread(target=processor.inference_worker).start()

        def download_and_infer():
            for url in self.selected_video_urls:
                with print_lock:
                    video_file = youtube_downloader.download_video(url)
                # Add the downloaded video to the queue for inference
                processor.waiting_for_inference.put(video_file)
            # Put sentinel values for each inference worker thread to signal them to exit
            for _ in range(processor.MAX_INFERENCE_THREADS):
                processor.waiting_for_inference.put(None)

        threading.Thread(target=download_and_infer).start()
        self.parentApp.switchForm(None)

    def on_ok(self):
        if not self.videos.values:
            self.load_videos()
            return
        elif "Load 20 More" in [self.videos.values[i] for i in self.videos.value]:
            self.page_number += 1
            self.get_selected_videos()
            return
        else:
            # Retrieve the video URLs for the selected video titles
            self.get_selected_videos()
            
            new_channel_form = self.parentApp.getForm("NEWCHANNEL")
            new_channel_form.channel_name.value = ""
            new_channel_form.edit()
            new_channel = new_channel_form.channel_name.value
            if new_channel:
                self.channel_name_value = new_channel
                self.loaded_video_count = 0  # Reset the video counter
                self.page_number = 1  # Reset the page number
            else:
                self.start_download_and_inference()

    def on_cancel(self):
        self.parentApp.switchForm('MAIN')

#============== Youtube Shorts ==============
class YouTubeShortsForm(npyscreen.ActionForm):
    # This form is tailored for shorts.
    def create(self):
        self.channel_name_value = None
        self.shorts = self.add(npyscreen.MultiSelect, name="Shorts", values=[], scroll_exit=True, max_height=-4)
        self.loaded_short_count = 0
        self.selected_short_urls = []
        self.page_number = 1  # Initialize page number to 1
        self.page_display = self.add(npyscreen.Textfield, value=f"Page: {self.page_number}", editable=False, rely=-4)
        self.button = self.add(N_Button, name="Download Bulk", target_form_id="YOUTUBESHORTS")

    def beforeEditing(self):
        if self.channel_name_value:
            try:
                self.load_shorts()  # Assuming load_shorts now returns something you handle
            except Exception as e:
                npyscreen.notify_confirm(str(e), title='Error', wrap=True)

    def on_ok(self):
        if not self.shorts.values:
            self.load_shorts()
            return
        elif "Load 20 More" in [self.shorts.values[i] for i in self.shorts.value]:
            self.page_number += 1
            self.get_selected_shorts()
            return
        else:
            self.get_selected_shorts()
            
            new_channel_form = self.parentApp.getForm("NEWCHANNEL")
            new_channel_form.channel_name.value = ""
            new_channel_form.edit()
            new_channel = new_channel_form.channel_name.value
            if new_channel:
                self.channel_name_value = new_channel
                self.loaded_short_count = 0
            else:
                self.start_download_and_inference()

    def load_shorts(self):
        # Call youtube_downloader_shorts.py functions
        channel_shorts = youtube_downloader_shorts.get_latest_shorts(self.channel_name_value, start=self.loaded_short_count, count=20)
        short_titles = [short[0] for short in channel_shorts] + ["Load 20 More"]
        
        self.shorts.value = []
        self.shorts.values = short_titles
        self.loaded_short_count += 20
        self.shorts.cursor_line = 0
        self.page_display.value = f"Page: {self.page_number}"
        self.page_display.display()
        self.shorts.display()
        self.display()

    def get_selected_shorts(self):
        selected_shorts = [self.shorts.values[i] for i in self.shorts.value if i != len(self.shorts.values) - 1]
        all_shorts = youtube_downloader_shorts.get_latest_shorts(self.channel_name_value, start=self.loaded_short_count - 20, count=20)
        self.selected_short_urls.extend([url for title, url in all_shorts if title in selected_shorts])
    
    def download_n_videos(self, n):
        self.selected_short_urls = []  # Clear previously selected videos
        all_shorts = youtube_downloader_shorts.get_latest_shorts(self.channel_name_value, start=0, count=n)
        self.selected_short_urls.extend([url for _, url in all_shorts])
        self.start_download_and_inference()

    def start_download_and_inference(self):
        threading.Thread(target=processor.inference_worker).start()

        def download_and_infer():
            for url in self.selected_short_urls:
                with print_lock:
                    short_file = youtube_downloader_shorts.download_short(url)
                processor.waiting_for_inference.put(short_file)
            for _ in range(processor.MAX_INFERENCE_THREADS):
                processor.waiting_for_inference.put(None)

        threading.Thread(target=download_and_infer).start()
        self.parentApp.switchForm(None)

    def on_cancel(self):
        self.parentApp.switchForm('MAIN')

#============== Folder ==============
class FolderProcessForm(npyscreen.ActionForm):
    def create(self):
        self.folder_name = self.add(npyscreen.TitleText, name="Enter Folder Name:")

    def on_ok(self):
        if os.path.exists(self.folder_name.value):
            processor.process_folder(self.folder_name.value)
            self.parentApp.switchForm(None)
        else:
            npyscreen.notify_confirm("Invalid folder path. Please enter a valid folder.", title="Error", wrap=True)

    def on_cancel(self):
        self.parentApp.switchForm('MAIN')

class CustomColorTheme(npyscreen.ThemeManager):
    default_colors = {
        'DEFAULT': 'WHITE_BLACK',
        'WARNING': 'YELLOW_BLACK',
        'DANGER': 'RED_BLACK',
        'GOOD': 'GREEN_BLACK',
    }

def main():
    try:
        app = App()
        app.run()
    finally:
        for thread in app.threads:
            try:
                thread.join()
            except Exception as e:
                print(f'Error while waiting for thread to join: {e}')

if __name__ == "__main__":
    main()