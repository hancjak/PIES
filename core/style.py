# core/style.py

THEME = {
    "bg": "#000000",
    "bg_alt": "#0A1A0A",      
    "fg": "#00FF00",          
    "fg_dim": "#005500",      # Ještě trochu tmavší pro lepší kontrast s oranžovou
    "accent": "#FF8C00",      
    "dark_grey": "#111111",   
    "font_main": ("Consolas", 10),
    "font_big": ("Consolas", 100, "bold"),
    "row_height": 30
}

def apply_ttk_styles(style):
    style.theme_use('clam')
    
    # Tabulky
    style.configure("Treeview", 
                    background=THEME["bg"], 
                    foreground=THEME["fg"], 
                    fieldbackground=THEME["bg"],
                    rowheight=THEME["row_height"],
                    font=THEME["font_main"],
                    borderwidth=0)
    
    style.map("Treeview", 
              background=[('selected', THEME["fg_dim"])], 
              foreground=[('selected', THEME["accent"])])

    style.configure("Treeview.Heading", 
                    background=THEME["dark_grey"], 
                    foreground=THEME["accent"], 
                    font=(THEME["font_main"][0], 10, "bold"),
                    borderwidth=1,
                    relief="flat")

    # Scrollbar
    style.configure("Vertical.TScrollbar", 
                    background=THEME["fg_dim"], 
                    troughcolor=THEME["bg"],
                    bordercolor=THEME["bg"],
                    arrowcolor=THEME["fg"])
    
    # Paned Window - ZABITÍ BÍLÝCH LIŠT
    style.configure("TPanedwindow", background=THEME["bg"])
    style.configure("Sash", background=THEME["dark_grey"], sashthickness=3)