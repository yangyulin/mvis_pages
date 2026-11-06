import re

import numpy as np

import make_fixtures as F
from mvis_site import assets
from mvis_site import markup as m


def _fv(**kw):
    return {"h": 100.0, "v": 80.0, "h_ext": False, "v_ext": False, "reach": 60.0, "turn": 180.0, **kw}


def test_num_uses_real_minus():
    assert m.num(-1.5, 1) == "−1.5" and m.num(None) == "not stored" and m.num(2, 1, True) == "+2.0"


def test_vec_and_chip():
    assert m.vec([1, -2], 1) == "[+1.0, −2.0]"
    assert m.chip("a<b", "ok") == '<span class="chip ok">a&lt;b</span>'


def test_fov_pair_marks_extrapolated_axes():
    assert m.fov_pair(_fv()) == "100° × 80°"
    assert m.fov_pair(_fv(h_ext=True)) == "~100° × 80°"
    assert m.fov_pair(_fv(h=None)) == "past the fit × 80°"


def test_fov_pair_with_no_axis_says_it_once():
    assert m.fov_pair(_fv(h=None, v=None, h_ext=True, v_ext=True)) == "past the fit"
    assert m.fov_text(0, _fv(h=None, v=None)).startswith("cam0: past the fit, corners reach")


def test_fov_text_without_corner_data():
    assert m.fov_text(1, _fv(reach=None)) == "cam1: 100° × 80°, no corner data"


def test_lens_svg_draws_a_curve_per_camera(variant):
    svg = m.lens_svg(variant)
    assert svg.count("<polyline") == 2 and 'class="c1"' in svg
    pts = re.findall(r'<polyline class="c0" points="([^"]*)"', svg)[0].split()
    assert len(pts) == 31 and pts[0] == "54.0,220.0"  # every 3° from 0 to 90


def test_lens_svg_leaves_out_points_past_the_plot(variant):
    for c in variant["run"]["cams"]:
        c["intr"] = c["intr"][:4] + [2.0, 0.0, 0.0, 0.0]  # radius grows past r_max well before 90°
    pts = re.findall(r'<polyline class="c0" points="([^"]*)"', m.lens_svg(variant))[0].split()
    assert 1 < len(pts) < 31


def test_lens_svg_eucm_axis_runs_to_2(variant):
    variant["run"]["cams"] = [F.cam("cam0", F.EUCM, [0, 0, 0], [0, 0, 0])]
    assert ">2.0</text>" in m.lens_svg(variant)


def test_board_drawing_is_the_real_grid():
    svg = m.board_svg({"rows": 6, "cols": 6, "tag_mm": 35.2, "spacing": 0.3}, assets.apriltag())
    assert "AprilGrid 6 × 6, 264 × 264 mm" in svg
    assert svg.count("<path") == 2 and len(svg) < 60000


def test_board_drawing_reads_tag_ids_from_the_bottom_left():
    tags = {str(i): ["1" * 6] * 6 for i in range(4)}
    tags["2"] = ["0" + "1" * 5] + ["1" * 6] * 5  # one white bit on tag 2, bottom-left in a 2 x 2 grid
    svg = m.board_svg({"rows": 2, "cols": 2, "tag_mm": 10, "spacing": 0.5}, tags)
    white = re.search(r'<path fill="#fff" d="([^"]*)"', svg).group(1)
    assert white == "M2.00 2.00h1.00v1.00h-1.00z"  # top row in SVG is the board's top row: tag 2


def test_imu_bars_clamp_at_8_percent():
    html = m.imu_bars({"Dw_diag": [1.2, 0.99, 1.0], "Da_diag": None})
    assert html.count("class=bar>") == 4 and "width:50.00%" in html and "left:43.75%" in html


def test_timing_svg_scales_to_the_largest_offset():
    html = m.timing_svg({"cams": [{"name": "cam0", "td_ms": 12.0}], "t_ga_ms": -3.0})
    assert "+20 ms" in html and "−3.00" in html and 'text-anchor=end' in html


def test_series_tables_keep_each_label_and_never_pool():
    runs = lambda t: [{"t_ga_ms": t, "cams": [{"name": "cam0", "p_CinI_mm": [1, 2, 3], "td_ms": 1.0}]}] * 2
    html = m.series_tables([{"label": "hand-held", "runs": runs(-5.25)}, {"label": "arm", "runs": runs(-1.75)}])
    hand, arm = html.split("Across arm")
    assert "Across hand-held" in hand and "5.25" in hand and "1.75" not in hand
    assert "1.75" in arm and "5.25" not in arm
    assert m.series_tables([]) == ""


def test_tiles_prefer_the_median_and_handle_one_camera(variant):
    r = variant["run"]
    assert "Reprojection median" in m.tiles(r) and "mm</small>" in m.tiles(r)
    one = dict(r, cams=r["cams"][:1], reproj_rms_px=0.4)
    del one["reproj_median_px"]
    html = m.tiles(one)
    assert "Reprojection RMS" in html and "<b>–</b>" in html


def test_each_hides_all_but_the_first_tab():
    html = m.each({"variants": ["a", "b"]}, lambda v, i: v)
    assert html == '<div class=v data-v="0">a</div><div class=v data-v="1" hidden>b</div>'
    assert m.each({"variants": ["a"]}, lambda v, i: v) == '<div class=v data-v="0">a</div>'


def test_proc_html(variant):
    html = m.proc_html(variant, 3)
    assert 'id="proc3"' in html and "<select" in html and "max=11" in html
    one = dict(variant, process=dict(variant["process"], spec=dict(variant["process"]["spec"], views=variant["process"]["spec"]["views"][:1])))
    assert "<select" not in m.proc_html(one, 0)
    assert "Needs a new solve" in m.proc_html(dict(variant, process=None), 0)


def test_params_names():
    assert m.PARAMS[8][4] == "k1" and m.PARAMS[6][4] == "alpha"


def test_ms_is_median_and_sample_sd():
    assert m._ms([1.0, 2.0, 3.0]) == "+2.00 ± 1.00"
    assert np.isclose(float(m._ms([1.0, 3.0], 1).split(" ± ")[1]), np.std([1, 3], ddof=1), atol=0.05)


def test_reproj_prefers_the_median():
    assert m.reproj({"reproj_median_px": 0.4, "reproj_rms_px": 0.9}) == ("median", 0.4)
    assert m.reproj({"reproj_median_px": None, "reproj_rms_px": 0.9}) == ("RMS", 0.9)
