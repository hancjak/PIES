import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

class DiffApp(tk.Frame):
    def __init__(self, master, log_func):
        super().__init__(master, bg="#2c2c2c")
        self.pack(fill=tk.BOTH, expand=True)
        self.log = log_func
        self.df_orig = None
        self.df_mod = None

        tk.Label(self, text="PIES DIFF TOOL", font=("Arial", 24, "bold"), fg="#f37021", bg="#2c2c2c").pack(pady=10)
        
        btn_f = tk.Frame(self, bg="#2c2c2c")
        btn_f.pack(pady=5)
        tk.Button(btn_f, text="1. Nahrát ORIGINÁL", width=20, command=self.load_orig).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_f, text="2. Nahrát UPRAVENÝ", width=20, command=self.load_mod).pack(side=tk.LEFT, padx=5)
        
        self.tree_frame = tk.Frame(self)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.tree = ttk.Treeview(self.tree_frame, columns=("Status", "Konec A", "Konec B", "Změna"), show="headings")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=200, anchor="center")
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(self.tree_frame, command=self.tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)

    def load_orig(self):
        f = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if f: 
            try:
                self.df_orig = pd.read_csv(f, encoding='cp1250')
                self.log(f"Diff: Originál načten ({len(self.df_orig)} řádků)")
                self.compare()
            except Exception as e: self.log(f"Chyba: {e}")

    def load_mod(self):
        f = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if f: 
            try:
                self.df_mod = pd.read_csv(f, encoding='cp1250')
                self.log(f"Diff: Upravená data načtena ({len(self.df_mod)} řádků)")
                self.compare()
            except Exception as e: self.log(f"Chyba: {e}")

    def compare(self):
        if self.df_orig is None or self.df_mod is None: return

        self.tree.delete(*self.tree.get_children())
        self.df_orig.columns = self.df_orig.columns.str.strip()
        self.df_mod.columns = self.df_mod.columns.str.strip()

        def create_id(df):
            for c in df.columns:
                if 'číslo kabelu' in c.lower() or 'cislo kabelu' in c.lower():
                    return df[c].astype(str).str.strip(), 'cislo'
            if 'Konec A' in df.columns and 'Konec B' in df.columns:
                return df['Konec A'].astype(str) + " >> " + df['Konec B'].astype(str), 'konce'
            return None, None

        id_orig, uid_type = create_id(self.df_orig)
        id_mod, _ = create_id(self.df_mod)

        if id_orig is None or id_mod is None:
            self.log("Kritická chyba: Soubory neobsahují sloupce 'Konec A' a 'Konec B'!")
            return

        self.df_orig['_uid'] = id_orig
        self.df_mod['_uid'] = id_mod

        orig_uids = set(self.df_orig['_uid'])
        mod_uids = set(self.df_mod['_uid'])

        # SMAZANÉ
        for uid in orig_uids - mod_uids:
            r = self.df_orig[self.df_orig['_uid'] == uid].iloc[0]
            self.tree.insert("", "end", values=("SMAZÁNO", r.get('Konec A', '?'), r.get('Konec B', '?'), "-"), tags=('del',))

        # NOVÉ
        for uid in mod_uids - orig_uids:
            r = self.df_mod[self.df_mod['_uid'] == uid].iloc[0]
            self.tree.insert("", "end", values=("NOVÉ", r.get('Konec A', '?'), r.get('Konec B', '?'), "-"), tags=('new',))

        # ZMĚNY — při Číslo kabelu jako ID kontrolujeme i přejmenování popisků
        compare_cols = ['Průřez', 'Barva', 'Typ vodiče']
        if uid_type == 'cislo':
            compare_cols = ['Konec A', 'Konec B'] + compare_cols
            self.log("Provádím srovnání podle Čísla kabelu (detekuji i změny popisků)...")
        else:
            self.log("Provádím srovnání podle Konec A + Konec B (bez detekce změn popisků)...")

        for uid in orig_uids & mod_uids:
            r1 = self.df_orig[self.df_orig['_uid'] == uid].iloc[0]
            r2 = self.df_mod[self.df_mod['_uid'] == uid].iloc[0]
            diffs = []
            for col in compare_cols:
                if col in r1 and col in r2 and str(r1[col]).strip() != str(r2[col]).strip():
                    diffs.append(f"{col}: {r1[col]}->{r2[col]}")
            if diffs:
                self.tree.insert("", "end", values=("ZMĚNA", r2.get('Konec A', '?'), r2.get('Konec B', '?'), " | ".join(diffs)), tags=('mod',))

        self.tree.tag_configure('del', background='#ffcccc')
        self.tree.tag_configure('new', background='#ccffcc')
        self.tree.tag_configure('mod', background='#ffffcc')

        smazano = sum(1 for i in self.tree.get_children() if self.tree.item(i)['values'][0] == 'SMAZÁNO')
        nove = sum(1 for i in self.tree.get_children() if self.tree.item(i)['values'][0] == 'NOVÉ')
        zmeny = sum(1 for i in self.tree.get_children() if self.tree.item(i)['values'][0] == 'ZMĚNA')
        self.log(f"Srovnání hotovo — Smazáno: {smazano}, Nové: {nove}, Změny: {zmeny}")