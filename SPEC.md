# TBank Watcher — Техническое задание

> Версия: v2.3.1
> Язык: Python 3.13+, Windows
> Точка входа: `main.py`
> Репозиторий: https://github.com/Damfler/TBank-Watcher

---

## 1. Назначение

Виджет в системном трее Windows для отслеживания инвестиционного портфеля
через T-Bank Invest API (REST). Показывает стоимость счетов, P&L за день
или за всё время, события по облигациям (купоны, оферты, погашения).

**Левый клик** на иконке → открывает popup-дашборд.  
**Правый клик** → контекстное меню со всеми данными.

---

## 2. Структура файлов

```
tbank_v6/
├── main.py            # Точка входа. Логирование, wizard, запуск app.
├── version.py         # Единый источник версии (APP_VERSION, APP_NAME).
├── config.py          # Загрузка/сохранение config.json. Поддержка .env.
├── api.py             # T-Bank Invest REST API. Retry + rate limit 429.
├── cache.py           # Дисковый кэш (cache.json 24ч + history.json бессрочно).
├── utils.py           # Форматирование чисел/дат, parse_ts, days_until.
├── icons_gen.py       # Генерация иконок трея (PIL). Стрелки вверх/вниз.
├── autostart.py       # Автозапуск через реестр Windows (winreg).
├── notifications.py   # Toast-уведомления через plyer.
├── analytics.py       # YTM, аллокация, топ-муверы, денежный поток по месяцам.
├── data_store.py      # Хранилище данных. Потокобезопасный DataStore + кэш инструментов.
├── menu.py            # Построитель меню pystray (callable, подменю).
├── app.py             # Главный класс TBankTrayApp. pywebview main + pystray detached.
├── window.py          # Менеджер окна pywebview + JS API + Excel XML экспорт.
├── dashboard.html     # HTML-дашборд (Chart.js, Lucide Icons, 5 табов).
├── wizard.py          # Мастер первого запуска (ввод токена, стиль T-Bank).
├── updater.py         # Автообновление через GitHub Releases.
├── .env               # Токен для разработки (в .gitignore).
├── tbank_invest.spec  # PyInstaller spec для сборки .exe.
├── build.bat          # Сборка .exe одной командой.
├── requirements.txt   # Зависимости pip.
├── .github/workflows/
│   └── build.yml      # GitHub Actions: сборка по тегу + ручной запуск.
└── icons/
    ├── positive.png   # Иконка трея: портфель в плюсе
    ├── negative.png   # Иконка трея: портфель в минусе
    ├── warn.png       # Оферта скоро (опционально)
    └── crit.png       # Оферта сегодня (опционально)
```

**При сборке .exe:**
- Пользовательские данные: `%APPDATA%\TBankWatcher\` (config, cache, logs)
- dashboard.html + icons упакованы внутрь .exe
- Пользователь видит только `tbank_invest.exe`

**Автоматически создаваемые файлы (в gitignore):**
```
cache.json         # Кэш последних данных
dismissed.json     # Скрытые предупреждения об офертах
tbank_errors.log   # Лог ошибок (ротация 1МБ × 3 файла)
config.json.bak    # Бэкап при повреждении конфига
```

---

## 3. Конфигурация (config.json)

```json
{
  "token": "YOUR_TBANK_API_TOKEN_HERE",
  "use_sandbox": false,
  "use_custom_icons": true,
  "bond_horizon_days": 60,
  "bond_sort": "date",
  "notify_move_pct": 1.0,
  "notify_offer_days": 2,
  "notifications": {
    "offer_warn": true,
    "offer_crit": true,
    "coupon_tomorrow": true,
    "portfolio_move": true
  }
}
```

| Поле | Тип | Описание |
|---|---|---|
| `token` | str | API-токен T-Bank (только чтение). Перезаписывается из `.env` |
| `use_sandbox` | bool | Sandbox-режим API |
| `use_custom_icons` | bool | Использовать файлы из `icons/` или рисовать кодом |
| `bond_horizon_days` | int | Горизонт событий облигаций (30-365). Меняется в настройках |
| `bond_sort` | str | Сортировка событий: `"date"` или `"amount"` |
| `notify_move_pct` | float | Порог движения портфеля для уведомления (%) |
| `notify_offer_days` | int | За сколько дней предупреждать об оферте |
| `max_bond_events` | int | Макс. событий в меню трея (по умолчанию 50) |
| `theme` | str | Тема дашборда: `"system"` / `"dark"` / `"light"` |
| `use_logos` | bool | Показывать логотипы инструментов из CDN |
| `app_name` | str | Пользовательское название приложения |
| `show_hints` | bool | Показывать подсказки (концентрация и т.д.) |
| `auto_update` | bool | Проверять обновления через GitHub Releases |

---

## 4. API T-Bank Invest (api.py)

**Базовый URL:**
- Prod:    `https://invest-public-api.tinkoff.ru/rest`
- Sandbox: `https://sandbox-invest-public-api.tinkoff.ru/rest`

**Авторизация:** `Authorization: Bearer {token}`

**Используемые эндпоинты:**

| Метод | Путь | Описание |
|---|---|---|
| POST | `UsersService/GetAccounts` | Список брокерских счетов |
| POST | `OperationsService/GetPortfolio` | Портфель по accountId (валюта RUB) |
| POST | `InstrumentsService/BondBy` | Инфо по облигации по FIGI |
| POST | `InstrumentsService/GetBondCoupons` | Купонный график за период |

**Важно для BondBy:**
```python
# ПРАВИЛЬНО (полное имя enum из документации):
{"idType": "INSTRUMENT_ID_TYPE_FIGI", "id": figi}

# НЕПРАВИЛЬНО — вернёт 400:
{"idType": "ID_TYPE_FIGI", "id": figi}
```

**Retry-логика:**
- 400 — сразу ошибка без retry (неверный запрос)
- 401/403 — сразу ошибка (неверный токен)
- 5xx / таймаут — 3 попытки с задержкой 2→4→8 сек

**Структура MoneyValue (units + nano):**
```python
def money_value(obj: dict | None) -> float:
    return int(obj.get("units", 0)) + int(obj.get("nano", 0)) / 1_000_000_000
```

---

## 5. DataStore (data_store.py)

Центральное хранилище всех данных. Потокобезопасен (`threading.Lock`).

**Принцип работы:**
- Фоновый поток вызывает `fetch_portfolio()` и `fetch_bond_events()`.
- `menu.py` и `window.py` получают данные через `snapshot()` — копию, не живые данные.
- Фоновый поток **никогда** не трогает GUI напрямую.

**Ключевые поля snapshot():**
```python
{
    "portfolios":      list[dict],    # [{name, total, day_delta, alltime_delta, account_id}]
    "bond_events":     list[dict],    # события отсортированы по дате
    "bond_nkd":        dict,          # figi → {nkd_per, nkd_total, qty, name, isin}
    "positions_extra": list[dict],    # [{instrumentType, name, isin, figi, qty, current_price, current_value, day_delta}]
    "bond_analytics":  list[dict],    # для YTM
    "last_update":     str,
    "error":           str | None,
    "show_mode":       str,           # "day" | "alltime"
    "bond_horizon":    int,
    "bond_sort":       str,           # "date" | "amount"
    "alert_level":     int,           # 0=NONE, 1=WARN, 2=CRIT
    "dismissed":       set,
}
```

**Структура bond_event:**
```python
{
    "type":       str,      # "coupon" | "offer" | "call" | "maturity"
    "name":       str,
    "isin":       str,      # используется для ссылки tbank.ru/invest/bonds/{isin}/
    "figi":       str,
    "date":       datetime,
    "amount":     float | None,     # точная сумма купона
    "amount_est": float | None,     # оценочная сумма (НКД × qty, если amount недоступен)
    "qty":        int,
}
```

**Уровни алерта:**
```python
ALERT_NONE = 0  # норма
ALERT_WARN = 1  # оферта через 1-N дней (оранжевая иконка, можно скрыть)
ALERT_CRIT = 2  # оферта сегодня (мигающая красная иконка, нельзя скрыть)
```

---

## 6. Меню трея (menu.py)

**Ключевое решение (fix заморозки меню):**
```python
# НЕПРАВИЛЬНО — фоновый поток меняет меню пока оно открыто → заморозка:
self.icon.menu = build_menu()

# ПРАВИЛЬНО — pystray вызывает callable в момент клика:
self._icon = pystray.Icon(..., menu=pystray.Menu(self._menu_builder))
```

`MenuBuilder.__call__()` вызывается pystray при каждом открытии меню, берёт свежий `snapshot()` и возвращает `tuple` пунктов.

**Секции меню (порядок сверху вниз):**
1. Переключатель режима (за сегодня / за всё время)
2. Итого + список счетов
3. НКД накоплено + купоны вперёд (30/90 дн.)
4. Топ-3 лучших / худших позиций за день
5. Аллокация портфеля
6. Средний YTM облигаций
7. Алерт-баннер (если есть оферта)
8. События облигаций (купоны → оферты put → call → погашения)
9. Горизонт событий (30/60/90 дней)
10. Сортировка облигаций (по дате / по сумме)
11. Автозапуск (вкл/выкл)
12. Обновлено, Обновить сейчас, Выйти

**Ссылки на облигации:**
```
https://www.tbank.ru/invest/bonds/{ISIN}/
```

---

## 7. Иконки трея (icons_gen.py)

| Состояние | Файл (custom) | Fallback |
|---|---|---|
| Норма, рост | `icons/positive.png` | Зелёный квадрат `+` |
| Норма, падение | `icons/negative.png` | Красный квадрат `−` |
| Алерт WARN | `icons/warn.png` | Оранжевый квадрат `⚠` |
| Алерт CRIT (мигает) | `icons/crit.png` | Красный квадрат `!!` (мигает 0.6 сек) |

При CRIT запускается `_blink_loop` в фоновом потоке, который чередует яркую/тёмную версию иконки.

---

## 8. Popup-дашборд (window.py)

**Открытие:** левый клик на иконке трея.

**Архитектура потоков (критично!):**
```
# tkinter и pywebview ТРЕБУЮТ один и тот же поток на всё время жизни окна.
# НЕЛЬЗЯ создавать новый поток при каждом клике.

DashboardWindow:
  _window_thread  — постоянный поток, запускается один раз при старте
  _queue          — queue.Queue, toggle() кладёт "toggle" сюда
  _worker()       — читает очередь, открывает/закрывает окно в своём потоке
```

**Приоритет фреймворка:**
1. `pywebview` (если установлен) → HTML-дашборд с Chart.js
2. `tkinter` (встроен в Python) → нативный fallback

**Содержимое HTML-дашборда (pywebview):**
1. Итоговые карточки: портфель, дельта, НКД, YTM
2. Купоны за 30/90 дней
3. Список счетов
4. **Бар-чарт купонов по месяцам** (12 месяцев, Chart.js 4.4)
5. Аллокация портфеля (горизонтальные бары)
6. Таблица облигаций с ISIN, кликабельными ссылками и событиями

**JS API (pywebview):**
```javascript
pywebview.api.get_data()    // → JSON со снапшотом данных
pywebview.api.refresh()     // → принудительное обновление
pywebview.api.open_url(url) // → открыть URL в браузере
```

**Содержимое tkinter-fallback:**
- Шапка: итого + дельта
- НКД
- Список счетов
- Таблица событий облигаций (Treeview)

---

## 9. Уведомления (notifications.py)

Библиотека: `plyer`. Срабатывает один раз за сессию по каждому ключу.

| Событие | Ключ в `_notified` | Условие |
|---|---|---|
| Оферта сегодня | `crit_{isin}_{date}` | days_until == 0 |
| Оферта скоро | `warn_{isin}_{date}` | 1 ≤ days ≤ notify_offer_days |
| Купон завтра | `coupon_{isin}_{date}` | days_until == 1 |
| Движение портфеля | `move_{YYYYMMDDHH}` | изменение ≥ notify_move_pct% |

---

## 10. Аналитика (analytics.py)

| Функция | Описание |
|---|---|
| `calc_ytm_simple(...)` | YTM по формуле: `(C + (F-P)/N) / ((F+P)/2)` |
| `compute_portfolio_ytm(positions)` | Взвешенный YTM по всему портфелю |
| `compute_allocation(positions)` | Аллокация: `[("Облигации", 38.5), ...]` |
| `top_movers(positions, n=3)` | Топ-N позиций по росту и падению за день |
| `monthly_coupon_flow(events, months=12)` | Купонный поток по месяцам: `[("апр 25", 3500.0), ...]` |
| `coupon_sum_horizon(events, days)` | Сумма купонов за N дней вперёд |

---

## 11. Зависимости

```
pystray>=0.19.5    # иконка в трее
Pillow>=10.0.0     # генерация иконок
requests>=2.31.0   # HTTP-запросы к API
plyer>=2.1.0       # toast-уведомления
pywebview>=5.0.0   # HTML-окно (опционально, fallback на tkinter)
```

**Для сборки .exe:**
```
pyinstaller>=6.0   # устанавливается в build.bat автоматически
```

---

## 12. Сборка .exe (v9)

```bat
build.bat
```

Делает: pip install → pyinstaller → копирует иконки и config.json в `dist/`.  
Результат: `dist/tbank_invest.exe` (~50-80 МБ, без Python на машине).

Spec-файл: `tbank_invest.spec`. Ключевые настройки:
- `console=False` — без окна консоли
- `onefile=True` — один файл
- `icon=icons/positive.ico` — если есть .ico файл

---

## 13. Мастер первого запуска (wizard.py)

Показывается если `config["token"] == "YOUR_TBANK_API_TOKEN_HERE"`.

Содержит:
- Поле ввода токена (скрытый ввод `show="•"`)
- Ссылку на https://www.tbank.ru/invest/open-api/
- Чекбокс "Запускать с Windows"
- Кнопку "Начать работу"

При сохранении: записывает токен в `config.json`, опционально вызывает `autostart.enable()`.

---

## 14. Известные особенности и решения

### Заморозка меню при обновлении API
**Проблема:** `icon.menu = build_menu()` в фоновом потоке блокирует открытое меню.  
**Решение:** `pystray.Menu(callable)` — меню строится только в момент клика пользователем.

### Левый клик в pystray на Windows
**Проблема:** `icon.default_action = fn` игнорируется Win32-бэкендом.  
**Решение:**
```python
pystray.MenuItem("Открыть", fn, default=True, visible=False)
```

### tkinter/pywebview — требование одного потока
**Проблема:** нельзя создавать GUI-объекты в разных потоках.  
**Решение:** `DashboardWindow` запускает один постоянный `_window_thread`. Команды передаются через `queue.Queue`.

### BondBy — неверный enum
**Проблема:** `"ID_TYPE_FIGI"` возвращает 400.  
**Решение:** использовать полное имя `"INSTRUMENT_ID_TYPE_FIGI"`.

### Купон без суммы
**Проблема:** `payOneBond` иногда не возвращается API.  
**Решение:** если `amount == None` или 0, используем `nkd_per` из портфеля как оценку. В меню/дашборде помечается `≈`.

---

## 15. Изменения v10

### Архитектура потоков (переворот)
- **Главный поток** = `webview.start(func=background_init)` — pywebview event loop
- **Фоновый поток** (через `func=`): pystray `run_detached()`, refresh loop
- **ЛКМ**: monkey-patch `_message_handlers[WM_NOTIFY]` → `toggle()` (show/hide окна)
- **HTML загружается из файла** `dashboard.html` через `url=` (inline `html=` блокирует JS-события в EdgeChromium)

### Дашборд (dashboard.html)
- **Стиль T-Bank Invest**: тёмная тема (#1c1c1e), розовые акценты (#ff2d55)
- **Переключатель тем** (тёмная/светлая), сохраняется в `config.json["theme"]`
  - Значения: `"system"` (по умолчанию), `"dark"`, `"light"`
  - При `"system"` — определяется по `prefers-color-scheme` ОС
- **4 вкладки**: Обзор, Позиции, Облигации, Аналитика
- **Табы счетов**: "Все счета" / конкретный — фильтрует позиции и итоги
- **Позиции**: карточки с иконками типа (B/S/F/$), ISIN, кол-во, счёт
  - Клик → открывает на tbank.ru (bonds/stocks/etfs по типу)
- **Облигации**: карточки по бумагам с пилюлями событий
  - Фильтр: Все / Купоны / Оферты / Погашения
- **Аллокация**: doughnut chart (по типам / по бумагам)
- **Купонный поток**: бар-чарт за 12 месяцев с итоговой суммой

### Данные позиций (data_store.py)
- Каждая позиция содержит `account_id` и `account_name`
- Позволяет фильтровать по счетам и показывать принадлежность

### Конфигурация (config.json)
- `"max_bond_events": 50` — лимит событий в меню
- `"theme": "system"` — тема дашборда

### Кэширование
- Кэш сохраняется после каждого refresh-цикла (не только при выходе)

### Исправления
- `days_until()` — сравнение по локальным календарным датам (не UTC)
- JS `daysUntil()` — аналогично, по локальному времени
- Меню организовано в подменю (Портфель, Аналитика, Облигации, Настройки)

---

## 16. Изменения v11

### Новые фичи дашборда (dashboard.html)

**Высокий приоритет:**
1. **График стоимости портфеля** — Chart.js line chart с кнопками 1Д/1Н/1М/3М/Все
   - Данные копятся в `history.json` (раз в 5 мин через `data_store.py`)
   - Градиентная заливка (зелёная при росте, красная при падении)
   - Показывает % изменения за выбранный период
2. **Календарь событий** — CSS-grid на вкладке "Облигации"
   - Цветные точки по типу (купон=синий, оферта=розовый, погашение=фиолетовый)
   - Клик по дню → popup с событиями, навигация по месяцам
3. **Карточка общей доходности** — `alltime_delta / invested * 100%`
   - Двойная ширина, на вкладке "Обзор"

**Средний приоритет:**
4. **Валютная экспозиция** — doughnut на вкладке "Аналитика"
   - Определение валюты из имени позиции (USD.../EUR.../..., остальное = RUB)
5. **Виджет ближайших событий** — 5 ближайших на вкладке "Обзор"
   - Иконки по типу (coins/alert-triangle/circle-check), обратный отсчёт
6. **Предупреждение о концентрации** — если позиция > 20% портфеля
   - Жёлтый баннер с `alert-triangle` на вкладке "Обзор"
7. **Сравнение счетов** — горизонтальный бар-чарт на вкладке "Аналитика"
   - Скрывается если только 1 счёт

### Skeleton loading
- Серые мерцающие блоки (shimmer) при загрузке данных
- Плавное появление контента (opacity transition)

### Lucide Icons
- Подключены через CDN (unpkg.com/lucide)
- Заменены все эмодзи: кнопки, вкладки, карточки, типы позиций
- `lucide.createIcons()` вызывается после каждого render

### Backend: история портфеля
- `cache.py`: `save_history()` / `load_history()` → `history.json`
  - Отдельный файл, без лимита по возрасту (max 5000 точек)
- `data_store.py`: `portfolio_history` поле, запись точки раз в 5 мин
  - Включено в `snapshot()` для передачи в JS

---

## 17. Изменения v2.3.1

### Архитектура
- **Главный поток** = `webview.start()`, pystray через `run_detached()`
- **ЛКМ**: monkey-patch `_message_handlers[WM_NOTIFY]` в pystray
- **Окно**: `hidden=True` при старте, `show()/hide()` по ЛКМ, `closing` → hide
- **Файлы .exe**: данные в `%APPDATA%\TBankWatcher\`, ресурсы внутри .exe

### Дашборд (dashboard.html)
- **5 табов**: Обзор, Позиции, Облигации, Аналитика, Настройки (через шестерёнку)
- **Стиль T-Bank**: тёмная/светлая тема, системная по умолчанию
- **Skeleton loading**: мерцающие заглушки при загрузке данных
- **Lucide Icons**: SVG-иконки вместо эмодзи
- **P&L переключатель**: клик меняет день/всё время, нулевой P&L серым
- **Табы счетов**: фильтрация по счёту, обрезка длинных названий с tooltip
- **Позиции**: поиск, сортировка (6 вариантов), фильтры по типу, итого
- **Облигации**: календарь событий + карточки с пилюлями + фильтры
- **Аналитика**: doughnut аллокация, купоны 12 мес., сравнение счетов, валютная экспозиция
- **Экспорт**: CSV + Excel XML (с формулами SUM, 2 листа)
- **Горячие клавиши**: Ctrl+R обновить, Esc закрыть, 1-4 табы
- **Относительное время**: "только что" → "5 сек назад" → "2 мин назад"
- **Режим стримера**: размытие балансов
- **Пользовательское название** приложения

### Данные
- `ticker` берётся из GetPortfolio API (не нужен отдельный запрос)
- `dailyYield` / `expectedYield` позиций — правильный P&L день/всё время
- Валюта: дробное количество (0.95 USD), `money_value()` для qty
- Кэш инструментов в памяти (rate limit protection)
- Логотипы из CDN: `invest-brands.cdn-tinkoff.ru/{logoName}x160.png`

### API
- `GetInstrumentBy` — информация по любому инструменту
- `ShareBy` — информация по акции
- Rate limit 429: увеличенная пауза 5/10/15 сек + паузы между запросами

### Автообновление (updater.py)
- Проверка GitHub Releases при старте (`Damfler/TBank-Watcher`)
- Сравнение `tag_name` с `APP_VERSION` из `version.py`
- Скачивание .exe → .bat скрипт замены → перезапуск
- Чекбокс вкл/выкл в настройках

### Сборка
- GitHub Actions: `build.yml` — по тегу `v*` или вручную
- `.env` для разработки (токен не попадает в git)
- `.gitignore` — dist, build, config, cache, .env
- `build.bat` — чистый dist, config генерируется через wizard

---

## 18. Что ещё не реализовано (backlog)

- Несколько токенов / профилей
- Детальная информация по позиции (цена покупки, средняя)
- График истории портфеля (данные копятся в history.json, UI скрыт)
- Уведомления в Telegram