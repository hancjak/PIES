import pandas as pd
import re

def analyze_raw_data(files_cary, files_signaly):
    """Spojí více CSV souborů a vytvoří základní soupisku."""
    df_c = pd.concat([pd.read_csv(f, sep=';', encoding='cp1250') for f in files_cary], ignore_index=True)
    df_s = pd.concat([pd.read_csv(f, sep=';', encoding='cp1250') for f in files_signaly], ignore_index=True)

    def get_zn(df):
        col = df['Značení']
        return col.iloc[:, 0].astype(str) if isinstance(col, pd.DataFrame) else col.astype(str)

    df_c['ZN'], df_s['ZN'] = get_zn(df_c), get_zn(df_s)
    vysledek = []
    vsechna_znaceni = {z for z in (set(df_c['ZN'].unique()) | set(df_s['ZN'].unique())) if z != 'nan' and z.strip() != ''}

    for zn in vsechna_znaceni:
        match = re.match(r"^(.*?):(.*?)/(.*?):(.*?)$", zn)
        if not match: continue
        p_a, s_a, p_b, s_b = match.groups()
        rows_c, rows_s = df_c[df_c['ZN'] == zn], df_s[df_s['ZN'] == zn]
        strany_raw = rows_c['Stránka č.'].dropna().tolist() + rows_s['Stránka č.'].dropna().tolist()
        strany = sorted(list(set([int(s) for s in strany_raw if str(s).strip().isdigit()])))
        vysledek.append({
            'Strana A': strany[0] if strany else "", 'Konec A': f"{p_a}:{s_a}",
            'Konec B': f"{p_b}:{s_b}", 'Strana B': strany[-1] if strany else "",
            'Typ vodiče': "", 'Průřez': "", 'Barva': ""
        })
    return pd.DataFrame(vysledek)