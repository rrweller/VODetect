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