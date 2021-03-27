import queue
import re
import threading

import praw
import pyperclip
import time

import requests

from ClipboardWatcher import ClipboardWatcher, log_clipboard
from bs4 import BeautifulSoup

REDDIT_USERNAME = ""
REDDIT_PASSWORD = ""
REDDIT_CLIENT_ID = ""
REDDIT_CLIENT_SECRET = ""


def parse_clipboard(url: str):
    if url.startswith("https://www.reddit.com/r/hentai"):
        q.put(url)
        return True
    else:
        return False


def link_fetcher(i, url_queue):
    while True:
        post_url = url_queue.get()
        submission = reddit_api.submission(url=post_url)
        found = False
        hentai_sauce = ""
        for comment in submission.comments:
            if comment.author == "HentaiSauce_Bot":
                found = True
                hentai_sauce = comment.body_html
                break
        f = open("links.txt", "a")
        if found:
            soup = BeautifulSoup(hentai_sauce, features="html.parser")
            for link in soup.findAll('a', attrs={'href': re.compile("^https://")}):
                if link.get('href').startswith("https://www.pixiv.net/member_illust.php?mode=medium&illust_id="):
                    response = requests.get(link.get('href'))
                    if not response.status_code == 404:
                        print("Found sauce: " + link.get('href'))
                        f.write(link.get('href') + "\n")
                        break
                elif link.get('href').startswith("https://danbooru.donmai.us/post/show/"):
                    response = requests.get(link.get('href'))
                    if not response.status_code == 404:
                        print("Found sauce: " + link.get('href'))
                        f.write(link.get('href') + "\n")
                        break
                else:
                    continue
        else:
            for comment in submission.comments:
                soup = BeautifulSoup(comment.body_html, features="html.parser")
                links = soup.findAll('a', attrs={'href': re.compile("^https://")})
                found = False
                if len(links) > 0:
                    for link in links:
                        current_link = link.get('href')
                        if not current_link.startswith("https://twitter.com"):
                            if any(l in link.contents[0] for l in
                                   ["Sauce", "pixiv", "Pixiv", "booru", "sauce", "source", "Source"]):
                                print("Found sauce: " + current_link)
                                f.write(current_link + "\n")
                                found = True
                                break
                    else:
                        continue
                else:
                    continue
                break
            if not found:
                f.write(post_url + "\n")
        f.close()
        print("Done!")
        url_queue.task_done()


def main():
    watcher = ClipboardWatcher(parse_clipboard,
                               log_clipboard,
                               0.5)
    watcher.start()

    for i in range(2):
        download_worker = threading.Thread(target=link_fetcher, args=(i, q))
        download_worker.start()

    print("Monitoring clipboard for URLs. Ctrl+C to exit.")
    while True:
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            watcher.stop()
            break


if __name__ == "__main__":
    q = queue.Queue()
    reddit_api = praw.Reddit(client_id=REDDIT_CLIENT_ID,
                             client_secret=REDDIT_CLIENT_SECRET,
                             password=REDDIT_PASSWORD,
                             user_agent='some script by /u/mclarence',
                             username=REDDIT_USERNAME)
    main()
