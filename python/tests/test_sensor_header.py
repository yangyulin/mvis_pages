import copy

import pytest

import make_fixtures as F
from mvis_site import sensor_header as H
from mvis_site.sensor_parts import parts_for


def _fv(**kw):
    return {"h": 100.0, "v": 80.0, "h_ext": False, "v_ext": False, "reach": 60.0, "turn": 180.0, **kw}


def test_spec_row_is_calibrated_and_keeps_the_maker_value():
    maker = {"v": "120° × 72°", "tag": "maker", "src": "https://example.com"}
    row = H._auto({"auto": "fov", "also": maker}, {"fov": [_fv()]})
    assert row["v"] == "Calibrated 100° × 80°" and row["also"] == maker
    html = H._fov_row("fov", row)
    assert "Calibrated 100° × 80°" in html and "Measured" in html and "120° × 72°" in html and "Maker" in html


def test_spec_row_names_the_cameras_when_they_differ():
    row = H._auto({"auto": "fov", "cams": {"mono": 0, "colour": 1}}, {"fov": [_fv(), _fv(h=None, h_ext=True)]})
    assert row["v"] == "Calibrated mono 100° × 80°, colour past the fit × 80°"


def test_auto_baseline_and_plain_rows(variant):
    assert H._auto({"auto": "baseline"}, variant) == {"v": "62.0 mm"}
    one = dict(variant, run=dict(variant["run"], cams=variant["run"]["cams"][:1]))
    assert H._auto({"auto": "baseline"}, one) == {"v": "One camera in this run"}
    assert H._auto({"v": "x"}, variant) == {"v": "x"}
    assert H._fov_row("imu", {"v": "y", "also": {"v": "z"}}) == "y<span class=sd-tag>Measured</span>"


def test_tags():
    url = "https://www.example.com/listing"
    assert H._tag({"tag": "listing", "src": url}) == f'<a class=sd-tag href="{url}">Listing ↗</a>'
    assert H._tag({"tag": "supplier"}) == "<span class=sd-tag>Supplier&#x27;s sheet</span>"
    assert H._tag({"tag": "own words"}) == "<span class=sd-tag>own words</span>"


def test_listing_values_group_apart_from_the_sheet():
    p = {"header": {}, "hardware": [["Shutter", "Global", "Listing"], ["Weight", "180 g", "Supplier"]]}
    assert {g["title"]: [r["item"] for r in g["rows"]] for g in H.spec_groups(p)} == {"From the seller's listing": ["Shutter"], "From the supplier's sheet": ["Weight"]}


def test_every_source_tag_has_its_group_title():
    tags = ["Maker", "Supplier", "Listing", "Dataset", "Catalog", "Measured", "Owner"]
    p = {"header": {}, "hardware": [[t.lower(), "1", t] for t in tags]}
    assert [g["title"] for g in H.spec_groups(p)] == ["Published by the maker", "From the supplier's sheet", "From the seller's listing",
                                                      "From the dataset", "From our catalog", "Measured in these recordings", "Maker"]


def test_unknown_rows_gather_under_not_published():
    p = {"header": {}, "hardware": [["Weight", "Not published", "Unknown"], ["Mount", "Clip", "Unknown"]], "_fov_spec": {"item": "FoV", "v": "x"}}
    assert H.spec_groups(p) == [{"title": "Measured in these recordings", "rows": [{"item": "FoV", "v": "x"}]},
                                {"title": "Not published", "rows": [{"item": "Open", "v": "Weight, Mount: Clip"}]}]


def test_hand_written_groups_get_the_measured_fov():
    p = {"header": {"groups": [{"title": "A", "rows": []}]}, "_fov_spec": {"item": "FoV", "v": "x"}}
    assert [g["title"] for g in H.spec_groups(p)] == ["A", "Measured in these recordings"]
    assert H.spec_groups({"header": {"groups": [{"title": "A", "rows": []}]}}) == [{"title": "A", "rows": []}]


def test_specs_html_links_sources_and_folds_the_contact(variant):
    p = F.pub_entry("photo")
    p["header"]["groups"] = [{"title": "G", "rows": [{"item": "a", "v": "1", "url": "https://x/a"}, {"item": "b", "v": "2", "src": "https://x/b"}, {"item": "c", "v": "3"}]}]
    html = H.specs_html(p, variant)
    assert '<a href="https://x/a">1</a>' in html and 'aria-label="Source">↗' in html and 'id="sales-contact"' in html and "Checked once." in html
    del p["header"]["contact"], p["header"]["spec_note"]
    assert "<p class=note>" not in H.specs_html(p, variant)


def test_thanks_strip_names_each_person_with_role_and_the_reason():
    t = {"people": [{"name": "A <B>", "role": "Head & founder"}, {"name": "C D", "role": "Lab", "url": "https://example.org/c"}], "note": "They recorded it."}
    html = H.thanks_html(t)
    assert "With thanks" in html and "They recorded it." in html and "A &lt;B&gt;" in html and "Head &amp; founder" in html
    assert html.count("<a ") == 1 and 'href="https://example.org/c"' in html
    assert H.thanks_html(None) == ""


def _header(variant, p):
    p = dict(p, _runs=1, _fov_spec=H.fov_spec(variant))
    return H.header_html("rig", p, p["header"], variant)


def test_header_with_photo_buttons_and_thanks(variant):
    html = _header(variant, F.pub_entry("photo"))
    assert '<img src="/media/sensors/rig/rig.jpg"' in html and "sd-maker" in html and "Product page ↗" in html and "Docs ↗" in html
    assert html.endswith("</aside></div>") and "All specs (" in html


def test_header_refuses_an_image_that_is_not_a_photo(variant):
    p = F.pub_entry("photo")
    p["header"]["image"] = {"kind": "drawing", "file": "rig.jpg"}
    with pytest.raises(SystemExit, match="header image must be a photo"):
        _header(variant, p)


def test_header_credit_without_link_and_fov_footnote(variant):
    p = F.pub_entry("photo")
    del p["header"]["image"]["url"]
    variant["fov"][0] = {**variant["fov"][0], "h_ext": True}
    html = _header(variant, p)
    assert "<figcaption>Maker Co</figcaption>" in html and H.e(H.FOV_FOOT) in html


def test_header_refuses_missing_rows_unsourced_tags_and_a_long_type(variant):
    p = F.pub_entry("photo")
    del p["header"]["key_specs"]["output"]
    with pytest.raises(SystemExit, match="needs \\['output'\\]"):
        _header(variant, p)
    p = F.pub_entry("photo")
    p["header"]["key_specs"]["fov"]["also"]["src"] = "http://insecure"
    with pytest.raises(SystemExit, match="fov has no listing source"):
        _header(variant, p)
    p = F.pub_entry("photo")
    p["header"]["type"] = "x" * 91
    with pytest.raises(SystemExit, match="type line is 91"):
        _header(variant, p)


def test_proc_preview_draws_board_and_path(variant):
    svg = H.proc_preview(variant)
    assert svg.startswith('<svg viewBox="0 0 400 220"') and "<polygon" in svg and "nan" not in svg
    variant["process"]["data"] = [t for t in variant["process"]["data"] if t["name"] != "Board Outline"]
    assert '<polygon points=""' in H.proc_preview(variant)


def test_decode_reads_both_number_forms():
    assert list(H._decode([1, 2])) == [1.0, 2.0]
    assert list(H._decode(F.b64f([3.5]))) == [3.5]


def test_header_parts_rewrites_the_page_for_a_datasheet(variant):
    p = F.pub_entry("photo")
    vs = [variant, dict(variant, label="Arm")]
    parts = parts_for("rig", p, {"board": {"rows": 2, "cols": 2, "tag_mm": 30, "spacing": 0.3}}, vs, [], "https://d", "/m", {str(i): ["1" * 6] * 6 for i in range(4)})
    lead = parts["lead"]
    out = H.header_parts("rig", p, vs, copy.deepcopy(parts))
    assert p["_runs"] == 2 and p["_fov_spec"]["item"] == "Calibrated field of view"
    assert {"header", "specifications", "rig", "detail"} <= set(out)
    assert out["glance"].startswith("<div class=vtabs") and "<p class=sd-note>One recording.</p>" in out["glance"]
    assert "▶︎ Play" in out["process"] and "Explore in 3D" in out["process"]
    assert out["detail"].count("<details class=fold") == 4 and lead == out["lead"]
    one = H.header_parts("rig", F.pub_entry("photo"), vs[:1], parts_for("rig", F.pub_entry("photo"), {"board": {"rows": 2, "cols": 2, "tag_mm": 30, "spacing": 0.3}},
                                                                         vs[:1], [], "https://d", "/m", {str(i): ["1" * 6] * 6 for i in range(4)}))
    assert one["glance"].startswith("<p>")
