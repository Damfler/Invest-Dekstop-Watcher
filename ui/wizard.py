"""
wizard.py — мастер первого запуска.
Показывается когда токен не введён.
"""
import os
import sys
import json
import logging
import webbrowser
import threading
from tkinter import filedialog

log = logging.getLogger("tbank.wizard")

from version import APP_VERSION, APP_NAME
from constants import TOKEN_STUB, BROKERS, BROKER_INFO, GITHUB_REPO

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)), "InvestDesktopWatcher")
    _PROJ_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _PROJ_DIR = BASE_DIR
os.makedirs(BASE_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def needs_wizard(cfg: dict) -> bool:
    connections = cfg.get("connections", [])
    if not connections:
        return True
    return all(
        not c.get("token") or c.get("token") == TOKEN_STUB
        for c in connections
    )


def run_wizard() -> str | None:
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        log.error("tkinter недоступен — введите токен вручную в config.json")
        return None

    result = {"token": None}

    # ── Темы ─────────────────────────────────────────────────────────────────
    THEMES = {
        "dark":  {"BG": "#1c1c1e", "BG2": "#2c2c2e", "SURFACE": "#3a3a3c",
                  "BORDER": "#48484a", "TEXT": "#f2f2f7", "MUTED": "#8e8e93"},
        "light": {"BG": "#f0f0f5", "BG2": "#ffffff", "SURFACE": "#e8e8ed",
                  "BORDER": "#c7c7cc", "TEXT": "#000000", "MUTED": "#48484a"},
    }
    PINK = "#ff2d55"
    BLUE = "#0a84ff"
    RED  = "#ff453a"
    GREEN = "#30d158"

    def _is_system_light():
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return val == 1
        except Exception:
            return False

    cur = {"theme": "light" if _is_system_light() else "dark"}

    def C(k):
        return THEMES[cur["theme"]][k]

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("500x700")
    root.resizable(False, False)
    root.configure(bg=C("BG"))
    root.attributes("-topmost", True)

    # Иконка приложения
    _ico = os.path.join(_PROJ_DIR, "assets", "icons", "icon.ico")
    if not os.path.exists(_ico):
        _ico = os.path.join(_PROJ_DIR, "icons", "icon.ico")
    if os.path.exists(_ico):
        try:
            root.iconbitmap(_ico)
        except Exception:
            pass

    # ── Перекрашивание ────────────────────────────────────────────────────────
    _roles = {}  # id(widget) → "bg"|"bg2"|"card"|"surface"

    def _repaint(w):
        role = _roles.get(id(w))
        cls = w.winfo_class()
        try:
            if role == "bg2":
                w.config(bg=C("BG2"))
            elif role == "card":
                w.config(bg=C("BG2"), highlightbackground=C("BORDER"))
            elif role == "surface":
                w.config(bg=C("SURFACE"), fg=C("MUTED"), activebackground=C("BORDER"), activeforeground=C("TEXT"))
            elif cls == "Frame":
                w.config(bg=C("BG") if role != "bg2" else C("BG2"))
            elif cls == "Label":
                pr = _roles.get(id(w.master))
                pbg = C("BG2") if pr in ("bg2", "card") else C("BG")
                fg = w.cget("fg")
                if fg in (THEMES["dark"]["TEXT"], THEMES["light"]["TEXT"]):
                    w.config(fg=C("TEXT"), bg=pbg)
                elif fg in (THEMES["dark"]["MUTED"], THEMES["light"]["MUTED"]):
                    w.config(fg=C("MUTED"), bg=pbg)
                elif fg in (THEMES["dark"]["BORDER"], THEMES["light"]["BORDER"]):
                    w.config(fg=C("BORDER"), bg=pbg)
                elif fg == BLUE:
                    w.config(bg=pbg)
                elif fg in (RED, GREEN):
                    w.config(bg=pbg if pr not in ("bg2", "card") else C("BG"))
                else:
                    w.config(bg=pbg)
            elif cls == "Button" and w.cget("bg") not in (PINK, "#e6264d"):
                if str(w.cget("state")) == "disabled":
                    w.config(bg=C("BG2"), disabledforeground=C("BORDER"), highlightbackground=C("BORDER"))
        except Exception:
            pass
        for ch in w.winfo_children():
            _repaint(ch)

    def _apply_theme():
        root.configure(bg=C("BG"))
        style.configure(".", background=C("BG"), foreground=C("TEXT"), bordercolor=C("BORDER"),
                        fieldbackground=C("BG2"), insertcolor=C("TEXT"))
        style.configure("TFrame", background=C("BG"))
        style.configure("TCheckbutton", background=C("BG"), foreground=C("TEXT"))
        style.map("TCheckbutton", background=[("active", C("BG"))], foreground=[("active", C("TEXT"))])
        style.configure("Tok.TEntry", fieldbackground=C("SURFACE"), foreground=C("TEXT"),
                        insertcolor=C("TEXT"), bordercolor=C("BORDER"))
        _repaint(root)
        theme_btn.config(text="\u2600" if cur["theme"] == "dark" else "\u263d",
                         bg=C("BG2"), fg=C("TEXT"), activebackground=C("SURFACE"))

    def _toggle_theme():
        cur["theme"] = "light" if cur["theme"] == "dark" else "dark"
        _apply_theme()

    # ── Стили ────────────────────────────────────────────────────────────────
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=C("BG"), foreground=C("TEXT"),
                    font=("Segoe UI", 10), bordercolor=C("BORDER"),
                    fieldbackground=C("BG2"), insertcolor=C("TEXT"))
    style.configure("TFrame", background=C("BG"))
    style.configure("TCheckbutton", background=C("BG"), foreground=C("TEXT"), font=("Segoe UI", 10))
    style.map("TCheckbutton", background=[("active", C("BG"))], foreground=[("active", C("TEXT"))])
    style.configure("Tok.TEntry", fieldbackground=C("SURFACE"), foreground=C("TEXT"),
                    insertcolor=C("TEXT"), selectbackground=BLUE, selectforeground="#fff",
                    bordercolor=C("BORDER"), font=("Consolas", 10), padding=(8, 8))
    style.map("Tok.TEntry", bordercolor=[("focus", BLUE)], lightcolor=[("focus", BLUE)])
    # Стиль для невалидного поля
    style.configure("Invalid.TEntry", fieldbackground="#3a2020", bordercolor=RED)
    style.map("Invalid.TEntry", bordercolor=[("focus", RED)])

    # ── Контейнер ────────────────────────────────────────────────────────────
    wrap = tk.Frame(root, bg=C("BG"))
    wrap.pack(fill="both", expand=True, padx=28, pady=16)

    # ── Header ───────────────────────────────────────────────────────────────
    hdr = tk.Frame(wrap, bg=C("BG"))
    hdr.pack(fill="x")
    tk.Label(hdr, text=APP_NAME, fg=C("TEXT"), bg=C("BG"),
             font=("Segoe UI", 20, "bold")).pack(side="left")
    theme_btn = tk.Button(hdr, text="\u2600" if cur["theme"] == "dark" else "\u263d",
                          bg=C("BG2"), fg=C("TEXT"), relief="flat",
                          font=("Segoe UI", 14), cursor="hand2", padx=6, pady=2, bd=0,
                          activebackground=C("SURFACE"), command=_toggle_theme)
    theme_btn.pack(side="right")
    tk.Label(wrap, text=f"v{APP_VERSION}", fg=C("BORDER"), bg=C("BG"),
             font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 2))
    tk.Label(wrap, text="Портфель, облигации, купоны, аналитика \u2014 всё в трее",
             fg=C("MUTED"), bg=C("BG"), font=("Segoe UI", 10)).pack(anchor="w")
    tk.Frame(wrap, bg=C("BORDER"), height=1).pack(fill="x", pady=12)

    # ── 1. Брокер ────────────────────────────────────────────────────────────
    tk.Label(wrap, text="1. Выберите брокера", fg=C("TEXT"), bg=C("BG"),
             font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))

    broker_var = tk.StringVar(value=list(BROKERS.keys())[0])
    broker_btns = {}
    bc = tk.Frame(wrap, bg=C("BG"))
    bc.pack(fill="x", pady=(0, 10))

    COLS = 3
    supported = {"tbank"}

    def _sel_broker(key):
        broker_var.set(key)
        for k, b in broker_btns.items():
            if k == key:
                b.config(bg=PINK, fg="#fff", highlightbackground=PINK)
            else:
                s = k in supported
                b.config(bg=C("SURFACE") if s else C("BG2"),
                         fg=C("TEXT") if s else C("BORDER"), highlightbackground=C("BORDER"))
        info = BROKER_INFO.get(key, BROKER_INFO["tbank"])
        tok_title.config(text=info["token_label"])
        tok_hint.config(text=info["hint"])
        tok_link.config(text=info["api_label"])
        tok_link.bind("<Button-1>", lambda e: webbrowser.open(info["api_url"]))

    if getattr(sys, 'frozen', False):
        items = [(k, v) for k, v in BROKERS.items() if k in supported]
    else:
        items = list(BROKERS.items())

    _tooltip_win = [None]

    def _show_tooltip(widget, text):
        def enter(e):
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{e.x_root+10}+{e.y_root+10}")
            tk.Label(tw, text=text, bg="#333", fg="#fff", font=("Segoe UI", 9),
                     padx=8, pady=4, relief="solid", bd=1).pack()
            _tooltip_win[0] = tw
        def leave(e):
            if _tooltip_win[0]:
                _tooltip_win[0].destroy()
                _tooltip_win[0] = None
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    rf = None
    for i, (key, name) in enumerate(items):
        if i % COLS == 0:
            rf = tk.Frame(bc, bg=C("BG"))
            rf.pack(fill="x", pady=(0, 3))
        act = key in supported
        sel = i == 0 and act
        btn = tk.Button(rf, text=name if act else f"{name} (скоро)", relief="flat",
                        font=("Segoe UI", 9), cursor="hand2" if act else "arrow",
                        width=13, height=1, bd=0, pady=8,
                        bg=PINK if sel else C("SURFACE") if act else C("BG2"),
                        fg="#fff" if sel else C("TEXT") if act else C("BORDER"),
                        activebackground=PINK if act else C("BG2"),
                        activeforeground="#fff" if act else C("BORDER"),
                        highlightbackground=PINK if sel else C("BORDER"), highlightthickness=1,
                        state="normal" if act else "disabled", disabledforeground=C("BORDER"),
                        command=lambda k=key: _sel_broker(k))
        btn.pack(side="left", fill="x", expand=True, padx=(0 if i % COLS == 0 else 3, 0))
        broker_btns[key] = btn
        if not act:
            _show_tooltip(btn, "Поддержка в разработке")

    # ── 2. Токен ─────────────────────────────────────────────────────────────
    tk.Label(wrap, text="2. Введите API-токен", fg=C("TEXT"), bg=C("BG"),
             font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))

    card = tk.Frame(wrap, bg=C("BG2"), highlightbackground=C("BORDER"), highlightthickness=1, bd=0)
    card.pack(fill="x")
    _roles[id(card)] = "card"
    ci = tk.Frame(card, bg=C("BG2"))
    ci.pack(fill="x", padx=14, pady=12)
    _roles[id(ci)] = "bg2"

    di = BROKER_INFO[broker_var.get()]
    tok_title = tk.Label(ci, text=di["token_label"], fg=C("TEXT"), bg=C("BG2"), font=("Segoe UI", 10, "bold"))
    tok_title.pack(anchor="w")
    tok_hint = tk.Label(ci, text=di["hint"], fg=C("MUTED"), bg=C("BG2"), font=("Segoe UI", 9), justify="left")
    tok_hint.pack(anchor="w", pady=(2, 6))
    tok_link = tk.Label(ci, text=di["api_label"], fg=BLUE, bg=C("BG2"), cursor="hand2",
                        font=("Segoe UI", 9, "underline"))
    tok_link.pack(anchor="w", pady=(0, 8))
    tok_link.bind("<Button-1>", lambda e: webbrowser.open(BROKER_INFO[broker_var.get()]["api_url"]))

    # Поле ввода + кнопки
    token_var = tk.StringVar()
    ef = tk.Frame(ci, bg=C("BG2"))
    ef.pack(fill="x")
    _roles[id(ef)] = "bg2"

    entry = ttk.Entry(ef, textvariable=token_var, style="Tok.TEntry", font=("Consolas", 10))
    entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 4))
    entry.config(show="\u2022")

    # Реалтайм валидация
    def _on_token_change(*_):
        val = token_var.get().strip()
        if val and len(val) < 10:
            entry.config(style="Invalid.TEntry")
        else:
            entry.config(style="Tok.TEntry")
    token_var.trace_add("write", _on_token_change)

    show_pwd = {"v": False}
    def _toggle_vis():
        show_pwd["v"] = not show_pwd["v"]
        entry.config(show="" if show_pwd["v"] else "\u2022")
        eye_btn.config(text="Hide" if show_pwd["v"] else "Show")

    _btn_s = {"bg": C("SURFACE"), "fg": C("MUTED"), "relief": "flat", "font": ("Segoe UI", 8),
              "cursor": "hand2", "bd": 0, "activebackground": C("BORDER"), "activeforeground": C("TEXT")}

    def _do_paste():
        try:
            txt = root.clipboard_get().strip()
            if txt:
                token_var.set(txt)
                entry.icursor(tk.END)
        except tk.TclError:
            pass

    paste_btn = tk.Button(ef, text="Вставить", command=_do_paste, padx=6, pady=4, **_btn_s)
    paste_btn.pack(side="left", fill="y", padx=(0, 2))
    _roles[id(paste_btn)] = "surface"

    eye_btn = tk.Button(ef, text="Show", command=_toggle_vis, padx=6, pady=4, **_btn_s)
    eye_btn.pack(side="left", fill="y")
    _roles[id(eye_btn)] = "surface"

    # Ctrl+V через keycode
    def _on_key(e):
        if e.state & 0x4 and e.keycode == 86:
            _do_paste()
            return "break"
    root.bind("<Key>", _on_key)
    entry.bind("<Key>", _on_key)
    entry.bind("<Button-3>", lambda e: (
        m := tk.Menu(root, tearoff=0, bg=C("BG2"), fg=C("TEXT"), activebackground=BLUE,
                     activeforeground="#fff", font=("Segoe UI", 10)),
        m.add_command(label="Вставить", command=_do_paste),
        m.add_command(label="Очистить", command=lambda: token_var.set("")),
        m.tk_popup(e.x_root, e.y_root),
    ))

    # ── Импорт конфига ───────────────────────────────────────────────────────
    def _import_config():
        path = filedialog.askopenfilename(title="Импорт config.json",
                                          filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
            import shutil
            shutil.copy2(path, CONFIG_FILE)
            # Извлекаем токен
            conns = cfg.get("connections", [])
            if conns:
                tok = conns[0].get("token", "")
                if tok and tok != TOKEN_STUB:
                    token_var.set(tok)
                    status_var.set("Конфиг импортирован!")
                    status_lbl.config(fg=GREEN)
                    return
            # Старый формат
            tok = cfg.get("token", "")
            if tok and tok != TOKEN_STUB:
                token_var.set(tok)
                status_var.set("Конфиг импортирован!")
                status_lbl.config(fg=GREEN)
                return
            status_var.set("Конфиг импортирован, но токен не найден")
            status_lbl.config(fg=C("MUTED"))
        except Exception as e:
            status_var.set(f"Ошибка импорта: {e}")
            status_lbl.config(fg=RED)

    # TODO: раскомментировать когда будет готов полноценный импорт/экспорт
    # import_link = tk.Label(wrap, text="Уже есть config.json? Импортировать",
    #                        fg=BLUE, bg=C("BG"), cursor="hand2", font=("Segoe UI", 9, "underline"))
    # import_link.pack(anchor="w", pady=(6, 0))
    # import_link.bind("<Button-1>", lambda e: _import_config())

    # ── Автозапуск ───────────────────────────────────────────────────────────
    auto_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(wrap, text="Запускать вместе с Windows",
                    variable=auto_var).pack(anchor="w", pady=(8, 0))

    # ── Статус ───────────────────────────────────────────────────────────────
    status_var = tk.StringVar()
    status_lbl = tk.Label(wrap, textvariable=status_var, fg=RED, bg=C("BG"),
                          font=("Segoe UI", 9), wraplength=440, justify="left")
    status_lbl.pack(anchor="w", pady=(4, 0))

    # ── Спиннер ──────────────────────────────────────────────────────────────
    spinner = {"active": False, "frames": ["\u25dc", "\u25dd", "\u25de", "\u25df"], "idx": 0}

    def _spin():
        if not spinner["active"]:
            return
        spinner["idx"] = (spinner["idx"] + 1) % 4
        status_var.set(f"{spinner['frames'][spinner['idx']]} Проверяю подключение...")
        root.after(150, _spin)

    # ── Кнопки ───────────────────────────────────────────────────────────────
    bf = tk.Frame(wrap, bg=C("BG"))
    bf.pack(fill="x", pady=(10, 0))

    def _submit(event=None):
        tok = token_var.get().strip()
        if not tok:
            status_var.set("Введите или вставьте токен")
            status_lbl.config(fg=RED)
            entry.focus_force()
            return
        if len(tok) < 10:
            status_var.set("Токен слишком короткий")
            status_lbl.config(fg=RED)
            entry.focus_force()
            return

        # Спиннер
        spinner["active"] = True
        status_lbl.config(fg=C("MUTED"))
        _spin()
        start_btn.config(text="Проверяю...", bg="#99173a", fg="#ffb3c4")
        root.update()

        def _check():
            try:
                from api.client import TBankAPI
                api = TBankAPI(tok)
                accounts = api.get_accounts()
                spinner["active"] = False
                if not accounts:
                    root.after(0, lambda: (status_var.set("Токен принят, но счета не найдены"),
                                           status_lbl.config(fg=RED), start_btn.config(text="Начать работу", bg=PINK, fg="#fff")))
                    return
                root.after(0, lambda: _save(tok, len(accounts)))
            except Exception as e:
                spinner["active"] = False
                root.after(0, lambda: (status_var.set(f"Ошибка: {str(e)[:80]}"),
                                       status_lbl.config(fg=RED), start_btn.config(text="Начать работу", bg=PINK, fg="#fff")))

        threading.Thread(target=_check, daemon=True).start()

    def _save(tok, n_accounts):
        status_var.set(f"\u2713 Найдено счетов: {n_accounts}")
        status_lbl.config(fg=GREEN)
        root.update()
        result["token"] = tok
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    cfg = json.load(f)
            else:
                from core.config import DEFAULT_CONFIG
                cfg = dict(DEFAULT_CONFIG)
            conn = {
                "name":   list(BROKERS.values())[list(BROKERS.keys()).index(broker_var.get())],
                "broker": broker_var.get(), "token": tok, "enabled": True, "use_sandbox": False,
            }
            existing = cfg.get("connections", [])
            if existing:
                existing[0] = conn
            else:
                existing = [conn]
            cfg["connections"] = existing
            cfg.pop("token", None)
            cfg.pop("broker", None)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            status_var.set(f"Ошибка: {e}")
            status_lbl.config(fg=RED)
            start_btn.config(text="Начать работу", bg=PINK, fg="#fff")
            return
        if auto_var.get():
            try:
                from utils import autostart
                autostart.enable()
            except Exception:
                pass
        root.after(500, root.destroy)

    _bf = ("Segoe UI", 10, "bold")
    start_btn = tk.Button(bf, text="Начать работу", command=_submit,
                          bg=PINK, fg="#fff", relief="flat", font=_bf, cursor="hand2",
                          padx=20, pady=10, bd=0, activebackground="#e6264d", activeforeground="#fff")
    start_btn.pack(side="left", fill="y")
    tk.Button(bf, text="Выйти", command=root.destroy,
              bg=C("SURFACE"), fg=C("MUTED"), relief="flat", font=_bf, cursor="hand2",
              padx=20, pady=10, bd=0, activebackground=C("BORDER"), activeforeground=C("TEXT")
              ).pack(side="left", padx=(8, 0), fill="y")

    # ── Footer ───────────────────────────────────────────────────────────────
    footer = tk.Frame(wrap, bg=C("BG"))
    footer.pack(fill="x", side="bottom", pady=(8, 0))
    tk.Label(footer, text=f"{APP_NAME} v{APP_VERSION}", fg=C("BORDER"), bg=C("BG"),
             font=("Segoe UI", 8)).pack(side="left")
    gh = tk.Label(footer, text="GitHub", fg=BLUE, bg=C("BG"), cursor="hand2",
                  font=("Segoe UI", 8, "underline"))
    gh.pack(side="right")
    gh.bind("<Button-1>", lambda e: webbrowser.open(f"https://github.com/{GITHUB_REPO}"))

    # ── Bindings ─────────────────────────────────────────────────────────────
    root.bind("<Return>", _submit)
    root.bind("<Escape>", lambda e: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)

    def _focus():
        root.attributes("-topmost", False)
        root.lift()
        root.focus_force()
        entry.focus_set()

    root.after(150, _focus)
    root.mainloop()
    return result["token"]
