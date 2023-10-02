import yt_dlp as youtube_dl
import os
import json

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

desired_quality = config["youtube_downloader"]["DESIRED_QUALITY"]

# Define video quality format codes
quality_codes = {
    "1440p": "264",  # 1440p video
    "1080p": "137",  # 1080p video
    "720p": "136",   # 720p video
    "480p": "135",   # 480p video
    "360p": "134"    # 360p video
}

format_code = quality_codes.get(desired_quality, "best")

def download_video(link):
    outtmpl = 'videos/%(title)s.%(ext)s'
    if not os.path.exists('videos'):
        os.makedirs('videos')

    # Define youtube_dl options
    ydl_opts = {
        'quiet': True,
        'format': format_code,
        'outtmpl': outtmpl,
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=True)
        filename = ydl.prepare_filename(info)
        return filename

def get_latest_videos(channel_name, start=0, count=20):
    # Define youtube_dl options for extracting video details
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': True,
        'no_warnings': True,  # Suppress warnings
        'geo_bypass': True,   # Bypass geographic restrictions
        'ignoreerrors': True,  # Ignore errors to allow the next URL format to be tried
        'nocheckcertificate': True,  # Don't check SSL certificates
        'logtostderr': False  # Don't log to stderr
    }

    # Try both URL formats
    urls = [
        f"https://www.youtube.com/c/{channel_name}/videos",
        f"https://www.youtube.com/@{channel_name}/videos"
    ]

    for url in urls:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)
            if result and 'entries' in result and result['entries']:
                # Return the videos starting from the 'start' index and fetch 'count' number of videos
                return [(entry['title'], entry['url']) for entry in result['entries'][start:start+count]]

    # If both URL attempts fail
    print(f"Warning: Channel '{channel_name}' not found on YouTube.")
    return []

if __name__ == '__main__':
    link = ""
    download_video(link)