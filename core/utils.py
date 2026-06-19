import re
import pandas as pd

def natural_sort_key(s):
    """Logické řazení (X2 před X10)."""
    if pd.isna(s) or s == '': return ((0, ""),)
    s_str = str(s).strip()
    return tuple((1, int(t)) if t.isdigit() else (0, t.lower()) 
                 for t in re.split(r'(\d+)', s_str))

def parse_cross_section(cs_str):
    """Vytáhne číselnou hodnotu průřezu (0.75 z '0,75mm2')."""
    if not cs_str: return None
    clean_str = str(cs_str).strip().replace(",", ".")
    try:
        num_match = re.search(r"(\d+\.?\d*)", clean_str)
        return float(num_match.group(1)) if num_match else None
    except: return None