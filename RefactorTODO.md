# План рефакторинга LittleTools

Этот документ описывает шаги по преобразованию проекта из набора разрозненных скриптов в управляемую, модульную экосистему пакетов на основе `pyproject.toml`.

## Фаза 1: Модуляризация и пакетирование

### 1. [x] Создание базового пакета `littletools-core`

-   [x] Создать директорию `littletools_core`.
-   [x] Переместить `little_tools_utils.py` внутрь `littletools_core/`, возможно, переименовав его в `utils.py`.
-   [x] Создать `littletools_core/__init__.py` для оформления в виде пакета.
-   [x] Создать `littletools_core/pyproject.toml`. Указать минимальные метаданные (имя, версия, автор). Зависимостей у этого пакета быть не должно.
-   [x] **(Ключевой шаг)** Пройти по всем скриптам проекта (`menu.py`, все утилиты) и заменить локальные импорты на импорты из нового пакета (например, `from little_tools_utils import ...` на `from littletools_core.utils import ...`).

### 2. [x] Выделение `Infinite Differ` в отдельный репозиторий

-   [x] Создать новый Git-репозиторий (например, `InfiniteDiffer`).
-   [x] Перенести содержимое `TxtTools/MultipleTextComparator` в новый репозиторий.
-   [x] В новом репозитории создать `pyproject.toml`, указав `PyQt6` как основную зависимость.
-   [x] Добавить `README.md` с инструкцией по установке и запуску.
-   [x] Удалить `TxtTools/MultipleTextComparator` из репозитория `LittleTools`.
-   [x] Удалить запись о `"infinite_differ"` из словаря `TOOLS` в `menu.py`.

### 3. [ ] Группировка оставшихся утилит в пакеты

-   [ ] **Пакет `littletools-video`:**
    -   [ ] Создать директорию `littletools_video`.
    -   [ ] Переместить туда скрипты из `VideoTools` (`FFMPEG_MKV_audio_normalizer_v2.py`, `Topaz_Video_Merger.py`, `video_converter.py`, `Image_Audio_To_Video.py`) и общие видео-утилиты (`ffmpeg_utils.py`).
    -   [ ] Создать `littletools_video/pyproject.toml`. В зависимостях указать `Pillow`. В `entry_points` определить консольные скрипты для каждого инструмента.
-   [ ] **Пакет `littletools-speech` (для Whisper Transcriber):**
    -   [ ] Создать директорию `littletools_speech`.
    -   [ ] Переместить `Audio-_Video-2-Text/whisper_transcriber.py` в новую директорию.
    -   [ ] Создать `littletools_speech/pyproject.toml`. Указать тяжелые зависимости (`torch`, `openai-whisper`, `ffmpeg-python`). Определить `entry_point`.
-   [ ] **Пакет `littletools-txt` (для остальных текстовых утилит):**
    -   [ ] Создать директорию `littletools_txt`.
    -   [ ] Переместить туда `Telegram_Chats_Distiller.py`, `SyntxAiDownloader.py`, `WMDconverter/WMDconverter.py`, `CyrillicRemover/CyrillicRemover.py`.
    -   [ ] Создать `littletools_txt/pyproject.toml`. Указать зависимости (`pypandoc`, `requests`, `beautifulsoup4`). Определить `entry_points` для каждого скрипта.

### 4. [ ] Рефакторинг `menu.py` в `littletools-cli`

-   [ ] Создать директорию `littletools_cli`.
-   [ ] Переместить `menu.py` в `littletools_cli/main.py`.
-   [ ] **Полностью переработать `main.py`:**
    -   [ ] Удалить огромный словарь `TOOLS`.
    -   [ ] Удалить всю логику по установке зависимостей, созданию venv, проверке системных утилит (это теперь задача `pip` и пользователя).
    -   [ ] Реализовать динамический поиск установленных "плагинов" через `importlib.metadata`. Скрипт должен искать все пакеты, у которых есть `entry_point` в группе `"littletools.commands"`.
    -   [ ] Меню должно строиться на основе найденных `entry_points`.
-   [ ] Создать `littletools_cli/pyproject.toml`. Зависимостью будет `littletools-core`. Определить `entry_point` для запуска самого меню (например, `lt-menu`).

### 5. [ ] Завершающие шаги

-   [ ] В корне проекта создать `pyproject.toml`, который объявит `workspace`, чтобы можно было удобно работать со всеми локальными пакетами (`littletools-core`, `littletools-video` и т.д.).
-   [ ] Обновить корневой `README.MD`, описав новую, пакетную структуру и новый способ установки (`pip install littletools-cli littletools-video ...`).
-   [ ] Обновить/упростить `start.ps1` и `start.bat`. Вместо сложной логики проверки окружения они могут просто выполнять установку пакетов через `pip` и запускать `lt-menu`.
-   [ ] Удалить старые, пустые директории (`TxtTools`, `VideoTools`, `Audio-_Video-2-Text`).

## Фаза 2: Тестирование и CI/CD

### 1. [ ] Покрытие кода тестами

-   [ ] Создать директорию `tests/` в корне репозитория.
-   [ ] Настроить `pytest` как основной тест-раннер.
-   [ ] Добавить базовые unit-тесты для `littletools_core.utils` и ключевых функций из других пакетов.
-   [ ] Сконфигурировать проверку покрытия (`pytest-cov`) и установить минимальный порог (например, 60 %).

### 2. [ ] Непрерывная интеграция (GitHub Actions)

-   [ ] Создать workflow `.github/workflows/ci.yml`.
-   [ ] Запускать тесты на версиях Python 3.10 и 3.11, а также на Windows, Linux, macOS.
-   [ ] Добавить шаги `ruff`/`flake8` и `mypy` для анализа кода.
-   [ ] Загружать отчёт о покрытии в `codecov`.

### 3. [ ] Линтеры и статический анализ

-   [ ] Добавить `ruff` или `flake8` в `pyproject.toml` как dev-dependency корневого workspace.
-   [ ] Настроить `pre-commit`-хуки: `black`, `ruff`, `mypy`, `pytest`.

## Фаза 3: Документация

### 1. [ ] Документация

-   [ ] Убедиться, что все ссылки и инструкции актуальны и согласованы.

### 2. [ ] Семантическое версионирование и CHANGELOG

-   [ ] Ввести `CHANGELOG.md` по стандарту Keep a Changelog.
-   [ ] Настроить `commitizen` или аналог для автоматического обновления версии и лога изменений.

## Фаза 4: Финальная уборка и сопровождение

### 1. [ ] Удаление устаревшего кода

-   [ ] Проверить репозиторий на наличие неиспользуемых файлов, временных скриптов и `__pycache__`.
-   [ ] Удалить старые директории, упомянутые в пункте «Завершающие шаги» Фазы 1.

### 2. [ ] Обновление документации и README

-   [ ] Добавить раздел FAQ и техническую поддержку.

## Фаза 5: Публикация пакетов

-   [ ] Создать workflow `publish.yml` для публикации в TestPyPI при пуше тэга `*-beta`.
-   [ ] При пуше тэга `v*.*.*` публиковать пакеты в PyPI.
