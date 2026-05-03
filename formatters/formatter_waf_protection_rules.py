import pandas as pd

def get_preferred_columns():
    return ['Parent Policy', 'Rule Name', 'Action', 'Capability Key', 'Version', 'Body Inspection']

def extract(df):
    rows = []
    for _, policy in df.iterrows():
        policy_name = policy.get('display_name', 'Unknown')
        
        # request_protection.rules 내의 protection_capabilities 추출
        protection_rules = policy.get('request_protection.rules', [])
        if not isinstance(protection_rules, list): continue
        
        for p_rule in protection_rules:
            rule_name = p_rule.get('name')
            action = p_rule.get('action_name')
            is_body_enabled = p_rule.get('is_body_inspection_enabled')
            
            capabilities = p_rule.get('protection_capabilities', [])
            if not isinstance(capabilities, list): continue
            
            for cap in capabilities:
                rows.append({
                    'Parent Policy': policy_name,
                    'Rule Name': rule_name,
                    'Action': action,
                    'Capability Key': cap.get('key'),
                    'Version': cap.get('version'),
                    'Body Inspection': "Enabled" if is_body_enabled else "Disabled"
                })
    return pd.DataFrame(rows)
