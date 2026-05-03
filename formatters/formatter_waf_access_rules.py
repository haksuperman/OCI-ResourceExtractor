import pandas as pd

def get_preferred_columns():
    return ['Parent Policy', 'Rule Name', 'Action', 'Condition', 'Condition Language', 'Type']

def extract(df):
    rows = []
    # df는 json_normalize된 상태이므로 request_access_control.rules 리스트를 참조
    for _, policy in df.iterrows():
        policy_name = policy.get('display_name', 'Unknown')
        rules = policy.get('request_access_control.rules', [])
        
        if not isinstance(rules, list): continue
        
        for rule in rules:
            rows.append({
                'Parent Policy': policy_name,
                'Rule Name': rule.get('name'),
                'Action': rule.get('action_name'),
                'Condition': rule.get('condition'),
                'Condition Language': rule.get('condition_language'),
                'Type': rule.get('type')
            })
    return pd.DataFrame(rows)
