import requests
import json
from urllib.parse import quote
from pathlib import Path
from tqdm import tqdm
import time

token_file_path = 'token.txt'

def robust_request(url, max_retries=5, backoff_factor=0.3):
    for i in range(max_retries):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            return response
        except requests.ConnectionError:
            if i < max_retries - 1:
                sleep_time = backoff_factor * (2 ** i)
                print(f"Request failed. Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                raise
        except requests.HTTPError:
            raise

def read_token_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print("Token file not found.")
        return None

secure_civitai_token = read_token_from_file(token_file_path)

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://civitai.com",
    "Content-Type": "application/json",
    "DNT": "1",
    "Alt-Used": "civitai.com",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "TE": "trailers"
}

def download_image_and_metadata(item, username):
    base_image_url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/"
    image_url = f"{base_image_url}{item['url']}/original=true/"

    user_dir = Path(f"users/{username}")
    user_dir.mkdir(parents=True, exist_ok=True)

    image_path = user_dir / f"{item['url']}.png"
    metadata_path = user_dir / f"{item['url']}.json"

    if not image_path.exists():
        try:
            response = robust_request(image_url)
            total_size_in_bytes = int(response.headers.get('content-length', 0))
            progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
            with open(image_path, 'wb') as f:
                for data in response.iter_content(1024):
                    progress_bar.update(len(data))
                    f.write(data)
            progress_bar.close()
        except Exception as e:
            print(f"Failed to download image: {e}")

    if not metadata_path.exists():
        with open(metadata_path, 'w') as f:
            json.dump(item, f, indent=4)

def fetch_images(username, cursor=None):
    base_url = "https://civitai.com/api/trpc/image.getInfinite"

    # For the initial request, include 'meta'; for subsequent requests, exclude 'meta'
    if cursor is None:  # Initial request
        payload = {
            "json": {
                "period": "AllTime",
                "sort": "Newest",
                "view": "feed",
                "types": ["image"],
                "username": username,
                "withMeta": False,
                "cursor": cursor,  # This will be None for the initial request
                "authed": True
            },
            "meta": {
                "values": {
                    "cursor": ["undefined"]
                }
            }
        }
    else:  # Subsequent requests
        payload = {
            "json": {
                "period": "AllTime",
                "sort": "Newest",
                "view": "feed",
                "types": ["image"],
                "username": username,
                "withMeta": False,
                "cursor": cursor,  # This will have the nextCursor value for subsequent requests
                "authed": True
            }
        }


    encoded_input = 'input=' + quote(json.dumps(payload))
    url = f"{base_url}?{encoded_input}"
    response = requests.get(url, headers=headers, cookies={"__Secure-civitai-token": secure_civitai_token})
    return response



def main():
    if not secure_civitai_token:
        print("Secure-civitai-token not available. Exiting...")
        return

    username = input("Enter the username to download images for: ")
    cursor = None
    while True:
        response = fetch_images(username, cursor)
        if response.status_code == 200:
            data = response.json()
            items = data["result"]["data"]["json"]["items"]
            cursor = data["result"]["data"]["json"].get("nextCursor")
            print(f"Next cursor: {cursor}")
            for item in items:
                download_image_and_metadata(item, username)
            if not cursor:
                print("No more items to process for this username.")
                break  # Exit the loop if no further pages are available
        else:
            print(f"Failed to retrieve data. Status code: {response.status_code}")
            # Save the response into a JSON file in the 'errors' folder
            error_folder = "errors"
            error_file_path = f"{error_folder}/{username}.json"
            Path(error_folder).mkdir(parents=True, exist_ok=True)
            with open(error_file_path, 'w') as error_file:
                json.dump(response.json(), error_file, indent=4)
            break
        time.sleep(0.7)

if __name__ == '__main__':
    main()
