The script to check lostfilm.tv's rss feed and download .torrent files of serials you want.

To start it is required to set some environment variables and insert to DB preferred serials:
1. Some environment variables:
- `LF_ID` - Your lostfilm account's `uid`, how to get: https://qna.habr.com/q/17175, https://gist.github.com/danilvalov/fecfce169d2ff0d31e53eff3e0be991e#gistcomment-2004465
- `LF_USESS` - Your retre.org session id, how to get: https://qna.habr.com/q/17175, https://gist.github.com/danilvalov/fecfce169d2ff0d31e53eff3e0be991e#gistcomment-2004465
- `LF_PTD` - Path To Download torrent files
- `LF_DISCORD_HOOK` - Discord webhook url to send notifications

2. Add to db preferred serials:
Basically, you have to run this software once in order to create sqlite database, and then
you need to insert patterns to search serials to `tracked_serials` table with preferred quality, as example:
`insert into tracked_serials (name_pattern, preferred_quality) values ("The Expanse", 0);` this command will insert
to `The Expanse` serial which quality `0` which mean 1080p, here the mapping 

| in DB | human |
|-------|-------|
|0      |1080p  |
|1      |MP4    |
|2      |SD     |


