from formatters import formatter_waf


def get_preferred_columns():
    return formatter_waf.get_preferred_columns_edge()


def transform(df):
    return formatter_waf.transform_edge(df)
