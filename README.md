<div align="center">

<img src="assets/icons/icon.png" alt="Stack" width="120" height="120" />

# Stack

**Windows tray widget for tracking your investment portfolio**

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Release](https://img.shields.io/github/v/release/Damfler/Invest-Dekstop-Watcher?color=B8F34A&label=release)](https://github.com/Damfler/Invest-Dekstop-Watcher/releases/latest)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<p>
  <a href="#english"><img src="https://img.shields.io/badge/Readme-English-B8F34A?style=for-the-badge&labelColor=0B0D0E&color=0B0D0E" alt="English" /></a>
  &nbsp;
  <a href="#russian"><img src="https://img.shields.io/badge/Readme-Русский-FF2D55?style=for-the-badge&labelColor=0B0D0E&color=0B0D0E" alt="Русский" /></a>
</p>

<sub>Click a badge to jump · expand a section below to read</sub>

</div>

---

<a id="english"></a>

<details open>
<summary><strong>🇬🇧 English</strong></summary>

<div align="center">

<a href="https://github.com/Damfler/Invest-Dekstop-Watcher/releases/latest">
  <img src="https://img.shields.io/badge/Download-Stack.exe-B8F34A?style=for-the-badge&logo=windows&logoColor=0B0D0E&labelColor=0B0D0E" alt="Download" />
</a>

<br><br>

<img src="assets/github-social-preview-en.png" alt="Stack — Investment Tracker" width="100%" />

</div>

## What is Stack?

**Stack** lives in the Windows system tray and shows your investment portfolio in near real time. The tray icon reflects current P&L; a left click opens an HTML dashboard with positions, bonds, events (coupons / offers / maturities), charts, and per-account filters.

**T-Bank Invest API** is supported today. The architecture is ready for more brokers.

## Features

| | |
|---|---|
| 🟢 **Tray icon** | Color reflects P&L: green / red / gray. Offer soon → orange; offer today → blinking red |
| 📊 **HTML dashboard** | 5 tabs: Overview, Positions, Bonds, Analytics, Settings. Dark / light / system theme |
| 📅 **Event calendar** | Coupons, offers, maturities with color coding and pop-up details |
| 🥧 **Allocation** | Doughnut charts by asset type and by instrument, currency exposure |
| 💰 **Coupon flow** | 12-month bar chart of expected coupons |
| 🏦 **Multi-account** | Compare accounts, filter, per-account totals |
| 🔍 **Search & filters** | Position search, 6 sort modes, filters by instrument type |
| 📤 **Export** | Excel (.xlsx with formulas) and XML, 2 sheets |
| 🔔 **Notifications** | Windows toasts: offers, coupons, portfolio moves |
| 🔄 **Auto-update** | Via GitHub Releases — one click, automatic restart |
| 🎬 **Streamer mode** | Blur balances with one click |
| ⌨️ **Hotkeys** | `Ctrl+R` refresh, `Esc` close, `1-4` switch tabs |
| 💿 **Compact mode** | Mono table layout — minimal chrome for daily use |

## Installation

### 🚀 Pre-built `.exe` — recommended

1. [Download Stack.exe](https://github.com/Damfler/Invest-Dekstop-Watcher/releases/latest) from the latest release
2. Run it — the first-run wizard opens
3. Create a token in **T-Invest → Settings → API → Create token** (read-only)
4. Paste the token in the wizard; optionally enable “Run with Windows”

User data is stored in `%APPDATA%\Stack\` (config, cache, logs). The app itself is a single `Stack.exe` (~50–80 MB), no extra runtime required.

### 🛠 From source

```bash
git clone https://github.com/Damfler/Invest-Dekstop-Watcher.git
cd Invest-Dekstop-Watcher
pip install -r requirements.txt
python main.py
```

For development, put your token in `.env`:

```
TBANK_TOKEN=t.your_token_here
```

## Configuration

`config.json` is created automatically in `%APPDATA%\Stack\` (`.exe`) or next to the script (dev). Most options are available in the dashboard — **Settings** (gear in the header).

| Parameter | Description |
|----------|----------|
| `theme` | Dashboard theme: `system` / `dark` / `light` |
| `design` | Layout: `classic` / `simple` (compact mono mode) |
| `bond_horizon_days` | Bond event horizon (30–365 days) |
| `notify_offer_days` | Days before an offer to warn |
| `notify_move_pct` | Portfolio move threshold (%) for notifications |
| `auto_update` | Check for updates on startup |
| `use_logos` | Instrument logos from T-Bank CDN |

## Architecture

<details>
<summary>Project structure</summary>

```text
├── main.py              # Entry point, wizard, init
├── version.py           # APP_VERSION, APP_NAME
├── constants.py         # Timers, alerts, broker list
├── core/
│   ├── app.py           # StackTrayApp — pystray + pywebview
│   ├── data_store.py    # Thread-safe store with snapshot()
│   ├── config.py        # Load/save config.json
│   └── cache.py         # Data cache + portfolio history
├── api/
│   ├── client.py        # T-Bank REST client (retry, rate-limit)
│   └── endpoints.py     # Endpoint URLs
├── ui/
│   ├── window.py        # pywebview window + JS API
│   ├── menu.py          # Callable pystray menu
│   ├── wizard.py        # First-run wizard
│   └── icons.py         # Tray icons (Pillow + PNG from assets/)
├── utils/
│   ├── formatting.py    # Number/date formatting
│   ├── analytics.py     # YTM, allocation, top-movers, cashflow
│   ├── notifications.py # Toast notifications (plyer)
│   ├── autostart.py     # Windows autostart registry
│   └── updater.py       # GitHub Releases auto-update
├── assets/
│   ├── dashboard.html   # HTML dashboard (Chart.js + Lucide)
│   └── icons/           # Logo, tray state icons
└── tools/
    ├── gen_icons.py             # Icon generator from logo.svg
    └── gen_social_preview.py    # GitHub Social Preview
```

</details>

<details>
<summary>Tech stack</summary>

- **Python 3.13+** — core runtime
- **pystray** + **Pillow** — tray icon, sprite generation
- **pywebview** (Edge WebView2) — dashboard window
- **requests** — T-Bank REST client
- **plyer** — native Windows toast notifications
- **openpyxl** — Excel export with formulas
- **Chart.js** + **Lucide** + **html2canvas** — frontend (CDN)
- **resvg-py** — SVG icon rendering (build-time)
- **PyInstaller** — single-file `.exe` build

</details>

## Build `.exe`

```bash
build.bat
# or directly:
python -m PyInstaller stack.spec --noconfirm --clean
```

Output: `dist/Stack.exe`. Resources (HTML, icons) are bundled inside.

## Icons

All tray state icons (`positive.png` / `negative.png` / `neutral.png` / `warn.png` / `crit.png`) are generated from one `assets/icons/logo.svg`:

```bash
python tools/gen_icons.py             # all: PNG icons + .ico
python tools/gen_icons.py --states    # tray states only
python tools/gen_icons.py --brand     # icon.png + icon.ico only
```

Icons are rendered with `resvg-py` (native Rust renderer, no cairo), recolored via alpha channel on a squircle background. Custom colors: edit `PRESETS` in `tools/gen_icons.py`.

## GitHub Social Preview

Repository share image (1280×640). Uses real app screenshots from `assets/mockups/` when present; otherwise draws a mockup with Pillow.

```bash
python tools/gen_social_preview.py            # en (default)
python tools/gen_social_preview.py --locale ru
python tools/gen_social_preview.py --all      # both locales
```

Capture screenshots from the app: enable **Dev mode** in Settings → click 📷 in the header on the screen you need.

**Upload to GitHub:** `Settings → Options → Social preview → Edit → Upload image` (use `assets/github-social-preview-en.png`).

## Supported brokers

| Broker | Status |
|--------|--------|
| 🟢 **T-Bank (T-Invest)** | Ready |
| 🟡 Sber Invest | Planned |
| 🟡 VTB My Investments | Planned |
| 🟡 Alfa Investments | Planned |
| 🟡 BCS World of Investments | Planned |

Broker list lives in `constants.BROKERS` + `wizard.py`. To add one: implement an `api/client.py`-compatible class and add `elif broker == "xxx"` in `main.py`.

## Author

**Dmitry Gashuk**

<a href="https://pay.cloudtips.ru/p/789f174f">
  <img src="https://img.shields.io/badge/❤-Support%20the%20project-FF2D55?style=for-the-badge" alt="Donate" />
</a>

<div align="center">
<sub>Made with ❤ · 2026</sub>
</div>

</details>

---

<a id="russian"></a>

<details>
<summary><strong>🇷🇺 Русский</strong></summary>

<div align="center">

<a href="https://github.com/Damfler/Invest-Dekstop-Watcher/releases/latest">
  <img src="https://img.shields.io/badge/Скачать-Stack.exe-B8F34A?style=for-the-badge&logo=windows&logoColor=0B0D0E&labelColor=0B0D0E" alt="Скачать" />
</a>

<br><br>

<img src="assets/github-social-preview-ru.png" alt="Stack — трекер инвестиций" width="100%" />

</div>

## Что это

**Stack** живёт в системном трее Windows и показывает состояние инвестиционного портфеля в реальном времени. Иконка меняет цвет в зависимости от текущего P&L, по левому клику открывается HTML-дашборд: позиции, облигации, события (купоны / оферты / погашения), графики и фильтры по счетам.

Сейчас поддерживается **T-Bank Invest API**. Архитектура подготовлена для других брокеров.

## Возможности

| | |
|---|---|
| 🟢 **Трей-иконка** | Цвет отражает P&L: зелёный / красный / серый. При оферте — оранжевая, при оферте сегодня — мигающая красная |
| 📊 **HTML-дашборд** | 5 вкладок: Обзор, Позиции, Облигации, Аналитика, Настройки. Тёмная / светлая / системная тема |
| 📅 **Календарь событий** | Купоны, оферты, погашения с цветовой подсветкой и popup-деталями |
| 🥧 **Аллокация** | Doughnut-чарт по типам и по бумагам, валютная экспозиция |
| 💰 **Купонный поток** | Бар-чарт по месяцам на 12 месяцев вперёд |
| 🏦 **Мультисчета** | Сравнение, фильтрация, итоги по каждому счёту |
| 🔍 **Поиск и фильтры** | Поиск позиций, сортировка по 6 критериям, фильтры по типу |
| 📤 **Экспорт** | Excel (.xlsx с формулами) и XML, 2 листа |
| 🔔 **Уведомления** | Toast: оферты, купоны, движения портфеля |
| 🔄 **Автообновление** | Через GitHub Releases — одна кнопка, перезапуск автоматически |
| 🎬 **Режим стримера** | Размытие балансов одним кликом |
| ⌨️ **Горячие клавиши** | `Ctrl+R` обновить, `Esc` закрыть, `1-4` табы |
| 💿 **Компактный режим** | Mono-таблица без лишних элементов — для повседневного использования |

## Установка

### 🚀 Готовый `.exe` — рекомендуется

1. [Скачай Stack.exe](https://github.com/Damfler/Invest-Dekstop-Watcher/releases/latest) из последнего релиза
2. Запусти — откроется мастер первого запуска
3. Создай токен в **Т-Инвестиции → Настройки → API → Создать токен** (только чтение)
4. Вставь токен в мастер, поставь галку «Запускать с Windows»

Пользовательские данные хранятся в `%APPDATA%\Stack\` (config, cache, logs). Само приложение — один `Stack.exe` ~50–80 МБ, без зависимостей.

### 🛠 Из исходников

```bash
git clone https://github.com/Damfler/Invest-Dekstop-Watcher.git
cd Invest-Dekstop-Watcher
pip install -r requirements.txt
python main.py
```

Для разработки положи токен в `.env`:

```
TBANK_TOKEN=t.твой_токен
```

## Конфигурация

`config.json` создаётся автоматически в `%APPDATA%\Stack\` (`.exe`) или рядом со скриптом (dev). Большинство параметров переключаются из дашборда — раздел «Настройки» (шестерёнка в шапке).

| Параметр | Описание |
|----------|----------|
| `theme` | Тема дашборда: `system` / `dark` / `light` |
| `design` | Дизайн: `classic` / `simple` (компактный mono-режим) |
| `bond_horizon_days` | Горизонт событий облигаций (30–365 дней) |
| `notify_offer_days` | За сколько дней до оферты предупреждать |
| `notify_move_pct` | Порог % движения портфеля для уведомления |
| `auto_update` | Проверять обновления при старте |
| `use_logos` | Логотипы бумаг из CDN T-Bank |

## Архитектура

<details>
<summary>Структура проекта</summary>

```text
├── main.py              # Точка входа, мастер, инициализация
├── version.py           # APP_VERSION, APP_NAME
├── constants.py         # Таймеры, алерты, список брокеров
├── core/
│   ├── app.py           # StackTrayApp — координатор pystray + pywebview
│   ├── data_store.py    # Потокобезопасное хранилище с snapshot()
│   ├── config.py        # Загрузка/сохранение config.json
│   └── cache.py         # Кэш данных + история портфеля
├── api/
│   ├── client.py        # T-Bank REST-клиент (retry, rate-limit)
│   └── endpoints.py     # URL эндпоинтов
├── ui/
│   ├── window.py        # Менеджер pywebview-окна + JS API
│   ├── menu.py          # Callable-меню pystray
│   ├── wizard.py        # Мастер первого запуска
│   └── icons.py         # Иконки трея (Pillow + PNG из assets/)
├── utils/
│   ├── formatting.py    # Форматирование чисел/дат
│   ├── analytics.py     # YTM, аллокация, top-movers, cashflow
│   ├── notifications.py # Toast-уведомления (plyer)
│   ├── autostart.py     # Реестр Windows для автозапуска
│   └── updater.py       # GitHub Releases auto-update
├── assets/
│   ├── dashboard.html   # HTML-дашборд (Chart.js + Lucide)
│   └── icons/           # Логотип, state-иконки трея
└── tools/
    ├── gen_icons.py             # Генератор иконок из logo.svg
    └── gen_social_preview.py    # GitHub Social Preview
```

</details>

<details>
<summary>Стек</summary>

- **Python 3.13+** — основной язык
- **pystray** + **Pillow** — иконка в трее, генерация спрайтов
- **pywebview** (Edge WebView2) — окно дашборда
- **requests** — REST-клиент T-Bank
- **plyer** — нативные toast-уведомления Windows
- **openpyxl** — Excel-экспорт с формулами
- **Chart.js** + **Lucide** + **html2canvas** — фронт (CDN)
- **resvg-py** — SVG-рендеринг иконок (build-time)
- **PyInstaller** — сборка в один `.exe`

</details>

## Сборка `.exe`

```bash
build.bat
# или напрямую:
python -m PyInstaller stack.spec --noconfirm --clean
```

Результат — `dist/Stack.exe`. Все ресурсы (HTML, иконки) упакованы внутрь.

## Иконки

Все state-иконки трея (`positive.png` / `negative.png` / `neutral.png` / `warn.png` / `crit.png`) генерируются из одного `assets/icons/logo.svg`:

```bash
python tools/gen_icons.py             # всё: PNG-иконки + .ico
python tools/gen_icons.py --states    # только трей-состояния
python tools/gen_icons.py --brand     # только icon.png + icon.ico
```

Иконки рендерятся через `resvg-py` с перекраской по альфа-каналу и наложением на squircle-фон. Свой цвет — поправь `PRESETS` в `tools/gen_icons.py`.

## GitHub Social Preview

Превью-картинка для шаринга репозитория (1280×640). Использует скриншоты из `assets/mockups/` или рисует мокап через Pillow.

```bash
python tools/gen_social_preview.py            # en (по умолчанию)
python tools/gen_social_preview.py --locale ru
python tools/gen_social_preview.py --all      # обе локали сразу
```

Скриншоты из приложения: **Dev-режим** в настройках → иконка 📷 в шапке на нужном экране.

**Загрузка в репо:** `Settings → Options → Social preview → Edit → Upload image` (файл `assets/github-social-preview-ru.png`).

## Поддерживаемые брокеры

| Брокер | Статус |
|--------|--------|
| 🟢 **Т-Банк (T-Invest)** | Готово |
| 🟡 Сбер Инвестиции | В планах |
| 🟡 ВТБ Мои Инвестиции | В планах |
| 🟡 Альфа-Инвестиции | В планах |
| 🟡 БКС Мир Инвестиций | В планах |

Чтобы добавить брокера — реализуй класс, совместимый с `api/client.py`, и добавь `elif broker == "xxx"` в `main.py`.

## Разработчик

**Гашук Дмитрий**

<a href="https://pay.cloudtips.ru/p/789f174f">
  <img src="https://img.shields.io/badge/❤-Поддержать%20проект-FF2D55?style=for-the-badge" alt="Donate" />
</a>

<div align="center">
<sub>Сделано с ❤ · 2026</sub>
</div>

</details>
