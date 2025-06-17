# План рефакторинга LittleTools

Этот документ описывает шаги по преобразованию проекта из набора разрозненных скриптов в управляемую, модульную экосистему пакетов на основе `pyproject.toml`.

## Фаза 1: Модуляризация и пакетирование

### 1. [ ] Создание базового пакета `littletools-core`

-   [ ] Создать директорию `littletools_core`.
-   [ ] Переместить `little_tools_utils.py` внутрь `littletools_core/`, возможно, переименовав его в `utils.py`.
-   [ ] Создать `littletools_core/__init__.py` для оформления в виде пакета.
-   [ ] Создать `littletools_core/pyproject.toml`. Указать минимальные метаданные (имя, версия, автор). Зависимостей у этого пакета быть не должно.
-   [ ] **(Ключевой шаг)** Пройти по всем скриптам проекта (`menu.py`, все утилиты) и заменить локальные импорты на импорты из нового пакета (например, `from little_tools_utils import ...` на `from littletools_core.utils import ...`).

### 2. [ ] Выделение `Infinite Differ` в отдельный репозиторий

-   [ ] Создать новый Git-репозиторий (например, `InfiniteDiffer`).
-   [ ] Перенести содержимое `TxtTools/MultipleTextComparator` в новый репозиторий.
-   [ ] В новом репозитории создать `pyproject.toml`, указав `PyQt6` как основную зависимость.
-   [ ] Добавить `README.md` с инструкцией по установке и запуску.
-   [ ] Удалить `TxtTools/MultipleTextComparator` из репозитория `LittleTools`.
-   [ ] Удалить запись о `"infinite_differ"` из словаря `TOOLS` в `menu.py`.

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
