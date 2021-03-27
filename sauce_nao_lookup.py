import json
import random
import re
import string
import threading
import time
import queue

from bs4 import BeautifulSoup

from ClipboardWatcher import ClipboardWatcher, log_clipboard
import requests

PREVIOUS_STATUS_CODE = None

STATUS_CODE_OK = 1
STATUS_CODE_SKIP = 2
STATUS_CODE_REPEAT = 3

API_KEY = None


def parse_clipboard(url):
    if url.startswith("http://") or url.startswith("https://"):
        q.put(url)
        return True
    return False


def queue_processor(i, queue_obj):
    while True:
        current_url = queue_obj.get()
        print("Looking up " + current_url)
        try:
            response = lookup_url(current_url)
        except DailyLimitReachedException:
            response = lookup_url(current_url, get_new_api_key())
        f = open("links_saucenao.txt", "a")
        url_to_use = None
        done = False
        for result in response['results']:
            if done:
                break
            similarity = float(result['header']['similarity'])
            if similarity > 80:
                for url in result['data']['ext_urls']:
                    if url.startswith("https://www.pixiv.net"):
                        response = requests.get(url)
                        if not response.status_code == 404:
                            print("Found sauce: " + url)
                            url_to_use = url
                            done = True
                            break
                    elif url.startswith("https://danbooru.donmai.us/post/show/"):
                        response = requests.get(url)
                        if not response.status_code == 404:
                            print("Found sauce: " + url)
                            url_to_use = url
                            done = True
                            break
                    else:
                        continue

        if url_to_use:
            f.write(url_to_use + "\n")
        else:
            f.write(current_url + "\n")

        f.close()
        print("Done")
        queue_obj.task_done()


def main():
    watcher = ClipboardWatcher(parse_clipboard,
                               log_clipboard,
                               0.5)
    watcher.start()

    for i in range(1):
        queue_worker = threading.Thread(target=queue_processor, args=(i, q))
        queue_worker.start()

    while True:
        try:
            print("Waiting for changed clipboard...")
            time.sleep(10)
        except KeyboardInterrupt:
            watcher.stop()
            break


def get_http_params(url: str, api_key=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/63.0.3239.84 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-DE,en-US;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive'
    }

    params = {
        'file': '',
        'Content-Type': 'application/octet-stream',
        # parameters taken from form on main page: https://saucenao.com/
        'url': url,
        'frame': 1,
        'hide': 0,
        # parameters taken from API documentation: https://saucenao.com/user.php?page=search-api
        'output_type': 2,
        'db': 999,
    }

    if api_key:
        params['api_key'] = api_key

    return params, headers


def randomString(stringLength=10):
    """Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


def get_new_api_key():
    request = requests.get("https://saucenao.com/user.php")
    soup = BeautifulSoup(request.text, features="html.parser")
    token = soup.find("input", {"name": "token"})['value']
    username = randomString()
    password = randomString()
    params = {
        'username': username,
        'email': username + "@gmail.com",
        'password': password,
        'password_conf': password,
        'token': token
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/63.0.3239.84 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-DE,en-US;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive'
    }

    cookies = {'token': token}

    register_response = requests.post(url='https://saucenao.com/user.php?page=register', data=params, headers=headers,
                                      cookies=cookies)
    if register_response.status_code == 200:
        api_page = requests.get("https://saucenao.com/user.php?page=search-api", cookies=register_response.cookies)
        if api_page.status_code == 200:
            soup = BeautifulSoup(api_page.text, features="html.parser")
            api_key_search = soup.find_all(text=re.compile("^api key: "))
            api_key = api_key_search[0].partition(": ")[2]
            return api_key


def lookup_url(url: str, api_key=None):
    global PREVIOUS_STATUS_CODE
    params, headers = get_http_params(url, api_key)
    link = requests.post(url='http://saucenao.com/search.php', params=params, headers=headers)

    code, msg = verify_status_code(link, url)

    if code == 2:
        print(msg)
        return json.dumps({'results': []})
    elif code == 3:
        if not PREVIOUS_STATUS_CODE:
            PREVIOUS_STATUS_CODE = code
            print(
                "Received an unexpected status code (message: {msg}), repeating after 10 seconds...".format(msg=msg)
            )
            time.sleep(10)
            return self.lookup_url(url)
        else:
            raise UnknownStatusCodeException(msg)
    else:
        PREVIOUS_STATUS_CODE = None

    return json.loads(link.text)


def verify_status_code(request_response: requests.Response, url: str) -> tuple:
    global STATUS_CODE_OK, STATUS_CODE_REPEAT, STATUS_CODE_SKIP
    if request_response.status_code == 200:
        return STATUS_CODE_OK, ''

    elif request_response.status_code == 429:
        if 'user\'s rate limit' in request_response.text:
            msg = "Search rate limit reached"
            return STATUS_CODE_REPEAT, msg
        if 'limit of 150 searches' in request_response.text:
            raise DailyLimitReachedException('Daily search limit for unregistered users reached')
        elif 'limit of 300 searches' in request_response.text:
            raise DailyLimitReachedException('Daily search limit for basic users reached')
        else:
            raise DailyLimitReachedException('Daily search limit reached')
    elif request_response.status_code == 403:
        raise InvalidOrWrongApiKeyException("Invalid or wrong API key")
    elif request_response.status_code == 413:
        msg = "Payload too large, skipping file: {0:s}".format(url)
        return STATUS_CODE_SKIP, msg
    else:
        msg = "Unknown status code: {0:d}".format(request_response.status_code)
        return STATUS_CODE_REPEAT, msg


class DailyLimitReachedException(Exception):
    pass


class InvalidOrWrongApiKeyException(Exception):
    pass


class UnknownStatusCodeException(Exception):
    pass


if __name__ == "__main__":
    q = queue.Queue()
    main()
