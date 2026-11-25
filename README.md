# news-image-20261124

[![make.fun · news-image-20261124](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![rank](https://make.fun/badge/news-image-20261124/wzs2004816/news-image-20261124/rank.svg)](https://make.fun/bounty/news-image-20261124/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![reward](https://make.fun/badge/news-image-20261124/wzs2004816/news-image-20261124/reward.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)

Sum up Tuesday 24 November 2026's world news in one image — a newspaper
front page drawn by a pure-stdlib Python program.

[View the bounty](https://make.fun/bounty/news-image-20261124) ·
[My make.fun referral](https://make.fun/r/zy5dg92r)

## The image

**"THE WORLD IN ONE PAGE — Tuesday, 24 November 2026"**: 44 stories across
8 regions, with 15 drawn scenes — three hero illustrations (Nvidia's
Jensen Huang returns and markets roar; fallout from Kyiv's Libya strike;
Russian strikes kill 14 in the Kyiv region), five spot illustrations, a
dotted world map with ten numbered story markers, a day-around-the-world
timeline, and a 36-story grid. A DATE CHECK box lists the neighbouring-day
stories deliberately left out (COP31 collapse, the Democrats' 258th House
seat, Pant's 128, the Peru quake, the ICJ Rohingya verdict, and more).

Every story was first reported on Tuesday 24 November 2026 in some time
zone. Sources: AP, Reuters, Bloomberg, CNN, SCMP, Al Jazeera, BBC,
The Times, Le Monde, The Japan Times, The Hindu, Manila Times, Arab News.

## Run it

```sh
mkdir -p out
MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
# writes out/entry.png — 1024x1024 PNG, deterministic, byte-identical
# across runs
```

`main.py` is Python 3 standard library only. It reads the data files
shipped in this repo (`atlas.bin` / `atlas.json` — glyph bitmaps rendered
at build time from system DejaVu fonts; `map.txt` — a land/sea dot grid
derived from Natural Earth land polygons) and draws the whole front page
with its own canvas, font, and PNG code. No network, no clock, no
randomness.

## License

MIT — see [LICENSE](LICENSE).
