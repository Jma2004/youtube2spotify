# import google_auth_oauthlib.flow
# import googleapiclient.discovery
# import googleapiclient.errors
import urllib.parse
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError  #Import HttpError
import urllib.parse
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
#google API credentials
client_secret_file = os.getenv("CLIENT_SECRET_FILE")
api_key = os.getenv("API_KEY")

#youtube scopes
scopes = ["https://www.googleapis.com/auth/youtube"]

# Spotify API credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://localhost:3000"

# Spotify Authentication scopes
SCOPES = "playlist-modify-private playlist-modify-public"

#Time threshold for matching song durations
TIME_THRESHOLD = 5000

def get_playlist_videos(playlist_url, youtube):
    # Extract playlist ID from URL
    parsed_url = urllib.parse.urlparse(playlist_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    playlist_id = query_params['list'][0]
    
    request = youtube.playlistItems().list(
        part='snippet',
        playlistId=playlist_id,
        maxResults=50  # Adjust as needed
    )
    try: 
        global response
        response = request.execute()
    except HttpError as e:
        return "Error requesting the playlist"
    video_data = []

    while request:
        for item in response['items']:
            video_id = item['snippet']['resourceId']['videoId']
            video_data.append({'title': item['snippet']['title'], 'id': video_id})
        if 'nextPageToken' in response:
            request = youtube.playlistItems().list(
                part='snippet',
                playlistId=playlist_id,
                maxResults=50,
                pageToken=response['nextPageToken']
            )
            response = request.execute()
        else:
            request = None
        # Fetch durations for each video
        for video in video_data:
            video_info_request = youtube.videos().list(
                part='contentDetails',
                id=video['id']
            )
            video_info = video_info_request.execute()
            if 'items' in video_info and video_info['items']:
                duration_iso = video_info['items'][0]['contentDetails']['duration']
                #Convert ISO 8601 duration to seconds (you'll need a helper function for this)
                duration_seconds = convert_iso8601_to_milliseconds(duration_iso)
                video['duration'] = duration_seconds

    return video_data

def convert_iso8601_to_milliseconds(iso_duration):
    # print(iso_duration)
    time = iso_duration[2:]
    hours = 0
    minutes = 0
    seconds = 0
    if ('H' in time):
        hours = int(time.split('H')[0])
        time = time.split('H')[1]
    if ('M' in time):
        minutes = int(time.split('M')[0])
        time = time.split('M')[1]
    if ('S' in time):
        seconds = int(time.split('S')[0])
    # print(f"{hours}:{minutes}:{seconds}")
    return (hours*360 + minutes*60 + seconds)*1000

def get_spotify_playlist(spotify_url, sp):
    spotify_url_id = spotify_url.split('/')[-1]
    try:
        result = sp.playlist_items(spotify_url_id)
    except:
        return "Invalid Spotify URL"
    song_list = []
    while(True):
        for item in result['items']:
            name = item['track']['name'] + " " + item['track']['artists'][0]['name']
            duration = item['track']['duration_ms']
            song_list.append({'title': name, 'duration': duration})
        result = sp.next(result)
        if (result == None):
            break
    return song_list

def main():
    #sign into youtube
    '''***note: add try and except for failed authentication***'''
    flow = InstalledAppFlow.from_client_secrets_file(
    client_secret_file, scopes)
    credentials = flow.run_local_server()
    youtube = build('youtube', 'v3', developerKey=api_key, credentials=credentials)

    #spotify authentication
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=SCOPES))
    continue_loop = 1
    while(continue_loop):
        mode = 0
        while(1):
            mode = int(input("Choose mode - 1 for youtube to spotify, 2 for spotify to youtube: "))
            if (mode == 1):
                print("mode: youtube to spotify")
                break
            elif (mode == 2):
                print("mode: spotify to youtube")
                break
            else:
                print("please choose a valid option")

        if (mode == 1): #youtube to spotify
            youtube_url = input("Enter the youtube playlist URL: ")
            #get the song names, lengths, artists? of each song
            #also get the playlist name
            song_list = get_playlist_videos(youtube_url, youtube)

            #create a new playlist on spotify
            playlist_name = input("Enter the name of the new playlist: ")
            user_id = sp.me()['id']
            playlist = sp.user_playlist_create(user_id, playlist_name)
            #search for each song on spotify, and add to new playlist
            for song in song_list:
                name = song['title']
                # print(f"SEARCHING FOR {name}")
                result = sp.search(q=name, type = "track", limit = 30)
                # count = 1
                for track in result['tracks']['items']:
                    # print(f"{count}. {track['name']} by {track['artists'][0]['name']}, {track['duration_ms']}")
                    # count += 1
                    if (track['duration_ms'] in range(song['duration'] - TIME_THRESHOLD, song['duration'] + TIME_THRESHOLD)): 
                        sp.playlist_add_items(playlist['id'], [track['uri']])
                        break
                else:
                    print(f"{name} not found")
                pass
        elif (mode == 2): #spotify to youtube
            spotify_url = input("Enter the spotify playlist URL: ")
            song_list = get_spotify_playlist(spotify_url, sp)
            #create a new playlist on youtube
            playlist_name = input("Enter the name of the new playlist: ")
            request = youtube.playlists().insert(
                part='snippet',
                body={
                    'snippet': {
                        'title': playlist_name
                    }
                }
            )
            response = request.execute()
            #search for each song on youtube, and add to new playlist
            for song in song_list:
                name = song['title']
                print(f"SEARCHING FOR {name}")
                search_request = youtube.search().list(
                    q=name,
                    part='id',
                    maxResults=10,
                    type='video'
                )
                search_response = search_request.execute()
                for item in search_response['items']:
                    video_id = item['id']['videoId']
                    video_request = youtube.videos().list(
                        part='contentDetails',
                        id=video_id
                    )
                    video_response = video_request.execute()
                    duration = convert_iso8601_to_milliseconds(video_response['items'][0]['contentDetails']['duration'])
                    if (duration in range(song['duration'] - TIME_THRESHOLD, song['duration'] + TIME_THRESHOLD)):
                        #add video to playlist
                        request = youtube.playlistItems().insert(
                            part='snippet',
                            body={
                                'snippet': {
                                    'playlistId': response['id'],
                                    'resourceId': {
                                        'kind': 'youtube#video',
                                        'videoId': video_id
                                    }
                                }
                            }
                        )
                        request.execute()
                        break
                else:
                    print(f"{name} not found")
            pass
        continue_loop = input("Do you want to continue? (y/n): ")
        if (continue_loop == 'n'):
            continue_loop = 0
        else:
            continue_loop = 1

if __name__ == "__main__":
    main()