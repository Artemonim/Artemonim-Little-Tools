# Как добавлять инструменты в LittleTools

> **Для опытных пользователей и ИИ-ассистентов:** Существует краткая, сжатая версия этой инструкции, оптимизированная для быстрого ознакомления и экономии контекста. См. [`ADDING_NEW_TOOLS_QUICK.md`](./ADDING_NEW_TOOLS_QUICK.md).

Это руководство объясняет, как добавлять новые инструменты в набор LittleTools. Проект спроектирован так, чтобы основное интерактивное меню (`lt`) автоматически обнаруживало и загружало любые корректно настроенные пакеты-инструменты.

## Основная концепция: Расширение или создание пакетов

Каждый "инструмент" (например, `video-converter`) является частью тематического пакета Python (например, `littletools_video`).

Ваша основная задача при добавлении новой функциональности — решить:

1.  **Расширить существующий пакет?** Если ваша новая функция тесно связана с видео, текстом, аудио и т.д., вам следует добавить ее в соответствующий пакет (`littletools_video`, `littletools_txt`, `littletools_speech`). Это предпочтительный способ, так как он способствует переиспользованию кода.
2.  **Создать новый пакет?** Если ваша функция представляет совершенно новую категорию инструментов (например, работа с архивами или изображениями), тогда следует создать новый пакет.

В обоих случаях важно активно использовать общие утилиты из `littletools-core`, чтобы избежать дублирования кода.

---

## Рекомендация: Загрузка ML-моделей через Hugging Face Hub

Для обеспечения консистентности и упрощения управления моделями машинного обучения (например, Whisper, BERT, и т.д.), настоятельно рекомендуется загружать их из [Hugging Face Hub](https://huggingface.co/).

В `littletools-core` для этого предусмотрена специальная утилита.

**Пример использования:**

```python
# ! bad-practice
# model = whisper.load_model("large-v3") # Загрузка напрямую, может быть нестабильной

# * good-practice
from littletools_core.huggingface_utils import download_hf_model

# 1. Определите ID репозитория модели на Hugging Face Hub
repo_id = "openai/whisper-large-v3"

# 2. Скачайте модель, используя утилиту
# Утилита кэширует модель локально в папке .huggingface в корне проекта
model_path = download_hf_model(repo_id=repo_id)

# 3. Загрузите модель из локального пути
model = whisper.load_model(model_path, device="cuda")
```

Этот подход обеспечивает:

-   **Кэширование:** Модели скачиваются один раз и хранятся локально.
-   **Централизованное управление:** Все модели проходят через единый механизм.
-   **Надежность:** Меньшая зависимость от прямых вызовов API конкретных библиотек для загрузки.

---

## Способ 1: Добавление новой команды в существующий пакет (Предпочтительный)

Это самый частый сценарий. Допустим, мы хотим добавить в пакет `littletools_video` новую команду. В зависимости от сложности команды, есть два подхода.

### Шаг 1: Выберите подход

-   **1A: Простая команда.** Если ваша команда — это одна-две простые функции, лучше добавить её в уже существующий основной файл пакета (например, `video_converter.py`).
-   **1B: Комплексная команда.** Если ваш инструмент — это самодостаточная программа со своей логикой, несколькими функциями и, возможно, специфичными зависимостями (как `ben2-remover`), лучше создать для него отдельный `.py` файл внутри пакета.

---

### Подход 1A: Простая команда (в существующем файле)

Это самый быстрый способ.

1.  **Найдите целевой файл:** Перейдите в папку пакета, например, `littletools_video/littletools_video/`, и найдите файл, который содержит главный объект `typer.Typer`. Обычно он называется по имени основного инструмента, например `video_converter.py`.

2.  **Добавьте вашу команду:** Откройте этот файл и добавьте новую функцию, обернутую в декоратор `@app.command()`.

```python
// ... существующий код ...
from rich.console import Console
from typing_extensions import Annotated

# * Главное приложение Typer для этого пакета уже должно быть определено
# app = typer.Typer(...)

console = Console()

// ... существующие команды ...

@app.command()
def add_watermark(
    input_video: Annotated[Path, typer.Argument(help="Исходный видеофайл.")],
    watermark_image: Annotated[Path, typer.Argument(help="Файл изображения для водяного знака.")],
    output_video: Annotated[Path, typer.Option("--output", "-o", help="Путь для итогового видео.")]
):
    """
    Накладывает изображение водяного знака на видео.
    """
    console.print(f"Накладывание водяного знака [cyan]{watermark_image}[/cyan] на [cyan]{input_video}[/cyan]...")

    # ? Используйте общие функции из этого же пакета, если они есть
    # ? Например, из ffmpeg_utils.py
    #
    # ? Также используйте утилиты из littletools_core
    # from littletools_core.utils import some_helper_function

    # TODO: Здесь должна быть ваша реальная логика с использованием FFMPEG.

    console.print(f"[green]✓ Видео сохранено в [bold]{output_video}[/bold]![/green]")

if __name__ == "__main__":
    app()
```

3.  **Готово!** Поскольку пакет уже зарегистрирован в системе, вам больше ничего не нужно делать. Новая команда автоматически появится в меню.

---

### Подход 1B: Комплексная команда (в новом файле)

Этот подход сохраняет чистоту кода, изолируя сложную логику.

1.  **Создайте файл инструмента:** Внутри папки с исходным кодом пакета (например, `littletools_video/littletools_video/`) создайте новый Python-файл, например `my_watermark_tool.py`.

2.  **Напишите код инструмента:** В этом новом файле создайте полноценное Typer-приложение. Код будет очень похож на создание нового пакета, но файл будет находиться внутри уже существующего.

    ```python
    #!/usr/bin/env python3
    # -*- coding: utf-8 -*-
    from pathlib import Path
    import typer
    from rich.console import Console
    from typing_extensions import Annotated

    # * Этот объект 'app' — то, на что мы будем ссылаться в pyproject.toml
    app = typer.Typer(no_args_is_help=True)
    console = Console()

    @app.command()
    def apply(
        # ... аргументы вашей функции ...
    ):
        """Накладывает водяной знак."""
        # TODO: Логика вашей команды
        console.print("[green]✓ Готово![/green]")

    if __name__ == "__main__":
        app()
    ```

3.  **Зарегистрируйте команду:** Откройте файл `pyproject.toml` родительского пакета (в нашем примере — `littletools_video/pyproject.toml`). Вам нужно добавить ссылку на ваш новый инструмент в двух местах:

    -   `[project.scripts]`: Позволяет запускать скрипт напрямую из командной строки.
    -   `[project.entry-points."littletools.commands"]`: Регистрирует команду в главном меню `lt`.

    ```toml
    # littletools_video/pyproject.toml

    # ... другие секции ...

    [project.scripts]
    # ... существующие скрипты ...
    watermarker = "littletools_video.my_watermark_tool:app"

    [project.entry-points."littletools.commands"]
    # ... существующие команды ...
    watermarker = "littletools_video.my_watermark_tool:app"

    # ...
    ```

4.  **Готово!** Запустите `start.bat` или `start.ps1`. Поскольку вы изменили `pyproject.toml`, установщик перерегистрирует ваш пакет, и новая команда появится в меню. Вам **не нужно** редактировать `start.ps1`, так как родительский пакет `littletools_video` уже включен в установку.

---

## Способ 2: Создание нового тематического пакета-инструмента

Используйте этот способ, только если ваша новая функциональность не вписывается ни в один из существующих пакетов.

Допустим, мы хотим создать новый инструмент под названием `archive` для работы с ZIP-файлами.

### Шаг 1: Создайте структуру пакета

1.  В корне проекта `LittleTools` создайте новую папку для вашего пакета. Соглашение об именовании — `littletools_themename`.

    ```
    /littletools_archive
    ```

2.  Внутри этой папки создайте еще одну папку с таким же названием. Здесь будет находиться ваш код на Python. Также создайте в ней пустой файл `__init__.py`.
    ```
    /littletools_archive
        /littletools_archive
            __init__.py
    ```

### Шаг 2: Создайте файл `pyproject.toml`

Это самый важный файл для интеграции. Создайте файл с именем `pyproject.toml` в папке верхнего уровня `littletools_archive`.

```
/littletools_archive
    pyproject.toml  <-- СОЗДАЙТЕ ЭТОТ ФАЙЛ
    /littletools_archive
```

Скопируйте и вставьте этот шаблон в ваш `pyproject.toml` и измените выделенные секции:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
# --- 1. ИЗМЕНИТЕ ЭТО ---
name = "littletools-archive"
version = "0.1.0"
description = "Инструмент для работы с архивами."
# --------------------

dependencies = [
    "littletools-core", # ! Важная зависимость от общих утилит ядра
    "typer[all]>=0.9.0",
    # Добавьте любые другие зависимости, необходимые вашему инструменту, например, "zipp"
]
requires-python = ">=3.8"

# --- 2. ЭТО МАГИЯ ---
# Эта секция сообщает главному меню, что данный пакет предоставляет команду.
[project.entry-points."littletools.commands"]
# `archive` — это имя, которое появится в меню.
# `littletools_archive.main:app` — указывает на объект `app` в файле `main.py`.
archive = "littletools_archive.main:app"
# --------------------------

[tool.setuptools.packages.find]
where = ["."]
```

### Шаг 3: Напишите код инструмента

Теперь создайте файл Python, содержащий логику вашего инструмента. Согласно нашему `pyproject.toml`, этот файл должен называться `main.py`.

```
/littletools_archive
    /littletools_archive
        __init__.py
        main.py  <-- СОЗДАЙТЕ ЭТОТ ФАЙЛ
```

Вот простой шаблон для `main.py` с использованием `typer` и стилем комментариев "Better Comments":

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Инструмент для архивации - часть набора LittleTools.
"""
from pathlib import Path
import typer
from rich.console import Console
from typing_extensions import Annotated

# * Создаем приложение Typer для этого конкретного инструмента.
# * Этот объект 'app' — то, на что ссылается точка входа в pyproject.toml.
app = typer.Typer(
    name="archive",
    help="Инструмент для создания и извлечения ZIP-архивов.",
    no_args_is_help=True
)

console = Console()

@app.command()
def create(
    archive_path: Annotated[Path, typer.Option("--output", "-o", help="Путь для нового ZIP-файла.")],
    files_to_add: Annotated[list[Path], typer.Argument(help="Файлы или папки для добавления в архив.")]
):
    """
    Создает новый ZIP-архив из указанных файлов и папок.
    """
    console.print(f"Создание архива: [cyan]{archive_path}[/cyan]")
    for file in files_to_add:
        console.print(f"  -> Добавление [yellow]{file}[/yellow]...")

    # TODO: Здесь должна быть ваша реальная логика архивации.

    console.print("[green]✓ Архив успешно создан![/green]")

@app.command()
def extract(
    archive_path: Annotated[Path, typer.Argument(help="ZIP-файл для извлечения.")],
    destination: Annotated[Path, typer.Option("--output", "-o", help="Папка для извлечения файлов.")]
):
    """
    Извлекает ZIP-архив в папку назначения.
    """
    console.print(f"Извлечение [cyan]{archive_path}[/cyan] в [cyan]{destination}[/cyan]...")

    # TODO: Здесь должна быть ваша реальная логика распаковки.

    console.print("[green]✓ Архив успешно извлечен![/green]")

if __name__ == "__main__":
    app()
```

### Шаг 4: Добавьте инструмент в установщик

Последний шаг — сообщить основному скрипту установки, что нужно установить ваш новый пакет.

1.  Откройте `start.ps1`.
2.  Найдите строку, которая начинается с `& $VenvPython -m pip install ...`.
3.  Добавьте `-e ./littletools_archive` в конец этой строки. Она должна выглядеть так:

    ```powershell
    # Было
    & $VenvPython -m pip install -e ./littletools_cli -e ./littletools_core -e ./littletools_speech -e ./littletools_txt -e ./littletools_video

    # Стало
    & $VenvPython -m pip install -e ./littletools_cli -e ./littletools_core -e ./littletools_speech -e ./littletools_txt -e ./littletools_video -e ./littletools_archive
    ```

### Шаг 5: Запустите установщик

Вот и все! Теперь просто запустите `start.bat` или `start.ps1` из корня проекта. Скрипт найдет ваш новый пакет `littletools_archive`, установит его, и когда запустится интерактивное меню, вы увидите "**archive**" как новую, полностью функционирующую опцию.
