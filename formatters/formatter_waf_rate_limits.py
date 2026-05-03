import pandas as pd

def get_preferred_columns():
    return ['Parent Policy', 'Rule Name', 'Action', 'Requests Per Period', 'Period (sec)', 'Condition']

def extract(df):
    rows = []
    for _, policy in df.iterrows():
        policy_name = policy.get('display_name', 'Unknown')
        rate_rules = policy.get('request_rate_limiting.rules', [])
        
        if not isinstance(rate_rules, list): continue
        
        for rule in rate_rules:
            rows.append({
                'Parent Policy': policy_name,
                'Rule Name': rule.get('name'),
                'Action': rule.get('action_name'),
                'Requests Per Period': rule.get('requests_per_period'),
                'Period (sec)': rule.get('period_in_seconds'),
                'Condition': rule.get('condition')
            })
    return pd.DataFrame(rows)
