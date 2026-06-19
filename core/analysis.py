import pandas as pd
import os
import re

# Sloupce, které musí být v každém vstupním EPLAN CSV.
REQUIRED_COLS = ['Značení', 'Stránka č.']

# Kódování, která zkoušíme. Pořadí nerozhoduje o správnosti (rozhoduje kontrola
# povinných sloupců níže), jen o tom, co se použije jako fallback.
ENCODINGS = ['utf-8-sig', 'cp1250', 'cp852', 'iso-8859-2', 'utf-8']


def _smart_read(path):
    """Načte CSV a sám zvolí správné kódování: vezme to, ve kterém vyjdou
    povinné sloupce. Vrací (DataFrame, kódování). Řeší cp1250 vs cp852 vs UTF-8."""
    fallback = None
    last_err = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, sep=';', encoding=enc)
        except Exception as e:
            last_err = e
            continue
        if all(c in df.columns for c in REQUIRED_COLS):
            return df, enc                      # správné kódování (sloupce sedí)
        if fallback is None:
            fallback = (df, enc)                # dekódovalo se, ale sloupce nesedí
    if fallback is not None:
        return fallback
    raise last_err or ValueError("soubor nelze přečíst žádným podporovaným kódováním")


def _read_and_check(paths, role, problems):
    """Načte a zkontroluje každý soubor. Problémy přidává do `problems`
    (nesahá na první chybu – posbírá je všechny). Vrací načtené validní DataFramy."""
    frames = []
    for f in paths:
        name = os.path.basename(f)
        try:
            df, _enc = _smart_read(f)
        except Exception as e:
            problems.append(f"[{role}] {name}: soubor nelze načíst ({e})")
            continue
        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            found = ", ".join(map(str, list(df.columns)[:8])) or "(žádné)"
            if len(df.columns) > 8:
                found += ", …"
            problems.append(f"[{role}] {name}: chybí sloupce {missing}  "
                            f"(nalezené sloupce: {found})")
        elif df.empty:
            problems.append(f"[{role}] {name}: soubor je prázdný (žádné řádky)")
        else:
            frames.append(df)
    return frames


def analyze_raw_data(files_cary, files_signaly):
    """Spojí více CSV souborů a vytvoří základní soupisku.

    Nejprve zkontroluje VŠECHNY vstupní soubory a posbírá všechny chyby
    najednou; teprve pak data zpracuje.
    """
    problems = []
    frames_c = _read_and_check(files_cary, "LINES (čáry)", problems)
    frames_s = _read_and_check(files_signaly, "SIGNALS (signály)", problems)
    if problems:
        raise ValueError("Import neprošel kontrolou souborů:\n• "
                         + "\n• ".join(problems))

    df_c = pd.concat(frames_c, ignore_index=True)
    df_s = pd.concat(frames_s, ignore_index=True)

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
