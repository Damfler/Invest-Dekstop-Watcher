"""
wizard.py — мастер первого запуска.
Показывается когда токен не введён.
Стилизован под дашборд Invest Desktop Watcher.
"""
import os
import sys
import json
import logging
import webbrowser

log = logging.getLogger("tbank.wizard")

from version import APP_VERSION, APP_NAME
from constants import TOKEN_STUB, BROKERS, BROKER_INFO

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)), "InvestDesktopWatcher")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


def needs_wizard(cfg: dict) -> bool:
    connections = cfg.get("connections", [])
    if not connections:
        return True
    # Нужен мастер если ни одно подключение не настроено (все TOKEN_STUB)
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
    root.title(APP_NAME)
    root.geometry("480x580")
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
    style.configure("Broker.TCombobox", fieldbackground=SURFACE, foreground=TEXT,
                    selectbackground=BLUE, selectforeground="#fff",
                    bordercolor=BORDER, font=("Segoe UI", 10))

    # ── Контейнер с отступами ────────────────────────────────────────────────
    wrap = tk.Frame(root, bg=BG)
    wrap.pack(fill="both", expand=True, padx=28, pady=24)

    # ── Заголовок ────────────────────────────────────────────────────────────
    tk.Label(wrap, text=APP_NAME, fg=TEXT, bg=BG,
             font=("Segoe UI", 20, "bold")).pack(anchor="w")
    tk.Label(wrap, text=f"v{APP_VERSION}", fg=BORDER, bg=BG,
             font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 4))
    tk.Label(wrap, text="Виджет для отслеживания инвестиционного портфеля",
             fg=MUTED, bg=BG, font=("Segoe UI", 10)).pack(anchor="w")

    # ── Разделитель ──────────────────────────────────────────────────────────
    tk.Frame(wrap, bg=BORDER, height=1).pack(fill="x", pady=16)

    # ── Карточка выбора брокера ──────────────────────────────────────────────
    broker_card = tk.Frame(wrap, bg=BG2, highlightbackground=BORDER,
                           highlightthickness=1, bd=0)
    broker_card.pack(fill="x", pady=(0, 10))
    broker_inner = tk.Frame(broker_card, bg=BG2)
    broker_inner.pack(fill="x", padx=16, pady=14)

    tk.Label(broker_inner, text="Брокер", fg=TEXT, bg=BG2,
             font=("Segoe UI", 12, "bold")).pack(anchor="w")
    tk.Label(broker_inner, text="Выберите брокера для подключения",
             fg=MUTED, bg=BG2, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 8))

    broker_var = tk.StringVar(value=list(BROKERS.keys())[0])
    broker_display = tk.StringVar(value=list(BROKERS.values())[0])

    broker_combo = ttk.Combobox(broker_inner, textvariable=broker_display,
                                values=list(BROKERS.values()),
                                state="readonly", style="Broker.TCombobox",
                                font=("Segoe UI", 10))
    broker_combo.pack(fill="x", ipady=4)

    def _on_broker_change(event=None):
        idx = list(BROKERS.values()).index(broker_display.get())
        key = list(BROKERS.keys())[idx]
        broker_var.set(key)
        info = BROKER_INFO.get(key, BROKER_INFO["tbank"])
        token_title_lbl.config(text=info["token_label"])
        token_hint_lbl.config(text=info["hint"])
        api_link_lbl.config(text=info["api_label"])
        api_link_lbl.bind("<Button-1>", lambda e: webbrowser.open(info["api_url"]))

    broker_combo.bind("<<ComboboxSelected>>", _on_broker_change)

    # ── Карточка ввода токена ────────────────────────────────────────────────
    card = tk.Frame(wrap, bg=BG2, highlightbackground=BORDER,
                    highlightthickness=1, bd=0)
    card.pack(fill="x")
    card_inner = tk.Frame(card, bg=BG2)
    card_inner.pack(fill="x", padx=16, pady=14)

    default_info = BROKER_INFO[broker_var.get()]

    token_title_lbl = tk.Label(card_inner, text=default_info["token_label"],
                                fg=TEXT, bg=BG2, font=("Segoe UI", 12, "bold"))
    token_title_lbl.pack(anchor="w")

    token_hint_lbl = tk.Label(card_inner, text=default_info["hint"],
                               fg=MUTED, bg=BG2, font=("Segoe UI", 9),
                               justify="left")
    token_hint_lbl.pack(anchor="w", pady=(4, 8))

    api_link_lbl = tk.Label(card_inner, text=default_info["api_label"],
                             fg=BLUE, bg=BG2, cursor="hand2",
                             font=("Segoe UI", 9, "underline"))
    api_link_lbl.pack(anchor="w", pady=(0, 10))
    api_link_lbl.bind("<Button-1>",
                      lambda e: webbrowser.open(BROKER_INFO[broker_var.get()]["api_url"]))

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

    def _do_paste():
        try:
            txt = root.clipboard_get().strip()
            if txt:
                cur = token_var.get()
                token_var.set(cur + txt)
                entry.icursor(tk.END)
        except tk.TclError:
            pass

    def _on_key(event):
        if event.state & 0x4 and event.keycode == 86:
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
            # Сохраняем в connections[0] (новый формат)
            first_conn = {
                "name":        list(BROKERS.values())[list(BROKERS.keys()).index(broker_var.get())],
                "broker":      broker_var.get(),
                "token":       tok,
                "enabled":     True,
                "use_sandbox": False,
            }
            existing = cfg.get("connections", [])
            if existing:
                existing[0] = first_conn
            else:
                existing = [first_conn]
            cfg["connections"] = existing
            # Удаляем старые поля если остались от миграции
            cfg.pop("token", None)
            cfg.pop("broker", None)
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

    def _set_focus():
        root.attributes("-topmost", False)
        root.lift()
        root.focus_force()
        entry.focus_set()
        entry.icursor(tk.END)

    root.after(150, _set_focus)
    root.mainloop()
    return result["token"]
