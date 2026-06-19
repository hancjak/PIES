import tkinter as tk
from tkinter import filedialog, ttk
import os, sys, pandas as pd, configparser, datetime

from modules.editor import KabelovyEditor
from modules.diff_tool import DiffApp
from core.analysis import analyze_raw_data
from core.style import THEME, apply_ttk_styles
from core.updater import check_for_updates

SYSTEM_NAME = "PIES"
CURRENT_VERSION = "v13.6"
CONFIG_FILE = 'config.ini'

class PIES_Main(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{SYSTEM_NAME} {CURRENT_VERSION}")
        self.geometry("1600x900")
        self.configure(bg=THEME["bg"])
        
        # Menu Bar barvy (Windows ji přebírá částečně)
        self.option_add('*Menu.background', THEME["bg"])
        self.option_add('*Menu.foreground', THEME["fg"])
        self.option_add('*Menu.activeBackground', THEME["fg"])
        self.option_add('*Menu.activeForeground', THEME["bg"])

        self.config_parser = configparser.ConfigParser()
        self.server_path = self.get_server_path()
        self.server_sklad = os.path.join(self.server_path, "seznam_vodicu.csv") if self.server_path else ""
        
        apply_ttk_styles(ttk.Style())
        self.create_menu()
        self.workspace = tk.Frame(self, bg=THEME["bg"])
        self.workspace.pack(fill=tk.BOTH, expand=True)
        self.setup_logging()
        self.show_welcome_screen()

        self.bind("<Control-s>", lambda e: self.action_save())
        self.bind("<Control-f>", lambda e: self.action_search())
        self.bind("<Control-n>", lambda e: self.action_add_row())
        self.bind("<Control-p>", lambda e: self.action_print())

        # Kontrola aktualizací (jen v .exe, na pozadí, neblokuje start)
        self.after(1500, lambda: check_for_updates(CURRENT_VERSION, self, self.log))

    def get_server_path(self):
        if os.path.exists(CONFIG_FILE):
            try:
                config = configparser.ConfigParser()
                config.read(CONFIG_FILE)
                return config.get('PATHS', 'server_path', fallback="")
            except: return ""
        return ""

    def get_initial_dir(self):
        """Vrátí nejlepší výchozí složku pro file dialog: poslední cesta → server → Downloads."""
        if os.path.exists(CONFIG_FILE):
            try:
                config = configparser.ConfigParser()
                config.read(CONFIG_FILE)
                last = config.get('PATHS', 'last_path', fallback="")
                if last and os.path.exists(last):
                    return last
            except: pass
        if self.server_path and os.path.exists(self.server_path):
            return self.server_path
        return os.path.expanduser("~/Downloads")

    def save_last_path(self, filepath):
        directory = os.path.dirname(filepath) if os.path.isfile(filepath) else filepath
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
        if 'PATHS' not in config:
            config['PATHS'] = {}
        config['PATHS']['last_path'] = directory
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)

    def change_server_path(self):
        new_path = filedialog.askdirectory(title="VYBERTE SLOŽKU NA SERVERU")
        if new_path:
            self.server_path = new_path
            self.server_sklad = os.path.join(new_path, "seznam_vodicu.csv")
            config = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE)
            if 'PATHS' not in config:
                config['PATHS'] = {}
            config['PATHS']['server_path'] = new_path
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
            self.log(f"Cesta k serveru změněna: {new_path}")
        self._refresh_server_status()

    def _refresh_server_status(self):
        if not hasattr(self, '_lbl_srv_status') or not self._lbl_srv_status.winfo_exists(): return
        path_text = self.server_path if self.server_path else "(nenastaveno)"
        if self.server_path and os.path.exists(self.server_path):
            self._lbl_srv_status.config(text="● PŘIPOJEN", fg="#00FF44")
        elif self.server_path:
            self._lbl_srv_status.config(text="● NEDOSTUPNÝ", fg="#FF3333")
            self.log(f"VAROVÁNÍ: Server není přístupný — {self.server_path}")
        else:
            self._lbl_srv_status.config(text="● NENASTAVENO", fg=THEME["fg_dim"])
        self._lbl_srv_path.config(text=path_text)

    def ensure_sklad_path(self):
        if not self.server_sklad or not os.path.exists(self.server_sklad):
            f = filedialog.askopenfilename(title="VYBERTE SEZNAM VODIČŮ (SKLAD)", filetypes=[("CSV", "*.csv")])
            if f:
                self.server_sklad = f
                return True
            return False
        return True

    def setup_logging(self):
        self.log_frame = tk.Frame(self, height=100, bg=THEME["bg"])
        self.log_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.log_text = tk.Text(self.log_frame, height=4, bg="#050505", fg=THEME["fg"], 
                                font=(THEME["font_main"][0], 9), borderwidth=0, state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        sb = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log_text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=sb.set)

    def log(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{ts}] > {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def show_welcome_screen(self):
        self.clear_workspace()

        outer = tk.Frame(self.workspace, bg=THEME["bg"])
        outer.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(outer, text="PIES", font=("Consolas", 72, "bold"),
                 fg=THEME["accent"], bg=THEME["bg"]).pack(pady=(0, 4))
        tk.Label(outer, text=CURRENT_VERSION, font=("Consolas", 13),
                 fg=THEME["fg_dim"], bg=THEME["bg"]).pack(pady=(0, 36))

        btn_row = tk.Frame(outer, bg=THEME["bg"])
        btn_row.pack(pady=(0, 30))
        btn_cfg = dict(bg=THEME["dark_grey"], fg=THEME["fg"],
                       font=("Consolas", 12, "bold"), relief=tk.FLAT,
                       activebackground=THEME["fg_dim"], activeforeground=THEME["accent"],
                       cursor="hand2", width=24, height=4)
        tk.Button(btn_row, text="[ NOVÝ PROJEKT ]\nImport EPLAN",
                  command=self.action_new_project, **btn_cfg).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_row, text="[ OTEVŘÍT PROJEKT ]\nUložený CSV",
                  command=self.action_open_project, **btn_cfg).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_row, text="[ DIFF TOOL ]\nPorovnat verze",
                  command=self.action_diff, **btn_cfg).pack(side=tk.LEFT, padx=8)

        srv = tk.LabelFrame(outer, text=" SERVER ", bg=THEME["bg"], fg=THEME["accent"],
                            font=("Consolas", 10, "bold"), borderwidth=1, relief=tk.GROOVE,
                            padx=20, pady=12)
        srv.pack(fill=tk.X)

        row1 = tk.Frame(srv, bg=THEME["bg"])
        row1.pack(fill=tk.X, pady=(0, 8))
        self._lbl_srv_status = tk.Label(row1, font=("Consolas", 11, "bold"), bg=THEME["bg"])
        self._lbl_srv_status.pack(side=tk.LEFT, padx=(0, 14))
        self._lbl_srv_path = tk.Label(row1, font=("Consolas", 9), bg=THEME["bg"], fg="#44AA44")
        self._lbl_srv_path.pack(side=tk.LEFT)

        tk.Button(srv, text="[ Změnit cestu ]", command=self.change_server_path,
                  bg=THEME["dark_grey"], fg=THEME["fg"], font=("Consolas", 10),
                  relief=tk.FLAT, cursor="hand2").pack()

        self._refresh_server_status()

    def clear_workspace(self):
        self.current_module = None
        for w in self.workspace.winfo_children(): w.destroy()

    def create_menu(self):
        m = tk.Menu(self, bg=THEME["bg"], fg=THEME["fg"])
        f = tk.Menu(m, tearoff=0, bg=THEME["bg"], fg=THEME["fg"])
        f.add_command(label="Open Project", command=self.action_open_project)
        f.add_command(label="Save (Ctrl+S)", command=self.action_save)
        m.add_cascade(label="File", menu=f)
        
        t = tk.Menu(m, tearoff=0, bg=THEME["bg"], fg=THEME["fg"])
        t.add_command(label="Import EPLAN", command=self.action_new_project)
        t.add_command(label="Diff Tool", command=self.action_diff)
        t.add_command(label="Search (Ctrl+F)", command=self.action_search)
        t.add_command(label="Print (Ctrl+P)", command=self.action_print)
        t.add_separator()
        t.add_command(label="Změnit cestu serveru", command=self.change_server_path)
        m.add_cascade(label="Tools", menu=t)
        self.config(menu=m)

    def action_new_project(self):
        if not self.ensure_sklad_path(): return
        idir = self.get_initial_dir()
        fc = filedialog.askopenfilenames(title="LINES", initialdir=idir, filetypes=[("CSV", "*.csv")])
        fs = filedialog.askopenfilenames(title="SIGNALS", initialdir=idir, filetypes=[("CSV", "*.csv")])
        if fc and fs:
            p = filedialog.asksaveasfilename(title="SAVE PROJECT", initialdir=idir, filetypes=[("CSV", "*.csv")])
            if p:
                self.save_last_path(p)
                self.clear_workspace()
                df_k = analyze_raw_data(fc, fs)
                df_s = pd.read_csv(self.server_sklad, encoding='cp1250')
                self.current_module = KabelovyEditor(self.workspace, df_k, df_s, p, self.log, self.server_sklad)

    def action_open_project(self):
        if not self.ensure_sklad_path(): return
        f = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")], initialdir=self.get_initial_dir())
        if f:
            self.save_last_path(f)
            self.clear_workspace()
            df_k = pd.read_csv(f, encoding='cp1250')
            df_s = pd.read_csv(self.server_sklad, encoding='cp1250')
            self.current_module = KabelovyEditor(self.workspace, df_k, df_s, f, self.log, self.server_sklad)

    def action_save(self):
        if self.current_module: self.current_module.save_project()
    def action_search(self):
        if self.current_module: self.current_module.show_search_bar()
    def action_add_row(self):
        if self.current_module: self.current_module.add_new_label_row()
    def action_print(self):
        if self.current_module: self.current_module.print_labels()
    def action_diff(self):
        self.clear_workspace(); self.current_module = DiffApp(self.workspace, self.log)

if __name__ == "__main__":
    app = PIES_Main(); app.mainloop()