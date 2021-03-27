import requests
from bs4 import BeautifulSoup
import re

from sauce_nao_lookup import randomString

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
        print(api_key)
