import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys, os, shutil
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path: sys.path.insert(0, parent_dir)

from core.style import THEME
from core.utils import natural_sort_key, parse_cross_section
from core.printer import make_the_shitty_file_200

class KabelovyEditor(tk.Frame):
    def __init__(self, master, df_k, df_s, filename, log_func, sklad_path):
        super().__init__(master, bg=THEME["bg"])
        self.pack(fill=tk.BOTH, expand=True)
        
        # --- FIX: Převedeme vše na string, aby editace (text) nekolidovala s dtypes (int) ---
        self.df = df_k.astype(str)
        self.df_sklad = df_s.astype(str)
        
        self.project_filename = os.path.abspath(filename)
        self.log, self.sklad_path = log_func, os.path.abspath(sklad_path)
        
        self.current_filter = "(Vše)"
        self.sort_states = {col: None for col in self.df.columns}
        self.search_results, self.search_index = [], -1
        self._pending_assignment = []
        self._shift_anchor = None
        self._ctrl_mode = False
        self._cursor_main = None
        self._cursor_sklad = None

        # Search Bar
        self.search_bar = tk.Frame(self, bg=THEME["dark_grey"])
        self.search_entry = tk.Entry(self.search_bar, bg=THEME["bg"], fg=THEME["fg"], insertbackground=THEME["fg"], font=THEME["font_main"])
        self.search_entry.pack(side=tk.LEFT, padx=10, pady=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self.perform_search())
        self.lbl_search_count = tk.Label(self.search_bar, text="0/0", bg=THEME["dark_grey"], fg=THEME["accent"])
        self.lbl_search_count.pack(side=tk.LEFT, padx=5)

        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.sidebar = tk.Frame(self.paned, bg=THEME["bg"])
        self.paned.add(self.sidebar, weight=1)
        tk.Label(self.sidebar, text="[ DEVICES ]", font=(THEME["font_main"][0], 10, "bold"), bg=THEME["bg"], fg=THEME["accent"]).pack(pady=5)
        self.tree_nav = ttk.Treeview(self.sidebar, show="tree")
        self.tree_nav.pack(fill=tk.BOTH, expand=True)
        self.tree_nav.bind("<<TreeviewSelect>>", lambda e: self.on_nav_select())

        self.center = tk.Frame(self.paned, bg=THEME["bg"])
        self.paned.add(self.center, weight=4)
        self.tree = ttk.Treeview(self.center, columns=list(self.df.columns), show='headings', selectmode='extended')
        sb_y = ttk.Scrollbar(self.center, orient="vertical", command=self.tree.yview); sb_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb_y.set)
        for col in self.df.columns:
            self.tree.heading(col, text=col, command=lambda _c=col: self.toggle_sort(_c))
            self.tree.column(col, width=100, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)

        bottom_bar = tk.Frame(self.center, bg=THEME["dark_grey"], height=38)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_bar.pack_propagate(False)

        _tb = dict(bg=THEME["dark_grey"], fg=THEME["fg"], font=(THEME["font_main"][0], 10, "bold"),
                   relief=tk.FLAT, cursor="hand2", pady=4)
        tk.Button(bottom_bar, text="[ SAVE ]",   command=self.save_project,   **_tb).pack(side=tk.LEFT, padx=(10, 2))
        tk.Button(bottom_bar, text="[ SEARCH ]", command=self.show_search_bar, **_tb).pack(side=tk.LEFT, padx=2)
        tk.Button(bottom_bar, text="[ PRINT ]",  command=self.print_labels,   **_tb).pack(side=tk.LEFT, padx=2)
        tk.Button(bottom_bar, text="[ EXPORT ]", command=self.export_dialog,  **_tb).pack(side=tk.LEFT, padx=2)

        self.btn_add = tk.Button(bottom_bar, text="[ + ADD ROW ]", bg=THEME["bg"], fg=THEME["accent"],
                                 font=(THEME["font_main"][0], 11, "bold"), command=self.add_new_label_row,
                                 relief=tk.FLAT, cursor="hand2")
        self.btn_add.pack(side=tk.RIGHT, padx=10, pady=4)

        self.right = tk.LabelFrame(self.paned, text="STORAGE", bg=THEME["bg"], fg=THEME["accent"], font=THEME["font_main"], borderwidth=1)
        self.paned.add(self.right, weight=2)
        self.tree_sklad = ttk.Treeview(self.right, columns=list(self.df_sklad.columns), show="headings", selectmode="browse")
        for c in self.df_sklad.columns:
            self.tree_sklad.heading(c, text=c)
            self.tree_sklad.column(c, width=80, anchor="center")
        self.tree_sklad.pack(fill=tk.BOTH, expand=True)

        storage_bar = tk.Frame(self.right, bg=THEME["dark_grey"], height=38)
        storage_bar.pack(side=tk.BOTTOM, fill=tk.X)
        storage_bar.pack_propagate(False)
        _sb = dict(bg=THEME["dark_grey"], fg=THEME["fg"], font=(THEME["font_main"][0], 10, "bold"),
                   relief=tk.FLAT, cursor="hand2", pady=4)
        tk.Button(storage_bar, text="[ + ADD ]",  command=self.add_new_sklad_row, bg=THEME["bg"],
                  fg=THEME["accent"], font=(THEME["font_main"][0], 10, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=(10, 2), pady=4)
        tk.Button(storage_bar, text="[ EDIT ]",   command=self.start_sklad_edit,  **_sb).pack(side=tk.LEFT, padx=2)
        tk.Button(storage_bar, text="[ DELETE ]", command=self.delete_sklad_row,
                  bg=THEME["dark_grey"], fg="#FF4444", font=(THEME["font_main"][0], 10, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=2, pady=4)

        # Kontext menu skladu
        self.m_sklad = tk.Menu(self, tearoff=0, bg=THEME["dark_grey"], fg=THEME["fg"])
        self.m_sklad.add_command(label="ADD WIRE", command=self.add_new_sklad_row)
        self.m_sklad.add_command(label="EDIT WIRE", command=self.start_sklad_edit)
        self.m_sklad.add_command(label="DELETE WIRE", command=self.delete_sklad_row)

        self.tree.bind("<Double-1>", lambda e: self.on_double_click(e, self.tree, self.df))
        self.tree_sklad.bind("<Double-1>", lambda e: self.assign_sklad_to_project())
        self.tree_sklad.bind("<Button-3>", lambda e: self.m_sklad.post(e.x_root, e.y_root))
        self.tree.bind("<Delete>", self.confirm_delete)

        # Keyboard navigation
        self.tree_nav.bind("<Tab>",       lambda e: self._tab_to(self.tree))
        self.tree.bind("<Tab>",           lambda e: self._tab_to(self.tree_sklad))
        self.tree_sklad.bind("<Tab>",     lambda e: self._tab_to(self.tree_nav))

        # Šipky: pohyb selectorem bez fill-highlightu
        self.tree.bind("<Up>",            lambda e: self._nav_key(self.tree, 'up'))
        self.tree.bind("<Down>",          lambda e: self._nav_key(self.tree, 'down'))
        self.tree_sklad.bind("<Up>",      lambda e: self._nav_key(self.tree_sklad, 'up'))
        self.tree_sklad.bind("<Down>",    lambda e: self._nav_key(self.tree_sklad, 'down'))

        # FocusOut: smaž selector pokud focus opustil panel (ne při inline editaci)
        self.tree.bind("<FocusOut>",
            lambda e: self.after(60, lambda: self._clear_if_left(self.tree)))
        self.tree_sklad.bind("<FocusOut>",
            lambda e: self.after(60, lambda: self._clear_if_left(self.tree_sklad)))
        self.tree_nav.bind("<FocusOut>",
            lambda e: self.after(60, lambda: self.tree_nav.selection_set([])))

        # Shift+šipky = range select
        self.tree.bind("<Shift-Down>",     lambda e: self._shift_nav(self.tree, 'down'))
        self.tree.bind("<Shift-Up>",       lambda e: self._shift_nav(self.tree, 'up'))
        # Ctrl+šipky = navigace BEZ změny selection (ctrl_mode ON)
        self.tree.bind("<Control-Down>",   lambda e: self._ctrl_nav('down'))
        self.tree.bind("<Control-Up>",     lambda e: self._ctrl_nav('up'))
        # Escape = zrušit výběr
        self.tree.bind("<Escape>",         lambda e: self._cancel_selection())
        self.tree_sklad.bind("<Escape>",   lambda e: self._cancel_selection())
        # Blokuj Left/Right v STORAGE (brání divokému chování defaultního Treeview)
        self.tree_sklad.bind("<Left>",     lambda e: "break")
        self.tree_sklad.bind("<Right>",    lambda e: "break")

        # Enter: v ctrl_mode = toggle řádku, jinak = otevřít editor
        self.tree.bind("<Return>",         self._enter_key)
        self.tree_sklad.bind("<Return>",   lambda e: self._storage_enter())

        # Barevné tagy pro zebra efekt + cursor
        self.tree.tag_configure('row_odd',  background=THEME["bg"])
        self.tree.tag_configure('row_even', background=THEME["bg_alt"])
        self.tree.tag_configure('cursor',   background='#1A1400', foreground=THEME["accent"])
        self.tree_sklad.tag_configure('row_odd',  background=THEME["bg"])
        self.tree_sklad.tag_configure('row_even', background=THEME["bg_alt"])
        self.tree_sklad.tag_configure('cursor',   background='#1A1400', foreground=THEME["accent"])

        self.refresh_nav_tree(); self.refresh_sklad(); self.fill_table()

    def spawn_inline_entry(self, tree, item, column, df):
        if not column: return
        col_idx = int(column[1:]) - 1
        col_name = tree.cget("columns")[col_idx]
        x, y, w, h = tree.bbox(item, column)
        
        entry = tk.Entry(tree, bg=THEME["accent"], fg=THEME["bg"], font=(THEME["font_main"][0], 10, "bold"), insertbackground=THEME["bg"], borderwidth=0)
        entry.insert(0, str(tree.item(item)['values'][col_idx]))
        entry.place(x=x, y=y, width=w, height=h); entry.focus_set(); entry.selection_range(0, tk.END)
        
        def save_and_move(direction=0):
            val = entry.get()
            df.at[int(item), col_name] = str(val)
            entry.destroy()

            if tree == self.tree_sklad: self.refresh_sklad()
            else: self.fill_table()

            if direction != 0:
                self.move_focus(tree, item, col_idx, direction, df)
            else:
                # Vrátit cursor na řádek, šipky fungují ihned
                tree.focus_set()
                if tree.exists(item):
                    self._set_cursor_tag(tree, item)
                    tree.focus(item)
                    tree.see(item)

        entry.bind("<Return>", lambda e: save_and_move(0))
        entry.bind("<Tab>", lambda e: save_and_move(1))
        entry.bind("<Right>", lambda e: save_and_move(1))
        entry.bind("<Left>", lambda e: save_and_move(-1))
        entry.bind("<FocusOut>", lambda e: entry.destroy())

    def move_focus(self, tree, item, current_idx, direction, df):
        next_idx = current_idx + direction
        if 0 <= next_idx < len(tree.cget("columns")):
            self.spawn_inline_entry(tree, item, f"#{next_idx+1}", df)

    def on_double_click(self, event, tree, df):
        if tree.identify_region(event.x, event.y) == "cell":
            self.spawn_inline_entry(tree, tree.identify_row(event.y), tree.identify_column(event.x), df)

    def fill_table(self):
        saved_sel = list(self.tree.selection())
        saved_cur = self._cursor_main
        self.tree.delete(*self.tree.get_children())
        if self.current_filter == "(Vše)":
            d = self.df
        else:
            pref = self.current_filter + ":"
            d = self.df[self.df['Konec A'].str.startswith(pref, na=False) | self.df['Konec B'].str.startswith(pref, na=False)]
        for i, (idx, r) in enumerate(d.iterrows()):
            tag = 'row_even' if i % 2 == 0 else 'row_odd'
            self.tree.insert("", tk.END, iid=idx, values=list(r), tags=(tag,))
        for col in self.df.columns:
            ic = " ^" if self.sort_states.get(col) == 'asc' else (" v" if self.sort_states.get(col) == 'desc' else "")
            self.tree.heading(col, text=f"{col}{ic}")
        valid_sel = [s for s in saved_sel if self.tree.exists(s)]
        if valid_sel:
            self.tree.selection_set(valid_sel)
        self._cursor_main = None
        if saved_cur and self.tree.exists(saved_cur):
            self._set_cursor_tag(self.tree, saved_cur)

    def refresh_sklad(self):
        saved_sel = list(self.tree_sklad.selection())
        saved_cur = self._cursor_sklad
        self.tree_sklad.delete(*self.tree_sklad.get_children())
        for i, (idx, r) in enumerate(self.df_sklad.iterrows()):
            tag = 'row_even' if i % 2 == 0 else 'row_odd'
            self.tree_sklad.insert("", tk.END, iid=idx, values=list(r), tags=(tag,))
        valid_sel = [s for s in saved_sel if self.tree_sklad.exists(s)]
        if valid_sel:
            self.tree_sklad.selection_set(valid_sel)
        self._cursor_sklad = None
        if saved_cur and self.tree_sklad.exists(saved_cur):
            self._set_cursor_tag(self.tree_sklad, saved_cur)

    def add_new_sklad_row(self):
        new_idx = self.df_sklad.index.max() + 1 if not self.df_sklad.empty else 0
        self.df_sklad.loc[new_idx] = ["NEW", "0.75", "BLACK"]
        self.refresh_sklad(); self.tree_sklad.selection_set(new_idx); self.start_sklad_edit()

    def start_sklad_edit(self):
        s = self.tree_sklad.selection()
        if s: self.spawn_inline_entry(self.tree_sklad, s[0], "#1", self.df_sklad)

    def delete_sklad_row(self):
        s = self.tree_sklad.selection()
        if s and messagebox.askyesno("PIES", "ERASE WIRE?"): self.df_sklad = self.df_sklad.drop(int(s[0])).reset_index(drop=True); self.refresh_sklad()

    def assign_sklad_to_project(self):
        sk = self.tree_sklad.selection()
        pr = self.tree.selection() or self._pending_assignment
        if sk and pr:
            v = self.tree_sklad.item(sk[0])['values']
            for i in pr:
                idx = int(i)
                for x, c in enumerate(["Typ vodiče", "Průřez", "Barva"]):
                    if c in self.df.columns: self.df.at[idx, c] = str(v[x])
            self._pending_assignment = []
            self.fill_table(); self.log(f"LINKED: {v[0]}")

    def on_nav_select(self):
        s = self.tree_nav.selection()
        if s: self.current_filter = s[0]; self.fill_table()

    def refresh_nav_tree(self):
        self.tree_nav.delete(*self.tree_nav.get_children()); self.tree_nav.insert("", "end", iid="(Vše)", text="(Vše)")
        p = sorted({str(v).split(":")[0] for c in ['Konec A', 'Konec B'] for v in self.df[c].dropna() if ":" in str(v)}, key=natural_sort_key)
        for x in p: self.tree_nav.insert("", "end", iid=x, text=x)

    def save_project(self):
        self.df.to_csv(self.project_filename, index=False, encoding='cp1250')
        self.df_sklad.to_csv(self.sklad_path, index=False, encoding='cp1250')
        self.log(f"SAVED TO: {self.project_filename}")

    def print_labels(self):
        target = filedialog.askdirectory()
        if not target: return
        self.log("Printing...")
        try:
            folder_count = 0
            for p_num, group in self.df.groupby('Strana A'):
                p_folder = Path(target) / f"Strana_{str(p_num).zfill(2)}"
                if p_folder.exists(): shutil.rmtree(p_folder)
                p_folder.mkdir(parents=True, exist_ok=True)
                folder_count += 1
                cats = {"BS25": [], "BS35": [], "BS45": [], "Ostatni": []}
                for idx, row in group.iterrows():
                    v = parse_cross_section(row['Průřez'])
                    if v is None: cats["Ostatni"].append(idx)
                    elif 0.24 <= v <= 0.75: cats["BS25"].append(idx)
                    elif 0.75 < v <= 1.5: cats["BS35"].append(idx)
                    elif 1.5 < v <= 4.0: cats["BS45"].append(idx)
                    else: cats["Ostatni"].append(idx)
                for sfx, ids in cats.items():
                    if ids:
                        with open(p_folder / f"Tisk_{sfx}.txt", "w", encoding="utf-8") as f:
                            f.write(make_the_shitty_file_200(group.loc[ids], 1))
            self.log(f"Print hotov — {folder_count} složek uloženo do: {target}")
        except Exception as e: self.log(f"Error: {e}")

    # ---------------- EXPORT ----------------
    @staticmethod
    def _safe_name(value, used):
        """Očistí hodnotu na název listu/souboru (bez zakázaných znaků, max 31 znaků, unikátní)."""
        parts = value if isinstance(value, tuple) else (value,)
        name = "_".join((str(v).strip() or "prazdne") for v in parts)
        for ch in '[]:*?/\\':
            name = name.replace(ch, "-")
        name = name[:31]
        base, i = name, 1
        while name.lower() in used:
            suffix = f"_{i}"
            name = base[:31 - len(suffix)] + suffix
            i += 1
        used.add(name.lower())
        return name

    def _grouped(self, group_cols):
        """Vrátí seznam (název, dataframe). Bez sloupců = jeden celek."""
        if not group_cols:
            return [("Export", self.df)]
        used = set()
        out = []
        for key, g in self.df.groupby(group_cols, sort=True, dropna=False):
            out.append((self._safe_name(key, used), g))
        return out

    def export_dialog(self):
        if self.df.empty:
            messagebox.showinfo("PIES", "Není co exportovat — tabulka je prázdná.")
            return

        win = tk.Toplevel(self)
        win.title("EXPORT")
        win.configure(bg=THEME["bg"])
        win.transient(self.winfo_toplevel())
        win.grab_set()

        tk.Label(win, text="ROZDĚLIT DO LISTŮ / SOUBORŮ PODLE:", bg=THEME["bg"], fg=THEME["accent"],
                 font=(THEME["font_main"][0], 10, "bold")).pack(anchor="w", padx=16, pady=(14, 6))

        col_vars = {}
        for col in self.df.columns:
            var = tk.BooleanVar(value=col in ("Průřez", "Barva"))
            col_vars[col] = var
            tk.Checkbutton(win, text=col, variable=var, bg=THEME["bg"], fg=THEME["fg"],
                           selectcolor=THEME["dark_grey"], activebackground=THEME["bg"],
                           activeforeground=THEME["accent"], font=THEME["font_main"],
                           anchor="w").pack(fill=tk.X, padx=24)

        tk.Label(win, text="(nic = vše do jednoho)", bg=THEME["bg"], fg=THEME["fg_dim"],
                 font=(THEME["font_main"][0], 8)).pack(anchor="w", padx=24, pady=(0, 8))

        tk.Label(win, text="FORMÁT:", bg=THEME["bg"], fg=THEME["accent"],
                 font=(THEME["font_main"][0], 10, "bold")).pack(anchor="w", padx=16, pady=(6, 4))
        fmt = tk.StringVar(value="xlsx")
        for val, txt in [("xlsx", "Excel (.xlsx) — jeden soubor, více listů"),
                         ("csv", "CSV — více souborů (jeden na skupinu)")]:
            tk.Radiobutton(win, text=txt, variable=fmt, value=val, bg=THEME["bg"], fg=THEME["fg"],
                           selectcolor=THEME["dark_grey"], activebackground=THEME["bg"],
                           activeforeground=THEME["accent"], font=THEME["font_main"],
                           anchor="w").pack(fill=tk.X, padx=24)

        btn_row = tk.Frame(win, bg=THEME["bg"])
        btn_row.pack(fill=tk.X, padx=16, pady=14)
        _b = dict(bg=THEME["dark_grey"], fg=THEME["fg"], font=(THEME["font_main"][0], 10, "bold"),
                  relief=tk.FLAT, cursor="hand2", pady=4, padx=10)

        def do_export():
            group_cols = [c for c, v in col_vars.items() if v.get()]
            win.destroy()
            self._run_export(group_cols, fmt.get())

        tk.Button(btn_row, text="[ EXPORT ]", command=do_export, **_b).pack(side=tk.LEFT)
        tk.Button(btn_row, text="[ ZRUŠIT ]", command=win.destroy, **_b).pack(side=tk.LEFT, padx=8)

    def _run_export(self, group_cols, fmt):
        groups = self._grouped(group_cols)
        try:
            if fmt == "xlsx":
                path = filedialog.asksaveasfilename(title="EXPORT DO EXCELU", defaultextension=".xlsx",
                                                    initialfile="export.xlsx", filetypes=[("Excel", "*.xlsx")])
                if not path: return
                try:
                    with pd.ExcelWriter(path, engine="openpyxl") as w:
                        for name, g in groups:
                            g.to_excel(w, sheet_name=name, index=False)
                except ImportError:
                    messagebox.showerror("PIES", "Chybí knihovna 'openpyxl'.\nNainstaluj příkazem: pip install openpyxl")
                    return
                self.log(f"EXPORT (Excel): {len(groups)} listů → {path}")
            else:
                target = filedialog.askdirectory(title="SLOŽKA PRO CSV EXPORT")
                if not target: return
                for name, g in groups:
                    g.to_csv(Path(target) / f"{name}.csv", index=False, encoding="cp1250")
                self.log(f"EXPORT (CSV): {len(groups)} souborů → {target}")
        except Exception as e:
            self.log(f"Export error: {e}")
            messagebox.showerror("PIES", f"Export selhal:\n{e}")

    def add_new_label_row(self):
        idx = self.df.index.max() + 1 if not self.df.empty else 0
        # Vytvoříme řádek stringů
        self.df.loc[idx] = pd.Series({c: "" for c in self.df.columns}).astype(str)
        self.df.at[idx, 'Strana A'] = "NEW"
        self.fill_table(); self.tree.selection_set(idx); self.tree.see(idx)

    def toggle_sort(self, col):
        s = self.sort_states[col]; self.sort_states[col] = 'asc' if s != 'asc' else 'desc'
        tdf = self.df.copy(); tdf['_s'] = tdf[col].apply(natural_sort_key)
        self.df = tdf.sort_values('_s', ascending=(self.sort_states[col]=='asc')).drop(columns='_s').reset_index(drop=True); self.fill_table()

    def confirm_delete(self, e=None):
        s = self.tree.selection()
        if s and messagebox.askyesno("PIES", "DELETE?"): self.df = self.df.drop([int(i) for i in s]).reset_index(drop=True); self.refresh_nav_tree(); self.fill_table()

    def _set_cursor_tag(self, tree, item):
        """Přesune 'cursor' tag na daný item (None = jen smaže z předchozího)."""
        attr = '_cursor_main' if tree is self.tree else '_cursor_sklad'
        old = getattr(self, attr)
        if old and old != item and tree.exists(old):
            tags = tuple(t for t in tree.item(old, 'tags') if t != 'cursor')
            tree.item(old, tags=tags)
        if item and tree.exists(item):
            tags = tuple(t for t in tree.item(item, 'tags') if t != 'cursor') + ('cursor',)
            tree.item(item, tags=tags)
        setattr(self, attr, item)

    def _tab_to(self, tree):
        self._shift_anchor = None
        self._ctrl_mode = False
        if tree is self.tree_sklad and self.tree.selection():
            self._pending_assignment = list(self.tree.selection())
            self._set_cursor_tag(self.tree_sklad, None)
            self.tree_nav.selection_set([]); self.tree_nav.focus("")
            self.tree_sklad.selection_set([]); self.tree_sklad.focus("")
        else:
            self._pending_assignment = []
            self._set_cursor_tag(self.tree, None)
            self._set_cursor_tag(self.tree_sklad, None)
            for t in (self.tree_nav, self.tree, self.tree_sklad):
                t.selection_set([]); t.focus("")
        tree.focus_set()
        self._place_selector(tree)
        return "break"

    def _place_selector(self, tree):
        """Umístí cursor tag na první řádek pokud žádný cursor není."""
        cur = tree.focus()
        if not cur:
            ch = tree.get_children()
            if ch:
                cur = ch[0]
                tree.focus(cur)
                tree.see(cur)
        if cur:
            self._set_cursor_tag(tree, cur)
            if not self._pending_assignment:
                tree.selection_set([cur])

    def _nav_key(self, tree, direction):
        """Pohyb cursorem — tag vždy viditelný, selection jen v non-ctrl módu."""
        self._shift_anchor = None
        cur = tree.focus()
        nxt = (tree.get_children()[0] if tree.get_children() else None) if not cur \
              else (tree.prev(cur) or cur) if direction == 'up' \
              else (tree.next(cur) or cur)
        if nxt:
            if not (tree is self.tree and self._ctrl_mode):
                tree.selection_set([nxt])
            self._set_cursor_tag(tree, nxt)
            tree.focus(nxt)
            tree.see(nxt)
        return "break"

    def _clear_if_left(self, tree):
        """Smaž selector jen pokud focus opustil celý panel (ne při inline editaci)."""
        fw = self.focus_get()
        if fw is None or fw is tree:
            return
        try:
            if str(fw).startswith(str(tree) + "."):
                return  # Focus je v inline Entry uvnitř tree
        except Exception:
            pass
        if tree is self.tree and self._pending_assignment:
            return
        self._set_cursor_tag(tree, None)
        tree.selection_set([])
        tree.focus("")

    # ── Multi-select & přiřazení ────────────────────────────────────────────

    def _shift_nav(self, tree, direction):
        """Shift+šipka: range select od anchoru po kurzor."""
        cur = tree.focus()
        if not cur:
            return "break"
        if self._shift_anchor is None:
            self._shift_anchor = cur
        nxt = tree.prev(cur) if direction == 'up' else tree.next(cur)
        if not nxt:
            return "break"
        items = tree.get_children()
        ai = items.index(self._shift_anchor) if self._shift_anchor in items else 0
        ni = items.index(nxt)
        start, end = min(ai, ni), max(ai, ni)
        tree.selection_set(items[start:end + 1])
        self._set_cursor_tag(tree, nxt)
        tree.focus(nxt)
        tree.see(nxt)
        return "break"


    def _ctrl_nav(self, direction):
        """Ctrl+šipka: přesune cursor tag BEZ změny selection, zapne ctrl_mode."""
        self._ctrl_mode = True
        self._shift_anchor = None
        cur = self.tree.focus()
        if not cur:
            return "break"
        nxt = self.tree.prev(cur) if direction == 'up' else self.tree.next(cur)
        if nxt:
            self._set_cursor_tag(self.tree, nxt)
            self.tree.focus(nxt)
            self.tree.see(nxt)
        return "break"

    def _ctrl_toggle_current(self):
        """Togglene aktuálně fokusovaný řádek v/z selection."""
        cur = self.tree.focus()
        if not cur:
            return
        sel = list(self.tree.selection())
        if cur in sel:
            sel.remove(cur)
        else:
            sel.append(cur)
        self.tree.selection_set(sel)

    def _enter_key(self, event):
        """Enter: v ctrl_mode togglene řádek, jinak otevře editor."""
        if self._ctrl_mode:
            self._ctrl_toggle_current()
        else:
            self._enter_edit_main(event)

    def _cancel_selection(self):
        """Escape: zruší celou operaci výběru."""
        self._pending_assignment = []
        self._shift_anchor = None
        self._ctrl_mode = False
        self._set_cursor_tag(self.tree, None)
        self._set_cursor_tag(self.tree_sklad, None)
        for t in (self.tree, self.tree_sklad):
            t.selection_set([])
            t.focus("")
        self.log("Výběr zrušen.")

    def _storage_enter(self):
        """Enter v STORAGE: pokud máme pending → potvrzovací dialog, jinak přiřadit myší."""
        if self._pending_assignment:
            self._show_assign_confirm()
        else:
            self.assign_sklad_to_project()

    def _show_assign_confirm(self):
        sel_sklad = self.tree_sklad.focus()
        if not sel_sklad:
            return
        v = self.tree_sklad.item(sel_sklad)['values']
        kabel_info = f"{v[0]}  /  {v[1]}  /  {v[2]}" if len(v) >= 3 else str(v)
        count = len(self._pending_assignment)

        dlg = tk.Toplevel(self)
        dlg.title("PIES – Potvrdit přiřazení")
        dlg.configure(bg=THEME["bg"])
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 480) // 2
        y = self.winfo_y() + (self.winfo_height() - 170) // 2
        dlg.geometry(f"480x170+{x}+{y}")

        tk.Label(dlg, text=f"Přiřadit kabel k  {count}  řádkům?",
                 font=("Consolas", 12), bg=THEME["bg"], fg=THEME["fg"]).pack(pady=(18, 4))
        tk.Label(dlg, text=kabel_info,
                 font=("Consolas", 13, "bold"), bg=THEME["bg"], fg=THEME["accent"]).pack(pady=(0, 18))

        btn_row = tk.Frame(dlg, bg=THEME["bg"])
        btn_row.pack()

        choice = tk.IntVar(value=0)  # 0 = ANO, 1 = NE

        lbl_ano = tk.Label(btn_row, text="[ ANO ]", font=("Consolas", 12, "bold"),
                           bg=THEME["dark_grey"], fg=THEME["accent"], padx=18, pady=6, cursor="hand2")
        lbl_ano.pack(side=tk.LEFT, padx=10)
        lbl_ne = tk.Label(btn_row, text="[ NE ]", font=("Consolas", 12, "bold"),
                          bg=THEME["bg"], fg=THEME["fg"], padx=18, pady=6, cursor="hand2")
        lbl_ne.pack(side=tk.LEFT, padx=10)

        def refresh():
            if choice.get() == 0:
                lbl_ano.config(bg=THEME["dark_grey"], fg=THEME["accent"])
                lbl_ne.config(bg=THEME["bg"], fg=THEME["fg"])
            else:
                lbl_ano.config(bg=THEME["bg"], fg=THEME["fg"])
                lbl_ne.config(bg=THEME["dark_grey"], fg="#FF4444")

        def confirm(event=None):
            if choice.get() == 0:
                self._do_assign(sel_sklad)
                dlg.destroy()
            else:
                dlg.destroy()
                self.tree_sklad.focus_set()
                self._place_selector(self.tree_sklad)

        def escape(event=None):
            dlg.destroy()
            self._cancel_selection()

        dlg.bind("<Left>",   lambda e: (choice.set(0), refresh()))
        dlg.bind("<Right>",  lambda e: (choice.set(1), refresh()))
        dlg.bind("<Return>", confirm)
        dlg.bind("<Escape>", escape)
        lbl_ano.bind("<Button-1>", confirm)
        lbl_ne.bind("<Button-1>",  lambda e: (choice.set(1), confirm()))
        dlg.focus_set()

    def _do_assign(self, sklad_item):
        v = self.tree_sklad.item(sklad_item)['values']
        for i in self._pending_assignment:
            idx = int(i)
            for x, c in enumerate(["Typ vodiče", "Průřez", "Barva"]):
                if c in self.df.columns:
                    self.df.at[idx, c] = str(v[x])
        count = len(self._pending_assignment)
        self._pending_assignment = []
        self._shift_anchor = None
        self.fill_table()
        self.log(f"LINKED: {v[0]} / {v[1]} / {v[2]}  →  {count} řádků")
        self.tree.focus_set()
        self._place_selector(self.tree)

    def _enter_edit_main(self, _event):
        item = self.tree.focus()
        if not item:
            return
        cols = list(self.df.columns)
        col_name = 'Konec A' if 'Konec A' in cols else cols[0]
        col_num = f"#{cols.index(col_name) + 1}"
        self.spawn_inline_entry(self.tree, item, col_num, self.df)

    def show_search_bar(self):
        self.search_bar.pack(side=tk.TOP, fill=tk.X, before=self.paned)
        self.search_entry.focus_set()
        self.search_entry.bind("<Escape>", lambda e: self.hide_search_bar())
    def hide_search_bar(self): self.search_bar.pack_forget()
    def perform_search(self):
        q = self.search_entry.get().lower(); self.search_results = [i for i in self.tree.get_children() if any(q in str(v).lower() for v in self.tree.item(i)['values'])] if q else []; self.search_index = 0 if self.search_results else -1; self.update_search_ui()
    def navigate_search(self, d):
        if self.search_results: self.search_index = (self.search_index + d) % len(self.search_results); self.update_search_ui()
    def update_search_ui(self):
        if self.search_index != -1: i = self.search_results[self.search_index]; self.tree.selection_set(i); self.tree.see(i); self.lbl_search_count.config(text=f"{self.search_index+1}/{len(self.search_results)}")
        else: self.lbl_search_count.config(text="0/0")