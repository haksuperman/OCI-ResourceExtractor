import pandas as pd


ZONE_CONTEXT_COLUMNS = [
    "dns_raw.name",
    "dns_raw.id",
    "dns_raw.scope",
    "dns_raw.zone_type",
    "dns_raw.compartment_name",
    "dns_raw.region_name",
]


def get_preferred_columns():
    return [
        *ZONE_CONTEXT_COLUMNS,
        "record_raw.domain",
        "record_raw.rtype",
        "record_raw.record_type",
        "record_raw.ttl",
        "record_raw.rdata",
        "record_raw.is_protected",
        "record_raw.record_hash",
        "record_raw.rrset_version",
    ]


def _safe_list(value):
    return value if isinstance(value, list) else []


def _zone_context(row):
    return {
        col: row.get(col)
        for col in ZONE_CONTEXT_COLUMNS
        if col in row.index
    }


def extract(df):
    rows = []
    for _, zone in df.iterrows():
        context = _zone_context(zone)
        for record in _safe_list(zone.get("dns_enriched.records")):
            if not isinstance(record, dict):
                continue
            rows.append(
                {
                    **context,
                    "record_raw": record,
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)
