"""
wizard.py — мастер первого запуска.
Показывается когда токен не введён.
Стилизован под дашборд TBank Watcher.
"""
import os
import sys
import json
import logging
import webbrowser

log = logging.getLogger("tbank.wizard")

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)), "TBankWatcher")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
TOKEN_STUB  = "YOUR_TBANK_API_TOKEN_HERE"


def needs_wizard(cfg: dict) -> bool:
    token = cfg.get("token", TOKEN_STUB)
    return not token or token == TOKEN_STUB


def run_wizard() -> str | None:
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        log.error("tkinter недоступен — введите токен вручную в config.json")
        return None

    result = {"token": None}

    # ── Цвета (как в дашборде) ───────────────────────────────────────────────
    BG      = "#1c1c1e"
    BG2     = "#2c2c2e"
    SURFACE = "#3a3a3c"
    BORDER  = "#48484a"
    TEXT    = "#f2f2f7"
    MUTED   = "#8e8e93"
    PINK    = "#ff2d55"
    BLUE    = "#0a84ff"
    GREEN   = "#30d158"
    RED     = "#ff453a"

    root = tk.Tk()
    root.title("TBank Watcher")
    root.geometry("480x520")
    root.resizable(False, False)
    root.configure(bg=BG)
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()

    # ── Стили ────────────────────────────────────────────────────────────────
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=TEXT,
                    font=("Segoe UI", 10), bordercolor=BORDER,
                    fieldbackground=BG2, troughcolor=BG2, insertcolor=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("TCheckbutton", background=BG, foreground=TEXT,
                    font=("Segoe UI", 10))
    style.map("TCheckbutton",
              background=[("active", BG)], foreground=[("active", TEXT)])

    # ── Контейнер с отступами ────────────────────────────────────────────────
    wrap = tk.Frame(root, bg=BG)
    wrap.pack(fill="both", expand=True, padx=28, pady=24)

    # ── Заголовок ────────────────────────────────────────────────────────────
    tk.Label(wrap, text="TBank Watcher", fg=TEXT, bg=BG,
             font=("Segoe UI", 22, "bold")).pack(anchor="w")
    tk.Label(wrap, text="v2.1", fg=BORDER, bg=BG,
             font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 4))
    tk.Label(wrap, text="Виджет для отслеживания инвестиционного портфеля",
             fg=MUTED, bg=BG, font=("Segoe UI", 10)).pack(anchor="w")

    # ── Разделитель ──────────────────────────────────────────────────────────
    tk.Frame(wrap, bg=BORDER, height=1).pack(fill="x", pady=16)

    # ── Карточка ввода токена ────────────────────────────────────────────────
    card = tk.Frame(wrap, bg=BG2, highlightbackground=BORDER,
                    highlightthickness=1, bd=0)
    card.pack(fill="x")
    card_inner = tk.Frame(card, bg=BG2)
    card_inner.pack(fill="x", padx=16, pady=14)

    tk.Label(card_inner, text="API-токен T-Invest", fg=TEXT, bg=BG2,
             font=("Segoe UI", 12, "bold")).pack(anchor="w")
    tk.Label(card_inner,
             text="Только чтение. Создайте в приложении Т-Инвестиции:\nНастройки → Открыть API → Создать токен",
             fg=MUTED, bg=BG2, font=("Segoe UI", 9),
             justify="left").pack(anchor="w", pady=(4, 8))

    # Ссылка
    lnk = tk.Label(card_inner, text="Открыть страницу T-Bank Invest API",
                   fg=BLUE, bg=BG2, cursor="hand2",
                   font=("Segoe UI", 9, "underline"))
    lnk.pack(anchor="w", pady=(0, 10))
    lnk.bind("<Button-1>",
             lambda e: webbrowser.open("https://www.tbank.ru/invest/open-api/"))

    # Поле ввода
    token_var = tk.StringVar()
    show_pwd = {"v": False}

    entry_frame = tk.Frame(card_inner, bg=BG2)
    entry_frame.pack(fill="x")

    style.configure("Tok.TEntry", fieldbackground=SURFACE, foreground=TEXT,
                    insertcolor=TEXT, selectbackground=BLUE,
                    selectforeground="#fff", bordercolor=BORDER,
                    font=("Consolas", 10), padding=(8, 8))
    style.map("Tok.TEntry",
              bordercolor=[("focus", BLUE)],
              lightcolor=[("focus", BLUE)], darkcolor=[("focus", BLUE)])
    entry = ttk.Entry(entry_frame, textvariable=token_var,
                      style="Tok.TEntry", font=("Consolas", 10))
    entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))

    def toggle_vis():
        show_pwd["v"] = not show_pwd["v"]
        entry.config(show="" if show_pwd["v"] else "\u2022")
        eye_btn.config(text="Hide" if show_pwd["v"] else "Show")

    eye_btn = tk.Button(entry_frame, text="Show", command=toggle_vis,
                        bg=SURFACE, fg=MUTED, relief="flat",
                        font=("Segoe UI", 9), cursor="hand2",
                        padx=8, pady=6, bd=0,
                        activebackground=BORDER, activeforeground=TEXT)
    eye_btn.pack(side="left")
    entry.config(show="\u2022")

    tk.Label(card_inner, text="Ctrl+V — вставить из буфера",
             fg=BORDER, bg=BG2, font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))

    # Ctrl+V — на русской раскладке генерирует <Control-м>/<Control-igrave>
    def _do_paste():
        try:
            txt = root.clipboard_get().strip()
            if txt:
                cur = token_var.get()
                token_var.set(cur + txt)
                entry.icursor(tk.END)
        except tk.TclError:
            pass

    # Ловим ВСЕ Ctrl+клавиша и проверяем keycode (V = 86 на всех раскладках)
    def _on_key(event):
        if event.state & 0x4 and event.keycode == 86:  # Ctrl + keycode 86 = V
            _do_paste()
            return "break"

    root.bind("<Key>", _on_key)
    entry.bind("<Key>", _on_key)

    def _right_click(event):
        m = tk.Menu(root, tearoff=0, bg=BG2, fg=TEXT,
                    activebackground=BLUE, activeforeground="#fff",
                    font=("Segoe UI", 10))
        m.add_command(label="Вставить", command=_do_paste)
        m.add_command(label="Очистить", command=lambda: token_var.set(""))
        m.tk_popup(event.x_root, event.y_root)

    entry.bind("<Button-3>", _right_click)

    # ── Чекбокс автозапуска ──────────────────────────────────────────────────
    auto_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(wrap,
                    text="Запускать вместе с Windows",
                    variable=auto_var).pack(anchor="w", pady=(14, 0))

    # ── Ошибка ───────────────────────────────────────────────────────────────
    err_var = tk.StringVar()
    tk.Label(wrap, textvariable=err_var, fg=RED, bg=BG,
             font=("Segoe UI", 9), wraplength=420,
             justify="left").pack(anchor="w", pady=(6, 0))

    # ── Кнопки ───────────────────────────────────────────────────────────────
    btn_frame = tk.Frame(wrap, bg=BG)
    btn_frame.pack(fill="x", pady=(14, 0))

    def _submit(event=None):
        tok = token_var.get().strip()
        if not tok:
            err_var.set("Введите или вставьте токен")
            entry.focus_force()
            return
        if len(tok) < 10:
            err_var.set("Токен слишком короткий")
            entry.focus_force()
            return
        result["token"] = tok
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    cfg = json.load(f)
            else:
                from config import DEFAULT_CONFIG
                cfg = dict(DEFAULT_CONFIG)
            cfg["token"] = tok
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            err_var.set(f"Ошибка сохранения: {e}")
            return
        if auto_var.get():
            try:
                import autostart
                autostart.enable()
            except Exception:
                pass
        root.destroy()

    def _cancel():
        root.destroy()

    # Кнопка "Начать"
    start_btn = tk.Button(btn_frame, text="Начать работу", command=_submit,
                          bg=PINK, fg="#fff", relief="flat",
                          font=("Segoe UI", 11, "bold"), cursor="hand2",
                          padx=20, pady=8, bd=0,
                          activebackground="#e6264d", activeforeground="#fff")
    start_btn.pack(side="left")

    quit_btn = tk.Button(btn_frame, text="Выйти", command=_cancel,
                         bg=SURFACE, fg=MUTED, relief="flat",
                         font=("Segoe UI", 10), cursor="hand2",
                         padx=14, pady=8, bd=0,
                         activebackground=BORDER, activeforeground=TEXT)
    quit_btn.pack(side="left", padx=(10, 0))

    root.bind("<Return>", _submit)
    root.bind("<Escape>", lambda e: _cancel())
    root.protocol("WM_DELETE_WINDOW", _cancel)

    # ── Фокус ────────────────────────────────────────────────────────────────
    def _set_focus():
        root.attributes("-topmost", False)
        root.lift()
        root.focus_force()
        entry.focus_set()
        entry.icursor(tk.END)

    root.after(150, _set_focus)
    root.mainloop()
    return result["token"]
