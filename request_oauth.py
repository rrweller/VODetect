import requests

CLIENT_ID = 'ENTER CLIENT_ID HERE'
CLIENT_SECRET = 'ENTER CLIENT_SECRET HERE'

def get_oauth_token():
    url = "https://id.twitch.tv/oauth2/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials',
        'scope': 'user:read:broadcast'  # Scope for reading non-public channel information
    }
    
    response = requests.post(url, data=payload)
    data = response.json()
    
    if 'access_token' in data:
        return data['access_token']
    else:
        print("Error:", data['message'])
        return None

oauth_token = get_oauth_token()
print("OAuth Token:", oauth_token)
