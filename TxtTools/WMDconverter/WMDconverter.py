"""Скрипт для конвертации файлов между DOCX и Markdown с извлечением изображений."""

import os
import pypandoc
import argparse

# Configuration variables
SOURCE_PATH = "1_WK-10C挖掘机电气产品说明书（中俄）.docx"  # Путь к исходному файлу по умолчанию
OUTPUT_PATH = "1_WK-10C挖掘机电气产品说明书（中俄）.md"   # Путь к выходному файлу по умолчанию
MEDIA_DIR = "media"         # Папка для хранения изображений по умолчанию


def convert_docx_to_md(source_path, output_path, media_dir):
    """Конвертирует DOCX файл в Markdown, извлекая изображения в указанную папку.

    Args:
        source_path (str): Путь к исходному DOCX файлу.
        output_path (str): Путь к выходному Markdown файлу.
        media_dir (str): Папка для хранения изображений.

    Raises:
        FileNotFoundError: Если исходный файл не существует.
        RuntimeError: Если pandoc не установлен или возникла ошибка при конвертации.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Исходный файл {source_path} не найден.")

    if not os.path.exists(media_dir):
        os.makedirs(media_dir)

    pypandoc.convert_file(
        source_path,
        "md",
        outputfile=output_path,
        extra_args=[f"--extract-media={media_dir}"]
    )


def convert_md_to_docx(source_path, output_path, media_dir, reference_docx):
    """Конвертирует Markdown файл в DOCX, используя эталонный DOCX для форматирования.

    Args:
        source_path (str): Путь к исходному Markdown файлу.
        output_path (str): Путь к выходному DOCX файлу.
        media_dir (str): Папка с изображениями.
        reference_docx (str): Путь к эталонному DOCX файлу.

    Raises:
        FileNotFoundError: Если исходный файл или эталонный DOCX не найдены.
        RuntimeError: Если pandoc не установлен или возникла ошибка при конвертации.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Исходный файл {source_path} не найден.")
    if not os.path.exists(reference_docx):
        raise FileNotFoundError(f"Эталонный DOCX файл {reference_docx} не найден.")

    pypandoc.convert_file(
        source_path,
        "docx",
        outputfile=output_path,
        extra_args=[f"--reference-doc={reference_docx}"]
    )


def parse_arguments():
    """Разбирает аргументы командной строки.

    Returns:
        argparse.Namespace: Объект с разобранными аргументами.
    """
    parser = argparse.ArgumentParser(
        description="Конвертация файлов между DOCX и Markdown с извлечением изображений."
    )
    parser.add_argument(
        "--source",
        default=SOURCE_PATH,
        help="Путь к исходному файлу (по умолчанию: input.docx)"
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_PATH,
        help="Путь к выходному файлу (по умолчанию: output.md)"
    )
    parser.add_argument(
        "--media-dir",
        default=MEDIA_DIR,
        help="Папка для хранения изображений (по умолчанию: media)"
    )
    parser.add_argument(
        "--reference-docx",
        default="reference.docx",
        help="Путь к эталонному DOCX файлу для конвертации MD в DOCX (по умолчанию: reference.docx)"
    )
    return parser.parse_args()


def main():
    """Основная функция для выполнения конвертации."""
    args = parse_arguments()

    source_ext = os.path.splitext(args.source.lower())[1]

    try:
        if source_ext == ".docx":
            convert_docx_to_md(args.source, args.output, args.media_dir)
            print(f"Успешно сконвертирован {args.source} в {args.output}")
        elif source_ext == ".md":
            convert_md_to_docx(args.source, args.output, args.media_dir, args.reference_docx)
            print(f"Успешно сконвертирован {args.source} в {args.output}")
        else:
            print("Неподдерживаемый формат файла. Используйте .docx или .md.")
    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
    except Exception as e:
        print(f"Произошла ошибка при конвертации: {e}")


if __name__ == "__main__":
    main()