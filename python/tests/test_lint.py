import re

import pytest
import yaml

from mvis_site import DATA
from mvis_site import lint as L

# One case per BANNED pattern. Values are synthetic: no real path, commit or device id goes in a public repo.
CAUGHT = [("/home/u/x", "internal path"), ("/tmp/x", "internal path"), ("~/x", "internal path"), ("openmvis-internal", "internal path"),
          ("results/x", "internal path"), ("in mira", "internal path"), ("Take 0123", "internal path"),
          ("commit abc1234", "hash or device id"), ("0123456789abcdef", "hash or device id"),
          ("a factory value", "maker comparison"), ("vendor lever", "maker comparison"),
          ("the best sensor", "rating"), ("ranked first", "rating"), ("ranking", "rating"), ("scores", "rating"), ("winner", "rating"),
          ("roll", "RPY"), ("pitch and yaw", "RPY"), ("RPY deg", "RPY"),
          ("Private draft", "private wording"), ("Unconfirmed", "private wording"), ("your OK", "private wording"),
          ("your note", "private wording"), ("your statement", "private wording")]


@pytest.mark.parametrize("text,why", CAUGHT)
def test_each_banned_pattern_is_caught(text, why):
    found = L.public_problems(text)
    assert found and any(f.startswith(why + ":") for f in found), text


def test_every_banned_pattern_has_a_case():
    assert {w for _, w in L.BANNED} == {w for _, w in CAUGHT}


def test_word_rules_ignore_case_but_the_hash_rule_does_not():
    assert L.public_problems("FACTORY") and L.public_problems("Best") and L.public_problems("rpy")
    assert not L.public_problems("ABCDEF0123")  # upper-case hex is a word, not a lower-case hash


def test_numbers_and_a_full_sha_pass():
    assert not L.public_problems('"readout": 1.3206776078716269e-11, sha ' + "0123456789abcdef" * 4)
    assert not L.public_problems("Rotation is log(R) in rad. Solved readout about 26 ms. Full results. 1234567 frames")


def test_a_long_hex_shorter_than_a_sha_is_caught():
    assert L.public_problems("0123456789abcdef" * 2)


def test_problem_names_the_match_and_its_context():
    (p,) = L.public_problems("x" * 50 + " vendor " + "y" * 50)
    assert p.startswith("maker comparison: 'vendor' in ...'") and "x" * 39 + " vendor " + "y" * 39 in p


def test_strip_urls_removes_links_only():
    assert L.strip_urls('see https://a.b/home/u/x and "http://c.d/e" <a href=https://x/y>z</a>') == 'see  and "" <a href=</a>'  # a link runs to the next space, quote or <


def test_process_strings_keeps_words_not_numbers():
    assert L.process_strings('{"name":"cam0","x":"AAAA1234","n":"12","p":"a/b","q":"0.5"}') == "name cam0 x AAAA1234 n p a/b q"


def test_refusals_name_paths_the_token_and_the_local_user():
    assert L.refusals("ok text", user="someone") == []
    assert L.refusals("/home/x someone HF_TOKEN", user="someone") == ["/home/", "HF_TOKEN", "someone"]


def test_refusals_default_to_whoever_runs_the_export(monkeypatch):
    monkeypatch.setattr(L.getpass, "getuser", lambda: "builder")
    assert L.refusals("by builder") == ["builder"]
    monkeypatch.setattr(L.getpass, "getuser", lambda: "ci")  # too short to tell from a word
    assert L.local_user() is None and L.refusals("ci circle") == []
    monkeypatch.setattr(L.getpass, "getuser", lambda: "abcd")  # 4 letters: the shortest name refused
    assert L.refusals("by abcd") == ["abcd"]
    monkeypatch.setattr(L.getpass, "getuser", lambda: "abc")
    assert L.local_user() is None

    def no_name():
        raise KeyError("uid")
    monkeypatch.setattr(L.getpass, "getuser", no_name)
    assert L.local_user() is None and L.refusals("/home/") == ["/home/"]


def test_committed_public_text_passes_the_lint():
    text = (DATA / "public_sensors.yaml").read_text(encoding="utf-8")
    body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    assert L.public_problems(L.strip_urls(body)) == []


def test_committed_public_text_names_no_take_id():
    # take ids are the first hex digits of a device id; clip and file names must not carry one either
    text = (DATA / "public_sensors.yaml").read_text(encoding="utf-8")
    ids = re.findall(r"(?<![0-9A-Za-z])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{4,6}(?![0-9A-Za-z])", L.strip_urls(text))
    models = {"d455", "d456"}      # RealSense product names that happen to read as hex
    assert [i for i in ids if i not in models] == []


def test_committed_public_text_names_no_recording_path():
    pub = yaml.safe_load((DATA / "public_sensors.yaml").read_text(encoding="utf-8"))
    assert not [s for s, p in pub["sensors"].items() if "sha256_of" in p]
    assert "{G}" not in (DATA / "public_sensors.yaml").read_text(encoding="utf-8")
