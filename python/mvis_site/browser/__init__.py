"""Drivers that measure the built site in Chrome (Playwright) or read media with ffprobe. The rules live in checks.py.

Each Playwright run() imports Playwright inside and is excluded from coverage (it needs Chrome and a served build);
what it prints and decides comes from checks.py, which is unit-tested. media_probe is tested with stub readers.
"""
