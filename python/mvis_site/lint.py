"""What may reach a public page. BANNED is the rule; nothing here may relax it."""
from __future__ import annotations

import getpass
import re

BANNED = [(r"/home/|/tmp/|~/|openmvis-internal|results/|\bmira\b|\bTake [0-9a-f]{4}\b", "internal path"), (r"\b[0-9a-f]{7,40}\b(?<!\d{7})", "hash or device id"),
          (r"\bfactory\b|\bvendor\b", "maker comparison"), (r"\b(best|rank(ed|ing)?|score[sd]?|winner)\b", "rating"),
          (r"\b(roll|pitch|yaw)\b|\bRPY\b", "RPY"), (r"Private|Unconfirmed|your (OK|note|statement)", "private wording")]

ALLOWED = (re.compile(r"[0-9a-f]{64}"),)



def public_problems(text: str) -> list[str]:
    """Words that must not reach a public page. Long hex strings allowed only as a full sha256."""
    clean = re.sub(r"-?\d+\.\d+(e[-+]?\d+)?", "0", text)
    for a in ALLOWED:
        clean = a.sub("", clean)
    out = []
    for pat, why in BANNED:
        m = re.search(pat, clean, re.I if why != "hash or device id" else 0)
        if m:
            out.append(f"{why}: {m.group(0)!r} in ...{clean[max(0, m.start() - 40):m.end() + 40]!r}")
    return out




def strip_urls(text: str) -> str:
    """Links leave the lint: a maker's URL may hold /home/ or a profile id that isn't ours."""
    return re.sub(r"https?://[^\s\"'<]+", "", text)


def process_strings(json_text: str) -> str:
    """The words in a process figure's JSON. Base64 numbers and bare numbers carry no text, so only quoted strings
    with a letter or slash are linted."""
    return " ".join(re.findall(r'"([^"]*[A-Za-z/][^"]*)"', json_text))


REFUSE = ("/home/", "HF_TOKEN")


def local_user() -> str | None:
    """The login name of whoever runs the export, so a stray local path or name never ships. Read at run time, not
    written here: the repo is public. Names under 4 letters would match ordinary words, so they are left out."""
    try:
        name = getpass.getuser()
    except Exception:  # no login name in some containers
        return None
    return name if len(name) >= 4 else None


def refusals(text: str, user: str | None = None) -> list[str]:
    """Words that stop a results table (board.json, board.css, uzh_fpv.json) from being written, links included.
    The sensor export uses public_problems instead: a maker's link there may hold /home/. user defaults to local_user()."""
    user = local_user() if user is None else user
    return [w for w in (*REFUSE, *([user] if user else [])) if w in text]
