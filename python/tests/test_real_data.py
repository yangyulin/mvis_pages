"""Checks on the real runs. Every path comes from the environment; skipped without it.

  MVIS_SENSORS_CONFIG=<mira>/scripts/mvis/huggingface/community_sensors/data/sensors.yaml MVIS_MEDIA=<clips dir> \
  PYTHONNOUSERSITE=1 python3 -m pytest -q -m real_data
"""
import numpy as np
import pytest

from conftest import env_path
from mvis_site import DATA
from mvis_site import export_sensors as X
from mvis_site.results import load_all_series, load_variant
from mvis_site.sensor_header import fov_spec, header_html
from mvis_site.sensor_rig import rig_drawing, rig_table

pytestmark = pytest.mark.real_data


@pytest.fixture(scope="module")
def collected():
    from mvis_site.results import solve_config
    import yaml
    cfg = solve_config(yaml.safe_load(env_path("MVIS_SENSORS_CONFIG").read_text()))
    return X.collect(X.public_sensors(), cfg), cfg


def _vs(collected):
    for slug, c in collected[0].items():
        for v in c["variants"]:
            yield slug, v


def test_rig_drawing_shows_solved_numbers_for_every_run(collected):
    for slug, v in _vs(collected):
        svg = rig_drawing(v)
        assert "From above" in svg and "From the front" in svg, slug
        assert svg.count('fill-opacity=".12"') == len(v["run"]["cams"]), slug
        for c in v["run"]["cams"]:
            assert f'<td>{float(np.linalg.norm(c["p_CinI_mm"])):.1f}</td>' in rig_table(v), slug


def test_a_fan_past_the_fit_is_dashed_and_explained(collected):
    seen = 0
    for slug, v in _vs(collected):
        svg = rig_drawing(v)
        past = any(f["h"] is None or f["v"] is None for f in v["fov"])
        seen += past
        assert ("past the fit" in svg) == past and ("stroke-dasharray" in svg) == past, slug
    assert seen >= 2


def test_thanks_sit_inside_the_looper_header_only(collected):
    pub = X.public_sensors()["sensors"]
    drawn = {}
    for slug, c in collected[0].items():
        v = c["variants"][0]
        p = dict(pub[slug], _runs=1, _fov_spec=fov_spec(v))
        drawn[slug] = header_html(slug, p, p["header"], v)
    assert [s for s, h in drawn.items() if "sd-thanks" in h] == ["looper-insight9"]
    assert drawn["looper-insight9"].endswith("</aside></div>")


def test_hp_has_four_cameras_and_t265_no_fov_value(collected):
    hp = collected[0]["hp-reverb-g2"]["variants"][0]
    assert [c["name"] for c in hp["run"]["cams"]] == ["cam0", "cam1", "cam2", "cam3"] and len(hp["fov"]) == len(hp["sizes"]) == 4
    assert all(f["h"] is None and f["v"] is None and f["reach"] is not None for f in collected[0]["intel-t265"]["variants"][0]["fov"])


def test_looper_tabs_and_sets(collected):
    c = collected[0]["looper-insight9"]
    assert [v["label"] for v in c["variants"]] == ["Hand-held 1", "Robot arm 1", "Robot arm 2"]
    for v in c["variants"]:
        assert [x["name"] for x in v["run"]["cams"]] == ["cam0", "cam1", "cam2"] and v["readout_ms"][2] > 25
    assert [(s["label"], len(s["runs"])) for s in c["series"]] == [("10 hand-held recordings", 10), ("2 robot-arm recordings", 2)]


def test_looper_limits_match_the_results(collected):
    hand, arm = collected[0]["looper-insight9"]["series"]
    mean = lambda s, f: float(np.mean([f(r) for r in s["runs"]]))
    for axis in (1, 2):
        assert 2.5 < abs(mean(arm, lambda r: r["cams"][0]["p_CinI_mm"][axis]) - mean(hand, lambda r: r["cams"][0]["p_CinI_mm"][axis])) < 4
    for cam in range(3):
        gaps = [np.median([r["cams"][cam]["p_CinI_mm"][k] for r in arm["runs"]]) - np.median([r["cams"][cam]["p_CinI_mm"][k] for r in hand["runs"]]) for k in range(3)]
        assert 4.5 <= np.linalg.norm(gaps) <= 5
    assert 1.5 < abs(mean(arm, lambda r: r["cams"][2]["td_ms"]) - mean(hand, lambda r: r["cams"][2]["td_ms"])) < 2.1


def test_the_real_export_passes_the_lint_and_writes(collected, tmp_path):
    plan = X.render(X.public_sensors(), collected[0], env_path("MVIS_MEDIA"), DATA / "photos")
    assert plan.problems == []
    X.write(tmp_path, plan)
    assert len(list((tmp_path / "site/src/data/sensors").glob("*.json"))) == len(plan.slugs)


def test_fixture_reports_parse_like_real_ones(collected, tmp_path):
    """make_fixtures writes reports in the same shape the real ones have."""
    import make_fixtures as F
    from mvis_site.results import extract_process
    real = next(v["process"] for _, v in _vs(collected))
    fake = extract_process(F.write_run(tmp_path / "r") / "cam_imu_report.html")
    assert set(real) == set(fake) and {"xyz", "views"} <= set(real["spec"]) & set(fake["spec"])
    assert set(fake["spec"]["views"][0]) <= set(real["spec"]["views"][0])
