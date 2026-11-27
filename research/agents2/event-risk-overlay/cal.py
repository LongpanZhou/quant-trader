"""Ex-ante event calendars for the event-risk overlay study.

Every date here is knowable *before* the session it refers to:

* FOMC      -- scheduled decision days, scraped from the Federal Reserve's own
               meeting-calendar pages (fomccalendars.htm / fomchistoricalYYYY.htm).
               The Fed publishes the following year's calendar roughly 12 months
               ahead (e.g. the 2026 dates were posted in mid-2025).  Unscheduled
               emergency meetings (2020-03-03, 2020-03-15) are deliberately
               EXCLUDED: they cannot be known in advance, so a rule that used
               them would be look-ahead.
* CPI       -- BLS "Schedule of Releases for the Consumer Price Index", archived
               snapshots of bls.gov/schedule/news_release/cpi.htm, one snapshot
               per year.  BLS publishes the whole next calendar year's schedule in
               advance.  Release time 08:30 ET.
* NFP       -- BLS "Employment Situation" schedule, same archive method. 08:30 ET.
* OpEx      -- deterministic: third Friday of each month; if that Friday is an
               exchange holiday (Good Friday) the expiry rolls back to the prior
               session.  Rule is pure calendar arithmetic.
* Pre-holiday -- deterministic: last trading session before a full-day NYSE
               holiday (New Year, MLK, Presidents, Good Friday, Memorial,
               Juneteenth, July 4, Labor, Thanksgiving, Christmas).  Also pure
               calendar arithmetic.  Ad-hoc closures (e.g. 2018-12-05 Bush
               funeral, 2025-01-09 Carter funeral) are NOT used as anchors.

Caveat documented in the report: the 2025 US federal shutdown moved several
BLS release dates (Oct-2025 CPI to 2025-10-24, Nov-2025 CPI not published,
Nov/Dec-2025 NFP moved).  The revised dates were announced only days ahead, so
for those months the "ex-ante" claim is weaker.  We keep them (they are still
knowable before the session) and report a sensitivity that drops 2025Q4.
"""
from __future__ import annotations

import datetime as dt

# --------------------------------------------------------------------------
# FOMC scheduled decision days (day 2 of each scheduled meeting).
# Source: federalreserve.gov/monetarypolicy/fomccalendars.htm (2012-2026 links
# fomcpresconfYYYYMMDD) and fomchistorical2016/2017/2018/2020.htm.
# --------------------------------------------------------------------------
FOMC = """
2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28
"""

# --------------------------------------------------------------------------
# CPI release dates (08:30 ET).  Union of archived BLS yearly schedules.
# --------------------------------------------------------------------------
CPI = """
2016-11-17 2016-12-15
2017-01-18 2017-02-15 2017-03-15 2017-04-14 2017-05-12 2017-06-14
2017-07-14 2017-08-11 2017-09-14 2017-10-13 2017-11-15 2017-12-13
2018-01-12 2018-02-14 2018-03-13 2018-04-11 2018-05-10 2018-06-12
2018-07-12 2018-08-10 2018-09-13 2018-10-11 2018-11-14 2018-12-12
2019-01-11 2019-02-13 2019-03-12 2019-04-10 2019-05-10 2019-06-12
2019-07-11 2019-08-13 2019-09-12 2019-10-10 2019-11-13 2019-12-11
2020-01-14 2020-02-13 2020-03-11 2020-04-10 2020-05-12 2020-06-10
2020-07-14 2020-08-12 2020-09-11 2020-10-13 2020-11-12 2020-12-10
2021-01-13 2021-02-10 2021-03-10 2021-04-13 2021-05-12 2021-06-10
2021-07-13 2021-08-11 2021-09-14 2021-10-13 2021-11-10 2021-12-10
2022-01-12 2022-02-10 2022-03-10 2022-04-12 2022-05-11 2022-06-10
2022-07-13 2022-08-10 2022-09-13 2022-10-13 2022-11-10 2022-12-13
2023-01-12 2023-02-14 2023-03-14 2023-04-12 2023-05-10 2023-06-13
2023-07-12 2023-08-10 2023-09-13 2023-10-12 2023-11-14 2023-12-12
2024-01-11 2024-02-13 2024-03-12 2024-04-10 2024-05-15 2024-06-12
2024-07-11 2024-08-14 2024-09-11 2024-10-10 2024-11-13 2024-12-11
2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11
2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18
2026-01-13 2026-02-11 2026-03-11 2026-04-10 2026-05-12 2026-06-10
2026-07-14 2026-08-12 2026-09-11 2026-10-14
"""

# --------------------------------------------------------------------------
# Employment Situation ("NFP") release dates (08:30 ET).
# --------------------------------------------------------------------------
NFP = """
2016-11-04 2016-12-02
2017-01-06 2017-02-03 2017-03-10 2017-04-07 2017-05-05 2017-06-02
2017-07-07 2017-08-04 2017-09-01 2017-10-06 2017-11-03 2017-12-08
2018-01-05 2018-02-02 2018-03-09 2018-04-06 2018-05-04 2018-06-01
2018-07-06 2018-08-03 2018-09-07 2018-10-05 2018-11-02 2018-12-07
2019-01-04 2019-02-01 2019-03-08 2019-04-05 2019-05-03 2019-06-07
2019-07-05 2019-08-02 2019-09-06 2019-10-04 2019-11-01 2019-12-06
2020-01-10 2020-02-07 2020-03-06 2020-04-03 2020-05-08 2020-06-05
2020-07-02 2020-08-07 2020-09-04 2020-10-02 2020-11-06 2020-12-04
2021-01-08 2021-02-05 2021-03-05 2021-04-02 2021-05-07 2021-06-04
2021-07-02 2021-08-06 2021-09-03 2021-10-08 2021-11-05 2021-12-03
2022-01-07 2022-02-04 2022-03-04 2022-04-01 2022-05-06 2022-06-03
2022-07-08 2022-08-05 2022-09-02 2022-10-07 2022-11-04 2022-12-02
2023-01-06 2023-02-03 2023-03-10 2023-04-07 2023-05-05 2023-06-02
2023-07-07 2023-08-04 2023-09-01 2023-10-06 2023-11-03 2023-12-08
2024-01-05 2024-02-02 2024-03-08 2024-04-05 2024-05-03 2024-06-07
2024-07-05 2024-08-02 2024-09-06 2024-10-04 2024-11-01 2024-12-06
2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06
2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16
2026-01-09 2026-02-06 2026-03-06 2026-04-03 2026-05-08 2026-06-05
2026-07-02 2026-08-07 2026-09-04 2026-10-02
"""


def _dates(block: str) -> list[dt.date]:
    out = []
    for tok in block.split():
        y, m, d = (int(x) for x in tok.split("-"))
        out.append(dt.date(y, m, d))
    return out


FOMC_DATES = _dates(FOMC)
CPI_DATES = _dates(CPI)
NFP_DATES = _dates(NFP)


# --------------------------------------------------------------------------
# Deterministic calendars
# --------------------------------------------------------------------------
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """n-th (1-based) weekday (Mon=0) of a month."""
    d = dt.date(year, month, 1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d + dt.timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year, month, 1)
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - dt.timedelta(days=1)
    while d.weekday() != weekday:
        d -= dt.timedelta(days=1)
    return d


def _observed(d: dt.date) -> dt.date:
    """NYSE Saturday/Sunday observance: Sat -> Fri before, Sun -> Mon after."""
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def _easter(year: int) -> dt.date:
    """Gregorian Easter (anonymous computus)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def nyse_holidays(year: int) -> set[dt.date]:
    """Full-day NYSE holidays.  Rules fixed decades in advance."""
    h = {
        _observed(dt.date(year, 1, 1)),                    # New Year
        _nth_weekday(year, 1, 0, 3),                       # MLK
        _nth_weekday(year, 2, 0, 3),                       # Presidents
        _easter(year) - dt.timedelta(days=2),              # Good Friday
        _last_weekday(year, 5, 0),                         # Memorial
        _observed(dt.date(year, 7, 4)),                    # Independence
        _nth_weekday(year, 9, 0, 1),                       # Labor
        _nth_weekday(year, 11, 3, 4),                      # Thanksgiving
        _observed(dt.date(year, 12, 25)),                  # Christmas
    }
    if year >= 2022:
        h.add(_observed(dt.date(year, 6, 19)))             # Juneteenth
    # A Jan-1 Saturday is observed on Dec 31 of the prior year; drop it here.
    h.discard(dt.date(year - 1, 12, 31))
    return h


def opex_dates(year0: int, year1: int) -> list[dt.date]:
    """Monthly option expiry: third Friday, rolled back over a holiday."""
    out = []
    for y in range(year0, year1 + 1):
        hol = nyse_holidays(y) | nyse_holidays(y + 1) | nyse_holidays(y - 1)
        for m in range(1, 13):
            d = _nth_weekday(y, m, 4, 3)
            while d in hol:                                # Good Friday case
                d -= dt.timedelta(days=1)
            out.append(d)
    return out


def pre_holiday_dates(year0: int, year1: int) -> list[dt.date]:
    """Last trading session strictly before each full-day NYSE holiday."""
    out = []
    for y in range(year0, year1 + 1):
        hol = nyse_holidays(y)
        for h in hol:
            d = h - dt.timedelta(days=1)
            while d.weekday() >= 5 or d in hol:
                d -= dt.timedelta(days=1)
            out.append(d)
    return sorted(set(out))
