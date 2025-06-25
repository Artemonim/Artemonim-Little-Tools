# Краткое руководство: Добавление инструментов в LittleTools

Это руководство предназначено для быстрого ознакомления и использования ИИ-ассистентами.

> **Полная версия:** [`ADDING_NEW_TOOLS.md`](./ADDING_NEW_TOOLS.md).

## Основной принцип

1.  **Предпочитайте расширение.** Найдите подходящий тематический пакет (`video`, `txt` и т.д.) и добавьте свою команду в него.
2.  **Создавайте новое, только если нет аналогов.** Если инструмент относится к совершенно новой категории, создайте новый пакет.
3.  **Используйте `littletools-core`** для общих утилит.

---

## Способ 1: Расширить существующий пакет (90% случаев)

1.  **Найдите файл:** Перейдите в `littletools_<theme>/littletools_<theme>/` и откройте основной файл с объектом `typer.Typer` (обычно `main.py` или `*_converter.py`).
2.  **Добавьте команду:**

    ```python
    // ... существующий код, включая app = typer.Typer(...)

    @app.command()
    def my_new_feature(
        param: Annotated[Path, typer.Argument(...)],
    ):
        """Краткое описание новой функции."""
        # Ваша логика здесь.
        # Используйте утилиты из `littletools_core.utils`
        # и тематические утилиты (напр. `ffmpeg_utils`)
        console.print("Готово!")
    ```

3.  **Все.** Больше ничего не требуется. Запустите `start.ps1`, чтобы проверить.

---

## Способ 2: Создать новый пакет

1.  **Структура папок:**

    ```
    /littletools_newname
        /littletools_newname
            __init__.py
            main.py
        pyproject.toml
    ```

2.  **Заполните `pyproject.toml`:**

    ```toml
    [build-system]
    requires = ["setuptools>=61.0"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "littletools-newname"
    version = "0.1.0"
    dependencies = [ "littletools-core", "typer[all]>=0.9.0" ]

    [project.entry-points."littletools.commands"]
    newname = "littletools_newname.main:app"
    ```

3.  **Создайте `main.py`:**

    ```python
    import typer
    from littletools_core import some_util_if_needed

    app = typer.Typer(name="newname", no_args_is_help=True)

    @app.command()
    def main_command():
        pass # Логика

    if __name__ == "__main__":
        app()
    ```

4.  **Обновите `start.ps1`:**
    Найдите строку `pip install` и добавьте `-e ./littletools_newname`.

5.  **Запустите `start.ps1`** для установки и проверки.
