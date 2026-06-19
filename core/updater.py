"""Auto-updater proti GitHub Releases veřejného repa (hancjak/PIES).

Při startu .exe na pozadí zkontroluje poslední release. Když je novější,
zeptá se uživatele a po potvrzení stáhne instalátor (PIES_Setup_*.exe),
přičemž ukáže okno s průběhem stahování. Pak instalátor spustí v tichém
režimu (s progress oknem Inno Setup) a ukončí aplikaci, aby ji instalátor
mohl přepsat a znovu spustit.

Běh ze zdrojáku se přeskakuje, síťové chyby jsou tiché a neblokují start.
"""
import sys, os, re, subprocess, threading, tempfile
import tkinter as tk
from tkinter import ttk, messagebox

GITHUB_REPO = "hancjak/PIES"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(tag):
    """'v13.8' -> (13, 8); nečíselné -> (0,)."""
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums) if nums else (0,)


def check_for_updates(current_version, parent, log=None):
    """Spustit po startu GUI. Kontrola běží na pozadí, ať neblokuje okno."""
    if not getattr(sys, "frozen", False):
        return  # běží ze zdrojáku — není co instalovat
    threading.Thread(target=_worker, args=(current_version, parent, log),
                     daemon=True).start()


def _worker(current_version, parent, log):
    try:
        import requests
        data = requests.get(API_LATEST, timeout=5).json()
    except Exception as e:
        if log:
            parent.after(0, lambda: log(f"Kontrola aktualizací selhala: {e}"))
        return

    latest = data.get("tag_name", "")
    if _parse_version(latest) <= _parse_version(current_version):
        return  # máme aktuální verzi

    assets = data.get("assets", [])
    # preferuj instalátor (PIES_Setup_*.exe), jinak jakýkoli .exe
    asset = next((a for a in assets
                  if a.get("name", "").lower().endswith(".exe")
                  and "setup" in a.get("name", "").lower()), None)
    asset = asset or next((a for a in assets
                           if a.get("name", "").lower().endswith(".exe")), None)
    if not asset:
        return
    url = asset["browser_download_url"]
    size = asset.get("size", 0)
    parent.after(0, lambda: _prompt(latest, url, size, parent, log))


def _prompt(latest, url, size, parent, log):
    if not messagebox.askyesno(
            "PIES – Aktualizace",
            f"Je dostupná nová verze {latest}.\n\n"
            f"Stáhnout a nainstalovat? Aplikace se po dokončení sama restartuje."):
        return
    UpdateWindow(parent, latest, url, size, log)


class UpdateWindow(tk.Toplevel):
    """Okno s průběhem stahování instalátoru a logem, aby uživatel viděl, co se děje."""

    def __init__(self, parent, version, url, size, log):
        super().__init__(parent)
        self.url, self.size, self.app_log = url, size, log
        self.title("PIES – Aktualizace")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # nezavírat během stahování

        tk.Label(self, text=f"Stahuji novou verzi {version}…",
                 font=("Consolas", 11, "bold")).pack(padx=20, pady=(16, 8))
        self.pb = ttk.Progressbar(self, length=380, mode="determinate",
                                  maximum=max(size, 1))
        self.pb.pack(padx=20)
        self.lbl = tk.Label(self, text="Připojuji se…", font=("Consolas", 9))
        self.lbl.pack(pady=(4, 8))
        self.txt = tk.Text(self, height=6, width=56, font=("Consolas", 8),
                           state="disabled", bg="#050505", fg="#cccccc", borderwidth=0)
        self.txt.pack(padx=20, pady=(0, 16))

        self._log("Spouštím stahování instalátoru…")
        threading.Thread(target=self._download, daemon=True).start()

    def _log(self, msg):
        if not self.winfo_exists():
            return
        self.txt.config(state="normal")
        self.txt.insert("end", msg + "\n")
        self.txt.see("end")
        self.txt.config(state="disabled")

    def _download(self):
        try:
            import requests
            dest = os.path.join(tempfile.gettempdir(), "PIES_Setup.exe")
            done = 0
            with requests.get(self.url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        self.after(0, self._progress, done)
            self.after(0, self._finished, dest)
        except Exception as e:
            self.after(0, self._failed, e)

    def _progress(self, done):
        if not self.winfo_exists():
            return
        self.pb["value"] = done
        if self.size:
            self.lbl.config(text=f"{int(done * 100 / self.size)} %   "
                                 f"({done // 1048576} / {self.size // 1048576} MB)")
        else:
            self.lbl.config(text=f"{done // 1048576} MB")

    def _finished(self, dest):
        self._log("Staženo. Spouštím instalátor…")
        try:
            # /SILENT = jen progress okno bez klikání; /CLOSEAPPLICATIONS = zavře běžící PIES
            subprocess.Popen([dest, "/SILENT", "/CLOSEAPPLICATIONS"])
        except Exception as e:
            self._failed(e)
            return
        if self.app_log:
            self.app_log("Spuštěn instalátor aktualizace, ukončuji aplikaci.")
        os._exit(0)  # tvrdé ukončení — uvolní .exe, aby ho instalátor mohl přepsat

    def _failed(self, e):
        self._log(f"CHYBA: {e}")
        messagebox.showerror("PIES", f"Aktualizace selhala:\n{e}")
        self.destroy()
