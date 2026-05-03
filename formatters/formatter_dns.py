import pandas as pd

from . import formatter_dns_records


def get_preferred_columns():
    return {
        "DNS_Zones": [
            "dns_raw.name",
            "dns_raw.id",
            "dns_raw.lifecycle_state",
            "dns_raw.scope",
            "dns_raw.zone_type",
            "dns_raw.dnssec_state",
            "dns_raw.is_protected",
            "dns_raw.serial",
            "dns_raw.compartment_name",
            "dns_raw.region_name",
            "dns_raw.time_created",
            "_errors",
        ],
        "DNS_Records": formatter_dns_records.get_preferred_columns(),
    }


def transform(df):
    if df.empty:
        return {"DNS_Zones": df}

    records_df = formatter_dns_records.extract(df)

    sheets = {"DNS_Zones": df.copy()}
    if isinstance(records_df, pd.DataFrame) and not records_df.empty:
        sheets["DNS_Records"] = records_df
    return sheets
