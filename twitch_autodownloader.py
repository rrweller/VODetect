import requests
import json
import subprocess
import os
import time
import streamlink
import sys

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

OUTPUT_DIR = "livevods"
live_processes = {}
channel_inferencing = {}

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_stream_url(channel_name, desired_quality):
    try:
        streams = streamlink.streams(f'https://www.twitch.tv/{channel_name}')
        if desired_quality in streams:
            return streams[desired_quality].url
        elif 'best' in streams:
            return streams['best'].url
        else:
            return None
    except Exception as e:
        print(f"Error fetching stream URL for channel {channel_name}: {e}")
        return None

def check_channel_status(channel_name, channel_status):
    if channel_status != "inference":
        try:
            streams = streamlink.streams(f'https://www.twitch.tv/{channel_name}')
            if streams:
                return "online"
            else:
                return "offline"
        except Exception as e:
            print(f"Error checking status for channel {channel_name}: {e}")
            return "error"
    elif channel_status == "inference":
        print(f"Channel {channel_name} is in 'inferencing' state.")
        return "inference"  # or you can return "unknown" or "error" based on your use case
    else:
        print(f"Unknown status for channel {channel_name}")
        return "unknown"

def generate_output_path(channel_name):
    filename = f"{channel_name}_{time.strftime('%Y%m%d%H%M%S')}.mp4"
    return os.path.join(OUTPUT_DIR, filename)

def download_stream(channel_name):
    # Retrieve configuration options
    desired_quality = config["twitch_autodownloader"]["DESIRED_QUALITY"]
    enable_trimming = config["twitch_autodownloader"]["ENABLE_TRIMMING"]
    start_time = config["twitch_autodownloader"]["START_TIME_MINUTES"] * 60  # Convert minutes to seconds
    end_time = config["twitch_autodownloader"]["END_TIME_MINUTES"] * 60  # Convert minutes to seconds

    # Get the stream URL of the desired quality
    stream_url = get_stream_url(channel_name, desired_quality)
    if not stream_url:
        print(f"Failed to get stream URL for {channel_name}.")
        return None

    output_path = generate_output_path(channel_name)
    print(f"Downloading stream for {channel_name} to {output_path}...")

    # Construct the FFmpeg command
    cmd = ["ffmpeg", "-i", stream_url, "-c", "copy"]
    if enable_trimming:
        if start_time > 0:
            cmd.extend(["-ss", str(start_time)])
        if end_time > start_time:
            cmd.extend(["-to", str(end_time)])
    cmd.append(output_path)

    process = subprocess.Popen(cmd)
    live_processes[channel_name] = process
    process.communicate()  # Wait for the process to finish
    return output_path

def stop_download(channel_name):
    if channel_name in live_processes:
        print(f"Stopping download for {channel_name}. Process ID: {live_processes[channel_name].pid}")

        # Check if the process is still running
        if live_processes[channel_name].poll() is None:
            try:
                if sys.platform == "win32":
                    print("Sending CTRL_C_EVENT to process")
                    os.kill(live_processes[channel_name].pid, subprocess.signal.CTRL_C_EVENT)
                else:
                    print("Sending SIGINT to process")
                    live_processes[channel_name].send_signal(subprocess.signal.SIGINT)

                print("Waiting for process to terminate")
                live_processes[channel_name].wait(timeout=10)  # Wait for the process to finish
                print("Process terminated successfully")
            except subprocess.TimeoutExpired:
                print(f"Timeout expired. Force terminating {channel_name}")
                live_processes[channel_name].terminate()
            except Exception as e:
                print(f"Failed to stop ffmpeg: {e}")

        else:
            print("Process already terminated.")

        del live_processes[channel_name]

if __name__ == "__main__":
    # Example usage
    channel = "example_channel"
    if check_channel_status(channel) == "online":
        download_stream(channel)