import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from services.report import calc_change_rate, parse_pct, get_week_range


def test_calc_change_rate_normal():
    assert calc_change_rate(110, 100) == "+10.00%"

def test_calc_change_rate_decrease():
    assert calc_change_rate(90, 100) == "-10.00%"

def test_calc_change_rate_zero_base():
    assert calc_change_rate(100, 0) == "N/A"

def test_calc_change_rate_none_base():
    assert calc_change_rate(100, None) == "N/A"

def test_parse_pct_with_percent():
    assert parse_pct("12.34%") == 12.34

def test_parse_pct_number():
    assert parse_pct("56.78") == 56.78

def test_parse_pct_none():
    assert parse_pct(None) is None

def test_get_week_range():
    start, end = get_week_range("2026-03-27")
    assert start == "2026-03-21"
    assert end == "2026-03-27"

def test_get_week_range_midweek():
    start, end = get_week_range("2026-03-25")
    assert start == "2026-03-21"
    assert end == "2026-03-27"
