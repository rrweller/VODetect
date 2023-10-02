import yt_dlp as youtube_dl
import os

# Since we always want the best quality for shorts, the format_code is set to 'best'
format_code = 'best'

def download_short(link):
    with youtube_dl.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(link, download=False)  # Extract info without downloading
        trimmed_title = trim_title(info['title'])  # Trim the title

    outtmpl = f'shorts/{trimmed_title}.%(ext)s'  # Use the trimmed title for the filename
    
    if not os.path.exists('shorts'):
        os.makedirs('shorts')

    # Define youtube_dl options
    ydl_opts = {
        'quiet': True,
        'format': format_code,
        'outtmpl': outtmpl,
        'progress_hooks': [lambda d: d['filename'] if d['status'] == 'finished' else None],  # Update filename after download
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([link])  # Download with the trimmed title as the filename
        filename = os.path.join('shorts', f'{trimmed_title}.mp4')  # Construct the filename based on the trimmed title
        return filename

def get_latest_shorts(channel_name, start=0, count=20):
    # Define youtube_dl options for extracting video details
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': True,
        'no_warnings': True,
        'geo_bypass': True,
        'ignoreerrors': True,
        'nocheckcertificate': True,
        'logtostderr': False
    }

    # Try both URL formats for the Shorts shelf
    urls = [
        f"https://www.youtube.com/c/{channel_name}/shorts",
        f"https://www.youtube.com/@{channel_name}/shorts"
    ]

    for url in urls:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)
            if result and 'entries' in result and result['entries']:
                return [(trim_title(entry['title']), entry['url']) for entry in result['entries'][start:start+count]]
            else:
                print(f"[DEBUG] No entries found for URL {url}")

    # If all URL attempts fail
    print(f"Warning: Channel '{channel_name}' not found on YouTube.")
    return []

def trim_title(title):
    invalid_chars = ['<', '>', ':', '"', '/', '//', '\\', '|', '?', '*', '__', '___', '____', '!', '。', ' ', '@']
    for char in invalid_chars:
        title = title.replace(char, '_')
    return title[:60]

if __name__ == '__main__':
    link = ""
    download_short(link)
