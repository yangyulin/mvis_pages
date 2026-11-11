"""Content rules on the committed public_sensors.yaml and its photos. The text is public, so tests may quote it."""
import re

import yaml

from mvis_site import DATA
from mvis_site.lint import public_problems, strip_urls
from mvis_site.sensor_header import thanks_html
from mvis_site.sensor_parts import dataset_rows
from mvis_site.site_files import card_for, overview_mdx, sensor_groups, sensor_nav


def _cards(pub):
    return {s: card_for(s, p) for s, p in pub["sensors"].items()}


def test_nav_lists_every_public_sensor_once_in_overview_order(pub):
    links = [n["link"] for n in sensor_nav(pub)]
    assert sorted(links) == sorted(f"/devices/{s}/" for s in pub["sensors"])
    assert links == [f"/devices/{s}/" for g in sensor_groups(pub) for s in g["slugs"]]


def test_t265_is_first_and_labels_keep_full_names(pub):
    nav = sensor_nav(pub)
    assert nav[0]["label"] == "Intel RealSense T265" and "Valve Index" in [n["label"] for n in nav]


def test_groups_follow_the_chosen_order(pub):
    assert [(g["title"], g["slugs"]) for g in sensor_groups(pub)] == [
        ("Tracking cameras and modules", ["intel-t265", "looper-insight9", "dibuli-prism-a4l", "alg-avs111c", "cyperstereo", "hampo"]),
        ("Head-worn cameras", ["gi-ego1", "gi-ego1gs", "xq20"]),
        ("VR headsets", ["valve-index", "hp-reverb-g2", "samsung-odyssey-plus"]),
    ]


def test_overview_names_every_sensor_once(pub):
    text = overview_mdx(pub)
    for g in pub["groups"]:
        assert f"\n## {g['title']}\n" in text
    for slug in pub["sensors"]:
        assert text.count(f'"{slug}"') == 1, slug


def test_card_name_does_not_repeat_the_maker(pub):
    for slug, c in _cards(pub).items():
        if c["maker"]:
            assert c["maker"].split()[0].lower() not in c["title"].lower() or slug.startswith("gi-"), slug


def test_card_tags_are_shutter_cameras_imu_in_that_order_and_hold_no_licence(pub):
    for slug, c in _cards(pub).items():
        tags = c["tags"]
        assert re.fullmatch(r"\d+ cameras", tags[-2]) and re.fullmatch(r"[\d.]+ k?Hz IMU", tags[-1]), slug
        assert len(tags) == 2 or (len(tags) == 3 and "shutter" in tags[0]), slug
        assert not any("CC BY" in t for t in tags), slug


def test_unknown_shutter_is_left_out_of_the_tags(pub):
    for slug, c in _cards(pub).items():
        known = pub["sensors"][slug]["header"]["key_specs"].get("shutter", {}).get("tag") != "not_published"
        assert any("shutter" in t for t in c["tags"]) == known, slug


# Live without a demo or hosted data, at the user's request (alg-avs111c 2026-11-06; cyperstereo 2026-11-11, which has a demo since): no permission to host the bag.
NO_DEMO_NOT_HOSTED = ("alg-avs111c", "cyperstereo")


def test_every_page_has_a_cited_photo_a_short_type_and_a_demo(pub):
    for slug, p in pub["sensors"].items():
        img = p["header"]["image"]
        assert len(p["header"]["type"]) <= 90 and ("demo" in p or slug in NO_DEMO_NOT_HOSTED), slug
        if img["kind"] == "photo":
            assert (DATA / "photos" / img["file"]).exists() and img["credit"] and img["alt"], slug


def test_every_page_reports_a_calibrated_fov(pub):
    assert all(p["header"]["key_specs"]["fov"].get("auto") == "fov" for p in pub["sensors"].values())


def test_looper_valve_and_reverb_link_examples_that_exist(pub):
    pages = pub["sensors"]
    examples = yaml.safe_load((DATA / "public_examples.yaml").read_text(encoding="utf-8"))["examples"]
    assert pages["looper-insight9"]["example"]["url"] == "/benchmark/examples/looper-insight9/"
    assert pages["hp-reverb-g2"]["example"]["url"] == pages["valve-index"]["example"]["url"] == "/benchmark/examples/monado/"
    assert "HP Reverb G2" in pages["valve-index"]["example"]["label"]  # the Index is not the Monado example's headset
    for slug, p in pages.items():
        if p.get("example"):
            assert p["example"]["url"].split("/")[-2] in examples, slug


def test_every_sensor_page_links_to_its_hosted_data(pub):
    for slug, p in pub["sensors"].items():
        html = dataset_rows(p, pub["data_url"])
        if slug in NO_DEMO_NOT_HOSTED:
            assert "Not hosted" in html and "__" not in html, slug
            continue
        assert f"calibench-vi/community/tree/main/{slug}/" in html and "__" not in html, slug
        if slug not in ("dibuli-prism-a4l", "hampo", "xq20"):
            assert "calibench-vi/datasets/tree/main/" in html, slug


def test_no_page_says_not_hosted_for_data_on_the_hub(pub):
    for s in ("xq20", "hampo", "dibuli-prism-a4l"):
        assert "not hosted" not in yaml.safe_dump(pub["sensors"][s]).lower(), s


def test_xq20_names_borme_and_tags_the_shutter_as_the_listings(pub):
    p = pub["sensors"]["xq20"]
    assert p["header"]["maker"]["name"] == "Borme" and p["header"]["maker"]["url"].startswith("https://www.alibaba.com/")
    assert p["header"]["key_specs"]["shutter"]["tag"] == "listing"
    assert not any(row[0] == "Shutter" and row[2] == "Unknown" for row in p["hardware"])
    assert not any("IMU to camera" in row[0] for row in p["hardware"])  # the solved td stands
    assert not any("Sync" in row[0] for row in p["hardware"])  # no maker sync claims on the page


def test_only_looper_thanks_anyone_and_it_passes_the_lint(pub):
    assert [k for k, p in pub["sensors"].items() if p.get("thanks")] == ["looper-insight9"]
    t = pub["sensors"]["looper-insight9"]["thanks"]
    assert [x["name"] for x in t["people"]] == ["Qinrui Yan", "Junjie Tang"] and "hand-held and robot-arm" in t["note"]
    assert public_problems(strip_urls(thanks_html(t))) == []  # a profile id in a link is not a device id


def test_looper_licence_is_scoped_to_hand_held(pub):
    p = pub["sensors"]["looper-insight9"]
    assert "CC BY-NC 4.0" not in p["chips"] and "Hand-held data CC BY-NC 4.0" in p["chips"]
    assert "not hosted" not in p["header"]["foot"] and "blurred except the board" in p["header"]["foot"]
    rows = dict(p["dataset"])
    assert rows["Robot-arm data"].startswith("__HUB:community/looper-insight9/data/__")
    # arm bags on the Hub were replaced with the unblurred frames (Hub a2a09ebc, 2026-11-07)
    assert "Normal frames" in rows["Robot-arm data"] and "blurred" not in rows["Robot-arm data"] and "CC BY-NC 4.0" in rows["Robot-arm data"]
    assert "__LINK__" in rows["Hand-held data"] and "CC BY-NC 4.0" in rows["Hand-held data"] and p["folder"] == "looper-insight9/"
    html = dataset_rows(p, "https://x")
    assert html.count("<a href") == 4 and "<td>Licence</td>" not in html and "<td>Hosted</td>" not in html
    assert "for the hand-held data, clip and figures" in html


def test_looper_limits_keep_the_two_sets_apart_and_clips_follow_the_tabs(pub):
    p = pub["sensors"]["looper-insight9"]
    limits = " ".join(p["limits"])
    for phrase in ("not pooled", "may not come from the same unit", "less well determined"):
        assert phrase in limits
    # no hand-held vs arm tables on the page for now (user, 2026-11-08), so no limits about them
    for phrase in ("repeatability rests", "between the two sets", "tables show"):
        assert phrase not in limits
    # first tab: the chessboard recording of our own unit (user, 2026-11-07), its clip from the copy blurred outside the board
    assert [x["from"] for x in p["demo"]["by_variant"]] == ["looper-insight9-chessboard_small", "looper-insight9-arm_small", "looper-insight9-arm_small"]
    assert "blurred" in p["demo"]["by_variant"][0]["note"] and "our own unit" in limits
    rows = dict(p["dataset"])
    # chessboard takes 01 to 04 hosted, blurred except the board (2026-11-07)
    assert rows["Chessboard data"].startswith("__HUB:community/looper-insight9/data/__") and "takes 01 to 04" in rows["Chessboard data"]
    assert "Everything except the board is blurred" in rows["Chessboard data"] and "CC BY-NC 4.0" in rows["Chessboard data"]
    text = strip_urls(yaml.safe_dump(p, allow_unicode=True))
    assert public_problems(text) == [] and "firmware" not in text.lower()
