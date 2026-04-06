# Invest Desktop Watcher

Windows-виджет в системном трее для отслеживания инвестиционного портфеля через T-Bank Invest API.

## Возможности

- Иконка в системном трее с индикацией роста/падения
- HTML-дашборд с тёмной/светлой темой (pywebview + Edge WebView2)
- 5 вкладок: Обзор, Позиции, Облигации, Аналитика, Настройки
- Календарь событий облигаций (купоны, оферты, погашения)
- Doughnut-аллокация (по типам / по бумагам)
- Купонный поток за 12 месяцев
- Сравнение счетов, валютная экспозиция
- Поиск и сортировка позиций (6 вариантов)
- Экспорт в Excel (.xlsx с формулами) и XML
- Автообновление через GitHub Releases
- Режим стримера (размытие балансов)
- Горячие клавиши: `Ctrl+R` обновить, `Esc` закрыть, `1-4` табы
- Toast-уведомления (оферты, купоны, движения портфеля)

## Установка

### Готовый .exe (рекомендуется)
1. Скачайте `InvestDesktopWatcher.exe` из [Releases](https://github.com/Damfler/Invest-Dekstop-Watcher/releases)
2. Запустите — откроется мастер настройки
3. Введите API-токен T-Invest (только чтение)

Данные хранятся в `%APPDATA%\InvestDesktopWatcher\`

### Из исходников
```bash
git clone https://github.com/Damfler/Invest-Dekstop-Watcher.git
cd Invest-Dekstop-Watcher
pip install -r requirements.txt
python main.py
```

## Конфигурация

Файл `config.json` (создаётся автоматически):

| Параметр | Описание |
|----------|----------|
| `theme` | Тема: `system` / `dark` / `light` |
| `bond_horizon_days` | Горизонт событий (30-365 дней) |
| `auto_update` | Проверка обновлений при старте |
| `use_logos` | Логотипы бумаг из CDN |
| `show_hints` | Подсказки (концентрация и т.д.) |
| `app_name` | Своё название приложения |

Для разработки: создайте `.env` с `TBANK_TOKEN=ваш_токен`

## Структура проекта

```
├── main.py              # Точка входа
├── version.py           # Версия
├── constants.py         # Константы
├── core/                # Ядро
│   ├── app.py           # Координатор
│   ├── data_store.py    # Хранилище данных
│   ├── config.py        # Конфигурация
│   └── cache.py         # Кэш
├── api/                 # T-Bank API
│   ├── client.py        # REST-клиент
│   └── endpoints.py     # URL-эндпоинты
├── ui/                  # Интерфейс
│   ├── window.py        # Дашборд (pywebview)
│   ├── menu.py          # Меню трея
│   ├── wizard.py        # Мастер настройки
│   └── icons.py         # Иконки трея
├── utils/               # Утилиты
│   ├── formatting.py    # Форматирование
│   ├── analytics.py     # Аналитика
│   ├── notifications.py # Уведомления
│   ├── autostart.py     # Автозапуск
│   └── updater.py       # Обновления
└── assets/              # Ресурсы
    ├── dashboard.html   # HTML-дашборд
    └── icons/           # Иконки
```

## Сборка .exe

```bash
build.bat
# или
python -m PyInstaller invest_desktop_watcher.spec --noconfirm --clean
```

## Разработчик

Гашук Дмитрий

[Поддержать проект](https://pay.cloudtips.ru/p/789f174f)
