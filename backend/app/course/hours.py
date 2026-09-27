"""门诊服务时段与红旗去向：紧急页的主按钮由"红旗去向（急诊 / 门诊）× 现在是否开诊"决定。"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..config import settings
from ..protocol.schema import Protocol
from ..util import now

WEEKDAY = "一二三四五六日"

# 协议没写文案时的保守默认（与模拟临床稿同义；上线前由门诊按实际改）
DEFAULT_COPY = {
    "ed_in_hours": {"headline": "请现在就去急诊", "body": "你说的情况需要尽快当面检查。请立即去附近有急诊的医院，或拨打 120。",
                    "primary": "拨打 120", "secondary": "打电话给门诊"},
    "ed_after_hours": {"headline": "请现在就去急诊", "body": "门诊已下班。你说的情况需要尽快当面检查，请立即去附近有急诊的医院，或拨打 120。",
                       "primary": "拨打 120", "secondary": None},
    "clinic_in_hours": {"headline": "请今天联系门诊", "body": "你说的情况需要医生今天知道。请现在打电话给门诊。",
                        "primary": "打电话给门诊", "secondary": "拨打 120"},
    "clinic_after_hours": {"headline": "门诊已下班", "body": "如果情况变重，请去急诊或拨打 120；否则明早开门后门诊会联系你。",
                           "primary": "拨打 120", "secondary": None},
}


def tz() -> ZoneInfo:
    return ZoneInfo(settings.clinic_tz)


def local_now() -> datetime:
    return now().astimezone(tz())


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def in_service_hours(protocol: Protocol, at: datetime | None = None) -> bool | None:
    """None = 协议没写服务时段（不做按时段分流）。"""
    wins = protocol.course.service_windows
    if not wins:
        return None
    t = (at or local_now()).astimezone(tz())
    return any(t.isoweekday() in w.days and _hm(w.start) <= t.time() < _hm(w.end) for w in wins)


def next_open(protocol: Protocol, at: datetime | None = None) -> datetime | None:
    """下一个开诊时刻（已在开诊时间内则返回现在）。"""
    wins = protocol.course.service_windows
    if not wins:
        return None
    t = (at or local_now()).astimezone(tz())
    if in_service_hours(protocol, t):
        return t
    for d in range(0, 15):
        day = (t + timedelta(days=d)).date()
        starts = sorted(_hm(w.start) for w in wins if day.isoweekday() in w.days)
        for s in starts:
            cand = datetime.combine(day, s, tzinfo=tz())
            if cand > t:
                return cand
    return None


def end_of_today(protocol: Protocol, at: datetime | None = None) -> datetime | None:
    t = (at or local_now()).astimezone(tz())
    ends = sorted(_hm(w.end) for w in protocol.course.service_windows if t.isoweekday() in w.days)
    for e in ends:
        cand = datetime.combine(t.date(), e, tzinfo=tz())
        if cand > t:
            return cand
    return None


def describe_windows(protocol: Protocol) -> str | None:
    wins = protocol.course.service_windows
    if not wins:
        return None
    parts = []
    for w in wins:
        ds = sorted(w.days)
        span = (f"周{WEEKDAY[ds[0] - 1]}至周{WEEKDAY[ds[-1] - 1]}" if ds == list(range(ds[0], ds[-1] + 1)) and len(ds) > 2
                else "、".join(f"周{WEEKDAY[d - 1]}" for d in ds))
        parts.append(f"{span} {w.start}–{w.end}")
    return "；".join(parts)


def describe_moment(protocol: Protocol, when: datetime | None) -> str | None:
    if when is None:
        return None
    t, n = when.astimezone(tz()), local_now()
    day = "今天" if t.date() == n.date() else ("明天" if t.date() == (n + timedelta(days=1)).date() else f"周{WEEKDAY[t.isoweekday() - 1]}")
    return f"{day} {t:%H:%M}"


def route_of(protocol: Protocol, rule_id: str, severity: str) -> str:
    """红旗去向：ed = 立即去急诊或拨打 120；clinic = 联系门诊。协议没写时，紧急级去急诊，其余联系门诊。"""
    r = protocol.course.red_flag_routes.get(rule_id)
    return r if r in ("ed", "clinic") else ("ed" if severity == "urgent" else "clinic")


def urgent_view(protocol: Protocol, alerts: list[dict]) -> dict | None:
    """患者端紧急页 / 提示条用：按最严重的在效红旗给出去向、是否开诊与对应文案。alerts 为 _alert_to_dict 结果。"""
    live = [a for a in alerts if a.get("severity") in ("urgent", "same_day")]
    if not live:
        return None
    routes = [route_of(protocol, a["rule_id"], a["severity"]) for a in live]
    route = "ed" if "ed" in routes else "clinic"
    open_now = in_service_hours(protocol)
    key = f"{route}_{'in' if open_now is not False else 'after'}_hours"
    copy = protocol.course.urgent_page.get(key)
    c = copy.model_dump() if copy else dict(DEFAULT_COPY[key])
    if any(a.get("provisional") for a in live):
        c["headline"] = "前后信息不一致，需要尽快核实"
        c["body"] = next(a["patient_message"] for a in live if a.get("provisional"))
    nxt = next_open(protocol) if open_now is False else None
    return {"route": route, "in_service_hours": open_now, "copy_key": key, **c,
            "reassurance": protocol.course.reassurance, "next_open": describe_moment(protocol, nxt),
            "service_hours": describe_windows(protocol), "simulated": protocol.course.simulated}
