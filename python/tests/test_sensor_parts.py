import re

import make_fixtures as F
from mvis_site import assets
from mvis_site import sensor_parts as S


def test_demo_keys_share_a_file_between_tabs():
    assert S.demo_keys({"by_variant": [{"from": "a"}, {"from": "b"}, {"from": "b"}]}) == [0, 1, 1]


def test_only_the_first_tab_clip_autoplays():
    html = S.demo_block({"by_variant": [{"from": "a", "note": "A"}, {"from": "b", "note": "B"}, {"from": "b", "note": "C"}]}, "/m")
    assert html.count("<video") == 3 and html.count(" autoplay") == 1
    assert html.index(" autoplay") < html.index('data-v="1"')
    assert re.findall(r'src="([^"]+)"', html) == ["/m/demo0.mp4", "/m/demo1.mp4", "/m/demo1.mp4"]
    assert re.findall(r'data-v="(\d)"( hidden)?', html) == [("0", ""), ("1", " hidden"), ("2", " hidden")]


def test_single_clip_page_html_is_unchanged():
    assert S.demo_block({"from": "x", "note": "N"}, "/m") == (
        '<figure class=demo><video src="/m/demo.mp4" poster="/m/demo.jpg" autoplay muted loop playsinline controls preload=metadata></video>'
        '<figcaption>N</figcaption></figure>')
    assert S.demo_block(None, "/m").startswith('<div class="demo empty">')
    assert 'src="/old/demo.mp4"' in S.demo_block({"existing": "/old/demo", "note": "N"}, "/m")


def test_hub_rows_become_links_to_the_right_repo():
    html = S.dataset_rows({"dataset": [["Hosted", "__HUB:community/xq20/__"], ["Copy", "__HUB:datasets/converted/tum_mic/__. CC BY 4.0"]]}, "https://h")
    assert '<a href="https://huggingface.co/datasets/calibench-vi/community/tree/main/xq20/">Calibench community, xq20/</a> (access by automatic approval)' in html
    assert '<a href="https://huggingface.co/datasets/calibench-vi/datasets/tree/main/converted/tum_mic/">Calibench, converted/tum_mic/</a> (access by automatic approval). CC BY 4.0' in html
    assert "__HUB" not in html


def test_dataset_rows_on_a_plain_folder_page_are_unchanged():
    assert S.dataset_rows({"dataset": [["A", "B"]], "folder": "x/"}, "https://d") == (
        "<tr><td>A</td><td>B</td></tr><tr><td>Licence</td><td>CC BY-NC 4.0, for the data and for this page&#x27;s clip and figures; commercial use by request</td></tr>"
        '<tr><td>Hosted</td><td><a href="https://d/x/">Calibench, x/</a> (access by automatic approval)</td></tr>')


def test_a_page_that_places_its_own_link_scopes_its_own_licence():
    html = S.dataset_rows({"dataset": [["Hand-held data", "__LINK__, CC BY-NC 4.0"]], "folder": "x/"}, "https://d")
    assert "<td>Licence</td>" not in html and '<a href="https://d/x/">' in html


def test_dataset_rows_with_an_outside_link_or_none():
    html = S.dataset_rows({"dataset": [["A", "B"]], "data_link": {"url": "https://e/d", "label": "Elsewhere"}}, "https://d")
    assert html.endswith('<tr><td>Data</td><td><a href="https://e/d">Elsewhere</a></td></tr>')
    assert S.dataset_rows({"dataset": [["A", "B"]]}, "https://d") == "<tr><td>A</td><td>B</td></tr>"


def test_hosted_row_says_access_is_automatic_not_on_request():
    html = S.dataset_rows({"dataset": [], "folder": "x/"}, "https://h")
    assert "automatic approval" in html and "on request" not in html.replace("commercial use by request", "")


def test_example_row_links_the_example_and_is_empty_without_one():
    assert '<a href="/benchmark/examples/monado/">Monado</a>' in S.example_row({"example": {"url": "/benchmark/examples/monado/", "label": "Monado"}})
    assert S.example_row({}) == ""


def test_public_results_have_no_reference_column(variant):
    variant["readout_ms"] = [26.0, 0.0]
    html = S.public_results(variant)
    assert "<th>MVIS</th></tr>" in html and html.count("Readout ms") == 1 and "k1" in html
    assert "<td>Readout ms</td><td>+26.00</td>" in html


def test_public_results_unknown_model_names_parameters_by_index(variant):
    variant["run"]["cams"] = [F.cam("cam0", [300, 300, 320, 240, 0.1], [0, 0, 0], [0, 0, 0])]
    variant["readout_ms"] = [0.0]
    assert "<td>p4</td>" in S.public_results(variant)


def test_rig_json_never_carries_a_reference(variant):
    j = S.rig_json(variant)
    assert j["ref"] is None and j["cams"][0]["fov"]["draw_h"] == variant["fov"][0]["h"] and j["label"] == "Take 0123"


def test_parts_for_both_runs_with_tabs_and_sha(variant):
    p = F.pub_entry("old")
    p["sha"] = "f" * 64
    p["checked"] = "2026-01-02"
    parts = S.parts_for("rig", p, {"board": {"rows": 2, "cols": 2, "tag_mm": 30, "spacing": 0.3}}, [variant, dict(variant, label="Two")], [],
                        "https://d", "/media/sensors/rig", assets.apriltag())
    assert set(parts) == {k for _, k in S.PARTS} | {"lead"}
    assert "vtabs" in parts["lead"] and 'src="/media/sensors/rig/old.jpg"' in parts["lead"]
    assert f"<code>{'f' * 64}</code>" in parts["run"] and "checked 2026-01-02" in parts["hardware"] and "Old Co" in parts["hardware"]
    assert "AprilGrid 2 × 2" in parts["dataset"] and "Worked example" in parts["dataset"]


def test_parts_for_one_run_without_extras(variant):
    p = F.pub_entry("photo")
    del p["demo"]
    parts = S.parts_for("rig", p, {"board": {"rows": 2, "cols": 2, "tag_mm": 30, "spacing": 0.3}}, [variant], [], "https://d", "/m", assets.apriltag())
    assert "vtabs" not in parts["lead"] and "sensorimg" not in parts["lead"] and "sha256" not in parts["run"]
    assert "No video on this page" in parts["glance"] and "<p class=note>" not in parts["hardware"]


def test_shared_section_builders():
    assert S.map_panel() == "<div class=panel><div class=picks id=picks></div><div id=info></div></div></div>"
    assert S.map_panel("<label>x</label>") == "<div class=panel><div class=picks id=picks></div><label>x</label><div id=info></div></div></div>"
    assert S.hardware_table("<tr></tr>") == ("<div class=scroll><table><thead><tr><th>Item</th><th>Value</th><th>Source</th></tr></thead>"
                                            "<tbody><tr></tr></tbody></table></div>")
    html = S.clip("a&b.mp4", "p.jpg", "N <1>", autoplay=False)
    assert 'src="a&amp;b.mp4" poster="p.jpg" muted' in html and "<figcaption>N &lt;1&gt;</figcaption>" in html


def test_process_section_puts_the_note_after_the_lead(variant):
    assert S.process_section("Note.", [variant]).startswith(f"<p>{S.PROCESS_LEAD} Note.</p><div class=v data-v=\"0\">")


def test_imu_section_pinned_says_so():
    from mvis_site.sensor_parts import imu_section
    run = {"imu_model": "calyx", "Dw_diag": [1.0, 1.0, 1.0], "Da_diag": [1.0, 1.0, 1.0], "t_ga_ms": -1.0, "t_ga_sigma_ms": 0.5}
    html = imu_section([{"label": "Unit A", "run": run}])
    assert "pinned the IMU intrinsics at identity" in html and "Gyro scale" not in html
    run_free = dict(run, Dw_diag=[1.002, 1.0, 1.0])
    html = imu_section([{"label": "Unit A", "run": run_free}])
    assert "IMU model: calyx" in html and "Gyro scale" in html


def test_imu_and_timing_explain_their_terms():
    from mvis_site.sensor_parts import imu_section, timing_section
    run = {"imu_model": "calyx", "Dw_diag": [1.002, 1.0, 1.0], "Da_diag": [1.0, 1.0, 1.0], "t_ga_ms": -1.0, "t_ga_sigma_ms": 0.5,
           "cams": [{"name": "cam0", "td_ms": 2.0}]}
    assert "<code>t_ga</code>, the time offset between the gyroscope and accelerometer channels: −1.00 ± 0.50 ms." in imu_section([{"label": "A", "run": run}])
    assert timing_section([{"label": "A", "run": run}]).startswith("<p>The time offsets, to scale. td is the camera–IMU time offset, with t_imu = t_cam + td.</p>")
