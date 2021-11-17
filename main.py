import os
import shutil
import feedparser
import requests
from datetime import datetime
import sqlite3
import logging
import sys
import os
from pathlib import Path

lostfilm_feed_link = "http://retre.org/rssdd.xml"

lostfilm_id = os.environ['LF_ID']  # ref how to get it: https://qna.habr.com/q/17175, https://gist.github.com/danilvalov/fecfce169d2ff0d31e53eff3e0be991e#gistcomment-2004465 # noqa
lostfilm_usess = os.environ['LF_USESS']
path_to_download = os.environ['LF_PTD']
discord_hook = os.environ['LF_DISCORD_HOOK']


lostfilm_cookies = {"uid": lostfilm_id, "usess": lostfilm_usess}
episodes_table_name = "episodes"
tracked_serials_table_name = "tracked_serials"

# setting up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stdout_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(process)d:%(thread)d: %(module)s:%(lineno)d: %(message)s')
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)

# torrents_dir = os.path.dirname(os.path.abspath(__file__))  # download to current dir, for debug purposes
torrents_dir = Path(path_to_download)
logger.debug(f"Torrents dir: {torrents_dir}")


def minimize_quality(quality_: str) -> int:
    return {"[MP4]": 1, "[1080p]": 0, "[SD]": 2}.get(quality_)


sqlite_connection = sqlite3.connect('lostfilm-rss-monitor-0.1.sqlite3')

with sqlite_connection:
    logger.debug("Trying to create DB")
    sqlite_connection.execute(f"create table if not exists {episodes_table_name} "
                              "(title text unique, quality text, published, "
                              "added DATATIME DEFAULT CURRENT_TIMESTAMP, link text);")

    sqlite_connection.execute(f"create table if not exists {tracked_serials_table_name} "
                              "(name_pattern text, preferred_quality integer default 0);")

logger.debug("Performing requests to feed")

try:
    r = requests.get(url=lostfilm_feed_link, cookies=lostfilm_cookies)

except requests.exceptions.ConnectionError as e:
    logger.warning("Catching exception, closing DB connection")
    sqlite_connection.close()
    raise e

if r.status_code != 200:
    logger.info(f"Feed request's status code isn't 200: {r.status_code}")

"""
*The script is wrote 20 August 2021*

1. Run by cron or systemd timer
2. Has tracked_serials table with tracked serials, preferred quality table with preferred quality
3. If found in rss feed episode is not in DB and serial in tracked_serials table and quality meet preferred quality
requirements, then process:
    1. Download episode torrent file
    2. Add it to DB
    3. Send notification

table: episodes
title       episode title, unique value, text
quality     one of [MP4], [1080p], [SD] (from tags.term), text
published   published field without day of week, text, utc, datetime
added       timestamp when episode was add to DB, done by DB, utc, datetime
link        link field, text

table: tracked_serials
name_pattern        name of serial to search in episode's title, text
preferred_quality   mapped code of quality, integer

quality mapping (upd from 17.11.2021: Idk why I used mapping when I just could use raw quality strings ¯\_(0_0)_/¯)
Carried by minimize_quality(quality_: str) -> int
mapping:
0 - [1080p]
1 - [MP4]
2 - [SD]
"""

feed = feedparser.parse(r.text)

# get tracked serials
with sqlite_connection:
    tracked_serials = list()
    for serial in sqlite_connection.execute(
            f"select name_pattern, preferred_quality from {tracked_serials_table_name}").fetchall():
        tracked_serials.append({"name_pattern": serial[0], "preferred_quality": serial[1]})

logger.debug(f"Tracked list: {tracked_serials}")

for entry in feed.entries:

    title = entry["title"]
    logger.debug(f"Checking episode: {title}")

    if "E999" in title:
        logger.info(f"{title} is full season, skipping")
        continue

    with sqlite_connection:  # Check if episode isn't in DB
        if sqlite_connection.execute(f"select count(title) from {episodes_table_name} where title = ?;",
                                     [title]).fetchone()[0] == 0:  # episode doesn't exists in DB
            logger.debug("Episode doesn't exists")

            for serial in tracked_serials:

                if serial["name_pattern"] in title:  # serial name matching

                    quality = minimize_quality(entry["tags"][0]["term"])
                    if quality == serial["preferred_quality"]:  # quality matching, we have to process this episode

                        logger.info(f"Processing episode: {title}\n in {quality} quality")
                        published = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z').strftime('%Y-%m-%d '
                                                                                                            '%H:%M:%S')
                        link = entry["link"]

                        # Downloading torrent file
                        r = requests.get(url=link, cookies=lostfilm_cookies, stream=True)
                        filename = r.headers['content-disposition'].split("=")[1].replace('"', "")
                        file_path = str(torrents_dir.joinpath(filename))
                        logger.info(f"Downloading: {file_path}")
                        with open(file_path, 'wb') as file:
                            shutil.copyfileobj(r.raw, file)

                        requests.post(url=discord_hook, data=f"content={requests.utils.quote(f'Downloading {title}')}",
                                      headers={'Content-Type': 'application/x-www-form-urlencoded'})
                        del r

                        logger.debug("Writing to DB")
                        sqlite_connection.execute(f"insert into {episodes_table_name} "
                                                  "(title, quality, published, link) values (?, ?, ?, ?);",
                                                  [title, quality, published, link])
        else:
            logger.debug("Episode does exists in DB")

sqlite_connection.close()

"""
lostfilm-rss-monitor.service
[Unit]
After=syslog.target
After=network.target

[Service]
Type=oneshot
User=user2
WorkingDirectory=/home/user2/projects_production/lostfilm-rss-monitor
ExecStart=/home/user2/projects_production/lostfilm-rss-monitor/start.bash

[Install]
WantedBy=multi-user.target

lostfilm-rss-monitor.timer
[Unit]

[Timer]
OnCalendar=*:0/3
Persistent=true

[Install]
WantedBy=multi-user.target
"""
