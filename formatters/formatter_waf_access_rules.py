"""Deprecated compatibility wrapper for the raw-first WAF formatter."""

import pandas as pd

from formatters import formatter_waf


SHEET_NAME = "WAF_Request_Access"


def get_preferred_columns():
    return formatter_waf.get_preferred_columns().get(SHEET_NAME, [])


def extract(df):
    return formatter_waf.transform(df).get(SHEET_NAME, pd.DataFrame())
