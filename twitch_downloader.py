import os
import subprocess
import requests
import threading
import json

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

CLIENT_ID = config["twitch_downloader"]["CLIENT_ID"]
OAUTH_TOKEN = config["twitch_downloader"]["OAUTH_TOKEN"]
desired_quality = config["twitch_downloader"]["DESIRED_QUALITY"]

HEADERS = {
    'Client-ID': CLIENT_ID,
    'Authorization': f"Bearer {OAUTH_TOKEN}"
}

print_lock = threading.Lock()

def download_single_vod(channel_name, vod_id):
    print(f"Attempting to download VOD ID: {vod_id}")  # Debug line
    # Ensure the 'vods' directory exists
    if not os.path.exists("vods"):
        os.makedirs("vods")

    # Define video quality format codes
    quality_codes = {
        "1080p": "1080p60",
        "720p": "720p60",
        "480p": "480p",
        "360p": "360p",
    }

    # Define desired video quality
    quality = quality_codes.get(desired_quality, "best")

    root_directory = os.getcwd()  # This gets the current working directory of the script
    output_path = os.path.join(root_directory, "vods", f"{vod_id}.mp4")
    
    # Construct the command to use yt-dlp
    cmd = f"yt-dlp https://www.twitch.tv/videos/{vod_id} -f {quality} -o {output_path}"
    
    # Print the command for debugging
    print(f"Executing command: {cmd}")
    
    # Run the command in a non-blocking manner and capture the output in real-time
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            with print_lock:  # Use the print lock to ensure synchronized printing
                print(output.strip(), end='\r')  # Use end='\r' to overwrite the current line
    rc = process.poll()

    # Check for errors in the result
    stderr_output = process.stderr.read()
    if "ERROR" in stderr_output or "Unhandled exception" in stderr_output:
        print(f"\nError downloading VOD {vod_id}: VOD not found or inaccessible.")
        return None

    print("\nDownload completed.")

    trimming_config = config["twitch_downloader"]
    if trimming_config["ENABLE_TRIMMING"]:
        print("Trimming video...")
        start_time_seconds = trimming_config["START_TIME_MINUTES"] * 60
        end_time_seconds = trimming_config["END_TIME_MINUTES"] * 60

        # Ensure end_time is after start_time
        if end_time_seconds <= start_time_seconds:
            print("Error: END_TIME_MINUTES is not greater than START_TIME_MINUTES. Skipping trimming.")
        else:
            trimmed_output_path = os.path.join(root_directory, "vods", f"trimmed_{vod_id}.mp4")
            success = trim_video(output_path, start_time_seconds, end_time_seconds, trimmed_output_path)
            if success:
                print(f"Trimmed video saved to {trimmed_output_path}")
                try:
                    os.remove(output_path)  # Delete the original VOD file
                    print(f"Original VOD file {output_path} deleted.")
                except Exception as e:
                    print(f"Failed to delete original VOD file: {e}")
                return trimmed_output_path  # Return the path to the trimmed video
            else:
                print("Failed to trim video.")

    return output_path

def get_user_id(channel_name):
    url = f"https://api.twitch.tv/helix/users?login={channel_name}"
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    #print(data)
    
    if 'data' in data and len(data['data']) > 0:
        return data['data'][0]['id']
    else:
        print("Error fetching user ID. Check the response above for details.")
        return None

def get_latest_vod_ids(user_id, num_vods=1, after_cursor=None):
    url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&first={num_vods}&type=archive"
    if after_cursor:
        url += f"&after={after_cursor}"
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    return [vod['id'] for vod in data['data']]
    
def get_latest_vods(channel_name, num_vods=10, after_cursor=None):
    user_id = get_user_id(channel_name)
    if not user_id:
        print(f"Failed to get user_id for channel: {channel_name}")
        return [], None  # Return empty list and None for after_cursor

    url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&first={num_vods}&type=archive"
    if after_cursor:
        url += f"&after={after_cursor}"
        
    response = requests.get(url, headers=HEADERS)
    data = response.json()

    if 'data' not in data:
        print(f"Error fetching VODs. Response: {data}")
        return [], None  # Return empty list and None for after_cursor

    after_cursor = data['pagination'].get('cursor', None) if 'pagination' in data else None
    return [(vod['title'], vod['id']) for vod in data['data']], after_cursor

def trim_video(input_path, start_time, end_time, output_path):
    cmd = f"ffmpeg -y -i {input_path} -ss {start_time} -to {end_time} -c:v copy -c:a copy {output_path}"
    process = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode == 0:
        return True
    else:
        print(f"Error trimming video: {process.stderr.decode('utf-8')}")
        return False

if __name__ == "__main__":
    try:
        channel_name = input("Enter the Twitch channel name: ")
        video_path = download_single_vod(channel_name)
        if video_path:
            print(f"Downloaded VOD to {video_path}")
        else:
            print("Failed to download VOD.")
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting...")