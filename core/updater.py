"""Jednoduchý auto-updater proti GitHub Releases veřejného repa.

Funguje pouze v sestaveném .exe (PyInstaller). Při běhu ze zdrojáku se
přeskočí. Síťové chyby jsou tiché a nikdy neblokují start aplikace.
"""
import sys, os, re, subprocess, threading
from tkinter import messagebox

GITHUB_REPO = "hancjak/PIES"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(tag):
    """'v13.6' -> (13, 6); nečíselné -> (0,)."""
    nums = re.findall(r"\d+", tag or "")
    return tuple(int(n) for n in nums) if nums else (0,)


def check_for_updates(current_version, parent, log=None):
    """Spustit po startu GUI. Kontrola běží na pozadí, ať neblokuje okno."""
    if not getattr(sys, "frozen", False):
        return  # běží ze zdrojáku — není co nahrazovat
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

    asset = next((a for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith(".exe")), None)
    if not asset:
        return
    url = asset["browser_download_url"]
    parent.after(0, lambda: _prompt_and_update(latest, url, parent, log))


def _prompt_and_update(latest_tag, url, parent, log):
    if not messagebox.askyesno(
            "PIES – Aktualizace",
            f"Je dostupná nová verze {latest_tag}.\n"
            f"Stáhnout a nainstalovat? Aplikace se po stažení restartuje."):
        return
    try:
        import requests
        exe_path = sys.executable
        new_path = exe_path + ".new"
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(new_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
    except Exception as e:
        messagebox.showerror("PIES", f"Stažení aktualizace selhalo:\n{e}")
        return
    if log:
        log(f"Aktualizace {latest_tag} stažena, restartuji…")
    _swap_and_restart(exe_path, new_path, parent)


def _swap_and_restart(exe_path, new_path, parent):
    """Spustí .bat, který počká na ukončení procesu, přepíše .exe a restartuje."""
    bat_path = exe_path + ".update.bat"
    script = (
        "@echo off\r\n"
        ":wait\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        f'del "{exe_path}" 2>nul\r\n'
        f'if exist "{exe_path}" goto wait\r\n'
        f'move /y "{new_path}" "{exe_path}" >nul\r\n'
        f'start "" "{exe_path}"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat_path, "w", encoding="ascii") as f:
        f.write(script)
    subprocess.Popen(["cmd", "/c", bat_path],
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
    parent.destroy()
    sys.exit(0)
