import requests
import json
import subprocess

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

CLIENT_ID = config["twitch_downloader"]["CLIENT_ID"]
OAUTH_TOKEN = config["twitch_downloader"]["OAUTH_TOKEN"]

def get_m3u8_link(channel_name, client_id, oauth_token):
    # 1. Get the channel's ID
    HEADERS = {
        'Client-ID': CLIENT_ID,
        'Authorization': f"Bearer {OAUTH_TOKEN}"
    }
    response = requests.get(f"https://api.twitch.tv/helix/users?login={channel_name}", headers=headers)
    user_data = response.json()
    user_id = user_data['data'][0]['id']

    # 2. Get the access token and signature
    access_response = requests.get(f"https://api.twitch.tv/api/channels/{channel_name}/access_token")
    access_data = json.loads(access_response.text)
    token = access_data['token']
    sig = access_data['sig']

    # 3. Get the m3u8 link
    m3u8_response = requests.get(f"https://usher.ttvnw.net/api/channel/hls/{channel_name}.m3u8?player=twitchweb&&token={token}&sig={sig}&allow_audio_only=true&allow_source=true&type=any&p=12345")
    m3u8_link = m3u8_response.text.split('\n')[2]  # This might need adjustment based on the response structure

    return m3u8_link

def download_stream(m3u8_link, output_path):
    cmd = [
        'ffmpeg', 
        '-i', m3u8_link, 
        '-c', 'copy', 
        '-bsf:a', 'aac_adtstoasc', 
        output_path
    ]
    subprocess.run(cmd, check=True)

def check_channel_status(channel_name):
    # Check if the channel is online or offline using the Twitch API
    HEADERS = {
        'Client-ID': CLIENT_ID,
        'Authorization': f"Bearer {OAUTH_TOKEN}"
    }
    response = requests.get(f"https://api.twitch.tv/helix/streams?user_login={channel_name}", headers=HEADERS)
    
    # Check if the request was successful
    if response.status_code != 200:
        print(f"Error fetching data for channel {channel_name}. Status code: {response.status_code}. Response: {response.text}")
        return "error"

    data = response.json()

    # Check if the 'data' key exists in the response
    if "data" not in data:
        print(f"Unexpected response format for channel {channel_name}. Response: {response.text}")
        return "error"

    if data["data"]:
        return "online"
    else:
        return "offline"

