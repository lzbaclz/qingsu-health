#!/usr/bin/env python3
"""BP / 视频用截图：造几条停在特定步骤的演示记录 → 本机 Chrome 无头截图 → 裁切。

前提：后端（:8000，已 make seed）与前端（:5173）在运行；本机装有 Google Chrome。
用法：python3 docs/assets/make_screenshots.py（需要 Pillow；后端虚拟环境里没有，用系统/conda 的 python3）
输出：docs/assets/screenshots/*.png（原图）与 docs/assets/screenshots/crops/*.png（BP 用）。
说明：Chrome 无头窗口最小宽度约 500px，手机页按 500px 宽截（等效大屏手机）。
"""
from __future__ import annotations

import json
import os
import pathlib
import signal
import subprocess
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "assets" / "screenshots"
API, WEB = "http://localhost:8000/api", "http://localhost:5173"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ELIG = {"adult": True, "not_pregnant": True}  # 开始页的适用范围确认（患者端接口必须带）


def post(path: str, body: dict) -> dict:
    r = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(r))


def get(path: str) -> dict:
    return json.load(urllib.request.urlopen(API + path))


def fixtures() -> dict:
    out = {}
    e = post("/patient/encounters", {"patient_code": "P-0101", "eligibility": ELIG})["id"]
    post(f"/patient/encounters/{e}/body-map", {"marks": [{"region_id": "lower_back_right", "kind": "primary"}, {"region_id": "buttock_right", "kind": "radiation"}]})
    post(f"/patient/encounters/{e}/text", {"text": "前两天搬花盆闪了腰，右边屁股到大腿后面都串着疼，腿不麻，也没发烧。"})
    get(f"/patient/encounters/{e}/next-question")
    out["verify"] = e
    e2 = post("/patient/encounters", {"patient_code": "P-0102", "eligibility": ELIG})["id"]
    post(f"/patient/encounters/{e2}/body-map", {"marks": [{"region_id": "lower_back_center", "kind": "primary"}]})
    post(f"/patient/encounters/{e2}/text", {"text": "腰痛两个多月了，最近越来越重，这两天小便憋不住。"})
    q = get(f"/patient/encounters/{e2}/next-question")["question"]
    post(f"/patient/encounters/{e2}/answer", {"question_id": q["question_id"], "value": {k: "confirm" for k in q["fact_keys"]}})
    out["urgent"] = e2
    e3 = post("/patient/encounters", {"patient_code": "P-0103", "eligibility": ELIG})["id"]
    post(f"/patient/encounters/{e3}/body-map", {"marks": [{"region_id": "lower_back_left", "kind": "primary"}]})
    post(f"/patient/encounters/{e3}/text", {"text": "前两天搬东西后左边腰酸，坐久了更明显，躺着好一些，腿不麻。"})
    ans = {"q_bladder_bowel": "no", "q_saddle": "no", "q_leg_weakness": "no", "q_fever": "no", "q_trauma": "no",
           "q_onset_mode": "sudden", "q_radiation_present": "no", "q_severity_now": 4, "q_function_impact": "mild"}
    q = get(f"/patient/encounters/{e3}/next-question")["question"]
    while q:
        if q["kind"] == "verification":
            body = {"question_id": q["question_id"], "value": {k: "confirm" for k in q["fact_keys"]}}
        elif q["question_id"] in ans:
            body = {"question_id": q["question_id"], "value": ans[q["question_id"]]}
        else:
            body = {"question_id": q["question_id"], "unknown": True}
        q = post(f"/patient/encounters/{e3}/answer", body)["next"]
    out["confirm"] = e3
    lst = get("/doctor/encounters")
    pre = {x["patient_code"]: x["id"] for x in lst if x["kind"] == "pre_visit"}
    out["P-0002"], out["P-0003"] = pre["P-0002"], pre["P-0003"]
    out["P-0004_fu"] = next(x["id"] for x in lst if x["kind"] == "follow_up" and x["patient_code"] == "P-0004")
    return out


def shoot(name: str, size: str, scale: str, url: str, prof: str) -> None:
    f = OUT / f"{name}.png"
    f.unlink(missing_ok=True)
    p = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
                          f"--user-data-dir={prof}", f"--window-size={size}", f"--force-device-scale-factor={scale}",
                          "--virtual-time-budget=6000", f"--screenshot={f}", url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    t0, last = time.time(), -1
    while time.time() - t0 < 60:
        time.sleep(1)
        if f.exists():
            sz = f.stat().st_size
            if sz == last and sz > 0:
                break
            last = sz
    try:
        os.killpg(p.pid, signal.SIGKILL)  # Chrome 截完图不一定自己退出
    except ProcessLookupError:
        pass
    print(name, f.stat().st_size if f.exists() else "MISSING")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fx = fixtures()
    jobs = [
        ("p1_start", "500,1250", "2", f"{WEB}/p"),
        ("p2_verify", "500,1150", "2", f"{WEB}/p/e/{fx['verify']}/questions"),
        ("p3_clarify", "500,1000", "2", f"{WEB}/p/e/{fx['P-0002']}/questions"),
        ("p4_urgent", "500,960", "2", f"{WEB}/p/e/{fx['urgent']}/urgent"),
        ("p5_confirm", "500,1500", "2", f"{WEB}/p/e/{fx['confirm']}/confirm"),
        ("d1_list", "1440,760", "1.5", f"{WEB}/d"),
        ("d2_detail_redflag", "1440,2300", "1.5", f"{WEB}/d/e/{fx['P-0003']}?actor=dr_demo"),
        ("d3_followup", "1440,1500", "1.5", f"{WEB}/d/e/{fx['P-0004_fu']}"),
        ("d4_tasks", "1440,900", "1.5", f"{WEB}/d/tasks"),
        ("d5_print", "900,1700", "1.5", f"{WEB}/d/e/{fx['P-0003']}/print"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, size, scale, url) in enumerate(jobs):
            shoot(name, size, scale, url, f"{tmp}/prof{i}")
    from PIL import Image
    crops = {"p2_verify": (0, 0, 1000, 1560), "p3_clarify": (0, 0, 1000, 1450), "p4_urgent": (0, 0, 1000, 1320),
             "p5_confirm": (0, 0, 1000, 1500), "d2_detail_redflag": (0, 0, 2160, 1780), "d3_followup": (330, 560, 1510, 1740)}
    cdir = OUT / "crops"
    cdir.mkdir(exist_ok=True)
    for name, box in crops.items():
        im = Image.open(OUT / f"{name}.png")
        c = im.crop((box[0], box[1], min(box[2], im.width), min(box[3], im.height))).convert("RGB")
        if c.width > 1400:
            c = c.resize((1400, round(c.height * 1400 / c.width)), Image.LANCZOS)
        c.save(cdir / f"{name}.png", optimize=True)
    print("fixtures:", json.dumps(fx))


if __name__ == "__main__":
    main()
