import requests
import json
import subprocess
import os
import time
import streamlink
import sys

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

OUTPUT_DIR = "vods"
ffmpeg_processes = {}

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_stream_url(channel_name):
    try:
        streams = streamlink.streams(f'https://www.twitch.tv/{channel_name}')
        if 'best' in streams:
            return streams['best'].url
        else:
            return None
    except Exception as e:
        print(f"Error fetching stream URL for channel {channel_name}: {e}")
        return None

def check_channel_status(channel_name):
    try:
        streams = streamlink.streams(f'https://www.twitch.tv/{channel_name}')
        if streams:
            return "online"
        else:
            return "offline"
    except Exception as e:
        print(f"Error checking status for channel {channel_name}: {e}")
        return "error"

def download_stream(channel_name):
    stream_url = get_stream_url(channel_name)
    if not stream_url:
        print(f"Failed to get stream URL for {channel_name}.")
        return

    output_path = generate_output_path(channel_name)
    print(f"Downloading stream for {channel_name} to {output_path}...")
    process = subprocess.Popen(["ffmpeg", "-i", stream_url, "-c", "copy", output_path])
    ffmpeg_processes[channel_name] = process

def generate_output_path(channel_name):
    filename = f"{channel_name}_{time.strftime('%Y%m%d%H%M%S')}.mp4"
    return os.path.join(OUTPUT_DIR, filename)

def stop_download(channel_name):
    if channel_name in ffmpeg_processes:
        if sys.platform == "win32":
            os.kill(ffmpeg_processes[channel_name].pid, subprocess.signal.CTRL_C_EVENT)
        else:
            ffmpeg_processes[channel_name].send_signal(subprocess.signal.SIGINT)
        # Remove the wait() method to avoid blocking
        del ffmpeg_processes[channel_name]

if __name__ == "__main__":
    # Example usage
    channel = "example_channel"
    if check_channel_status(channel) == "online":
        download_stream(channel)