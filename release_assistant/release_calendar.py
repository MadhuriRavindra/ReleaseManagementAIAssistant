"""
Release calendar: the Orbitra Retail weekly and monthly release cycles.

Weekly release (ID WR-YYYY-MMDD, named by its Saturday):
    Mon-Thu   changes accepted until 15:00 IST, deployed to Acceptance (A) at 16:00
    Friday    no A deployments: regression testing and approvals (deadline 18:00)
    Saturday  Production (P) deployment 08:00-10:00 IST

Monthly release (ID MR-YYYY-MM, P on the last Sunday of the month):
    D1 (Tue)            all changes ready in ServiceNow by 23:59
    Extraction (Wed)    changes downloaded from ServiceNow, scope frozen
    A deployment (Mon)  following Monday, 09:00
    Regression          two weeks on A
    Go/No-Go (Sat)      approvals by 12:00; downtime comms sent 48h before P
    P deployment (Sun)  00:00-06:00 IST downtime window
"""

import calendar
from datetime import date, datetime, time, timedelta

WEEKLY_CUTOFF = time(15, 0)
WEEKLY_A_DEPLOY = time(16, 0)
WEEKLY_APPROVAL_DEADLINE = time(18, 0)
WEEKLY_P_START, WEEKLY_P_END = time(8, 0), time(10, 0)
MONTHLY_WINDOW_MINUTES = 360


# ------------------------------------------------------------------ weekly
def weekly_id(saturday):
    return f"WR-{saturday:%Y-%m%d}"


def weekly_calendar(saturday):
    mon = saturday - timedelta(days=5)
    return {
        "type": "Weekly",
        "release_id": weekly_id(saturday),
        "name": f"Weekly release · Sat {saturday:%d %b}",
        "intake_days": [mon + timedelta(days=i) for i in range(4)],     # Mon-Thu
        "final_cutoff": datetime.combine(mon + timedelta(days=3), WEEKLY_CUTOFF),
        "regression_day": saturday - timedelta(days=1),
        "approval_deadline": datetime.combine(saturday - timedelta(days=1),
                                              WEEKLY_APPROVAL_DEADLINE),
        "p_start": datetime.combine(saturday, WEEKLY_P_START),
        "p_end": datetime.combine(saturday, WEEKLY_P_END),
    }


def next_weekly_after(moment):
    """The first weekly release whose Thursday 15:00 cutoff is still open."""
    d = moment.date()
    sat = d + timedelta(days=(5 - d.weekday()) % 7)
    while weekly_calendar(sat)["final_cutoff"] < moment:
        sat += timedelta(days=7)
    return weekly_id(sat)


# ----------------------------------------------------------------- monthly
def last_sunday(year, month):
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - 6) % 7)


def monthly_id(year, month):
    return f"MR-{year}-{month:02d}"


def monthly_calendar(year, month):
    p_sun = last_sunday(year, month)
    a_mon = p_sun - timedelta(days=13)
    extraction = a_mon - timedelta(days=5)
    d1 = extraction - timedelta(days=1)
    return {
        "type": "Monthly",
        "release_id": monthly_id(year, month),
        "name": f"Monthly release · {date(year, month, 1):%B %Y}",
        "d1": datetime.combine(d1, time(23, 59)),
        "extraction": datetime.combine(extraction, time(10, 0)),
        "a_deploy": datetime.combine(a_mon, time(9, 0)),
        "regression_start": datetime.combine(a_mon, time(14, 0)),
        "regression_mid": datetime.combine(a_mon + timedelta(days=7), time(9, 0)),
        "go_no_go": datetime.combine(p_sun - timedelta(days=1), time(12, 0)),
        "comms_deadline": datetime.combine(p_sun - timedelta(days=2), time(0, 0)),
        "p_start": datetime.combine(p_sun, time(0, 0)),
        "p_end": datetime.combine(p_sun, time(6, 0)),
    }


def next_monthly_after(moment):
    """The first monthly release whose D1 is still open."""
    y, m = moment.year, moment.month
    while monthly_calendar(y, m)["d1"] < moment:
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return monthly_id(y, m)


def calendar_for(release_id):
    kind, rest = release_id.split("-", 1)
    if kind == "WR":
        return weekly_calendar(datetime.strptime(rest, "%Y-%m%d").date())
    y, m = rest.split("-")
    return monthly_calendar(int(y), int(m))
