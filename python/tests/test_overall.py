"""Overall tab (mvis_site.overall): tier A pair rules, absolute tiers, presets, the leave-one-out badge, public text."""
import copy
import json
from pathlib import Path

import pytest

from mvis_site import overall

RUBRIC = overall.load_rubric()


def _pair(a, b, d):
    return {"a": a, "b": b, "decision": d}


def _rep(fams):
    return {"batch": "2026-01-01a", "results_commit": "0" * 40,
            "datasets": [{"id": "ds", "families": [{"id": fid, "mode": mode, "cells": cells} for fid, mode, cells in fams]}]}


M = RUBRIC["measured"]
TOOLS = tuple(RUBRIC["tools"])
A1 = next(a for a in M["aspects"] if a["id"] == "A1")
A2 = next(a for a in M["aspects"] if a["id"] == "A2")


def test_pairs_average_groups_then_families():
    cells = {"focal_pp": {"caveats": [], "pairs": [_pair("MVIS", "Kalibr", "b"), _pair("Kalibr", "Basalt", "a")]},
             "distortion": {"caveats": [], "pairs": [_pair("MVIS", "Kalibr", "tie")]}}
    r = overall.measured_aspect(A1, _rep([("T4", "cam", cells)]), M, TOOLS)
    mk = next(p for p in r["pairs"] if p["b"] == "Kalibr")
    assert mk["points"] == {"MVIS": 0.25, "Kalibr": 0.75} and mk["lead"] == "Kalibr"
    assert mk["families"][0]["href"] == "#rp-T4-focal_pp"
    assert r["values"]["Kalibr"] == pytest.approx(0.875)


def test_caveat_drops_its_tool_and_count_despite_keeps_the_pair():
    snapped = {"focal_pp": {"caveats": ["basalt_snapped"], "pairs": [_pair("MVIS", "Kalibr", "a"), _pair("MVIS", "Basalt", "a")]}}
    r = overall.measured_aspect(A1, _rep([("T1", "cam", snapped)]), M, TOOLS)
    assert [(p["a"], p["b"]) for p in r["pairs"]] == [("MVIS", "Kalibr")]
    settings = {"lever": {"caveats": ["settings_differ"], "pairs": [_pair("MVIS", "Kalibr", "a")]}}
    assert overall.measured_aspect(A2, _rep([("T8", "cam+imu", settings)]), M, TOOLS)["pairs"] == []
    assert overall.measured_aspect(A2, _rep([("T6", "cam+imu", settings)]), M, TOOLS)["pairs"]   # counted despite


def test_cycle_mode_and_out_of_scope_give_no_points():
    cyc = {"lever": {"caveats": [], "pairs": [_pair("MVIS", "Kalibr", "a"), _pair("Kalibr", "Basalt", "a"), _pair("MVIS", "Basalt", "b")]}}
    assert overall.measured_aspect(A2, _rep([("T11", "cam+imu", cyc)]), M, TOOLS)["pairs"] == []
    ok = {"lever": {"caveats": [], "pairs": [_pair("MVIS", "Kalibr", "a")]}}
    assert overall.measured_aspect(A2, _rep([("T7", "cam+imu", ok)]), M, TOOLS)["pairs"] == []
    assert overall.measured_aspect(A1, _rep([("T11", "cam+imu", {"focal_pp": ok["lever"]})]), M, TOOLS)["pairs"] == []


def test_h2h_line_names_the_shape():
    P = lambda a, b, lead: {"a": a, "b": b, "lead": lead, "families": [{"id": "T3"}]}
    line = overall.h2h_line("X", [P("MVIS", "Kalibr", "MVIS"), P("MVIS", "Basalt", None), P("Kalibr", "Basalt", "Basalt")], TOOLS)
    assert line == "X: MVIS and Basalt repeat about equally well; both repeat better than Kalibr."
    line = overall.h2h_line("X", [P("MVIS", "Kalibr", "MVIS"), P("MVIS", "Basalt", None)], TOOLS)
    assert line == "X: MVIS repeats better than Kalibr (T3); about equal: MVIS and Basalt (T3)."


def test_sub_checks_and_sub_presets():
    c4 = overall._abs_aspect(RUBRIC, "C4")
    assert overall.aspect_points(c4, "Kalibr") == 0.25
    assert overall.aspect_points(c4, "Kalibr", keep={"a", "b"}) == 0.5


def _full_rep():
    focal = {"caveats": [], "pairs": [_pair("MVIS", "Kalibr", "a"), _pair("MVIS", "Basalt", "tie"), _pair("Kalibr", "Basalt", "b")]}
    lever = {"caveats": [], "pairs": [_pair("MVIS", "Kalibr", "a"), _pair("MVIS", "Basalt", "tie"), _pair("Kalibr", "Basalt", "tie")]}
    return _rep([("T3", "cam", {"focal_pp": focal}), ("T11", "cam+imu", {"lever": lever})])


def test_build_tiers_total_badge_and_presets():
    o = overall.build(RUBRIC, _full_rep())
    tiers = {t["id"]: t for t in o["tiers"]}
    assert tiers["A"]["coverage"] == "3 of 6 aspects have points"
    assert tiers["C"]["values"] == {"MVIS": 0.68, "Kalibr": 0.51, "Basalt": 0.43}
    assert tiers["U"]["values"] == {"MVIS": 0.67, "Kalibr": 0.79, "Basalt": 0.54}
    assert o["total"]["n_aspects"] == 18
    eq = next(p for p in o["presets"] if p["id"] == "equal")
    assert eq["values"] == o["total"]["values"]
    assert o["badge"].startswith(f"Equal tiers: {o['total']['leader']} first in ")
    a4 = next(a for a in tiers["A"]["aspects"] if a["id"] == "A4")
    assert all(c["points"] is None and c["na"] == "not measured" for c in a4["cells"].values())
    c5 = next(a for a in tiers["C"]["aspects"] if a["id"] == "C5")
    assert c5["cells"]["MVIS"]["subs"][4]["label"].endswith("(Designed into MVIS)")


def test_no_home_preset_drops_home_rows_and_sub_checks():
    o = overall.build(RUBRIC, _full_rep())
    nh = next(p for p in o["presets"] if p["id"] == "no_home")
    # left: C1, C2, C5 a-c, C6 a b d, C7 a b
    exp_k = (1 + 1 + (1 + 0.5 + 0) / 3 + 1 + 1) / 5
    assert nh["values"]["Kalibr"] == round(exp_k, 2)


def test_export_refuses_rating_words(tmp_path):
    rep = tmp_path / "rep.json"
    rep.write_text(json.dumps(_full_rep()))
    out = overall.export(rep, tmp_path / "overall.json")
    text = out.read_text()
    assert "score" not in text.lower().replace("scoring", "")
    bad = copy.deepcopy(RUBRIC)
    bad["not_counted"].append("Kalibr has the best docs.")
    rub = tmp_path / "rub.yaml"
    import yaml
    rub.write_text(yaml.safe_dump(bad))
    with pytest.raises(SystemExit, match="rating"):
        overall.export(rep, tmp_path / "x.json", rub)


def test_challenge_template_lists_every_rubric_aspect():
    import yaml
    tpl = Path(__file__).resolve().parents[2] / ".github/ISSUE_TEMPLATE/rubric-challenge.yml"
    form = yaml.safe_load(tpl.read_text())
    aspect = next(b for b in form["body"] if b.get("id") == "aspect")["attributes"]["options"]
    tool = next(b for b in form["body"] if b.get("id") == "tool")["attributes"]["options"]
    rows = [f"{a['id']} {a['label']}" for a in RUBRIC["measured"]["aspects"]]
    rows += [f"{a['id']} {a['label']}" for t in RUBRIC["tiers"] for a in t["aspects"]]
    assert [o for o in aspect if o[:1] in "ACU" and o[1:2].isdigit()] == rows
    assert tool[:3] == RUBRIC["tools"]
    assert RUBRIC["challenge_url"].endswith("template=" + tpl.name)
