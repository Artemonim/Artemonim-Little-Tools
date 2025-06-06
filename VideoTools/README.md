# VideoTools - Инструменты для обработки видео

Набор скриптов для обработки видео файлов с помощью FFmpeg, специализирующихся на нормализации аудио и объединении аудио/видео потоков.

## Основные инструменты

### 1. FFMPEG_MKV_audio_normalizer.py

Нормализует аудиодорожки в MKV файлах, применяя стандарт громкости EBU R128 (loudnorm).

**Основные возможности:**

-   Обработка нескольких MKV файлов асинхронно
-   Анализ и нормализация всех аудиодорожек
-   Сохранение метаданных, названий аудиодорожек и субтитров
-   Настраиваемые параметры нормализации (интегральная громкость, пиковый уровень, диапазон громкости)
-   Отображение прогресса FFmpeg в реальном времени

**Использование:**

```bash
python FFMPEG_MKV_audio_normalizer.py [options]

# Примеры:
# Обработка файлов в текущей директории:
python FFMPEG_MKV_audio_normalizer.py

# Указание входной и выходной директорий:
python FFMPEG_MKV_audio_normalizer.py -i /путь/к/входным/файлам -o /путь/к/выходным/файлам

# Разрешение перезаписи существующих файлов:
python FFMPEG_MKV_audio_normalizer.py --overwrite

# Установка конкретного числа потоков обработки:
python FFMPEG_MKV_audio_normalizer.py --threads 4

# Настройка параметров нормализации:
python FFMPEG_MKV_audio_normalizer.py --target-loudness -18 --true-peak -2.0 --loudness-range 9

# Отключение вывода прогресса:
python FFMPEG_MKV_audio_normalizer.py --quiet
```

### 2. Topaz_Video_Merger.py

Объединяет аудио из одного файла с видео из другого файла, одновременно нормализуя аудио.

**Основные возможности:**

-   Объединение аудио/субтитров из первичного источника с видео из вторичного
-   Нормализация аудио в процессе объединения
-   Оптимизированное кодирование HEVC (H.265) с настройками для минимизации артефактов
-   Сохранение метаданных и названий аудиодорожек
-   Отображение прогресса кодирования в реальном времени

**Использование:**

```bash
python Topaz_Video_Merger.py [options]

# Примеры:
# Базовая обработка с указанием первичного и вторичного файлов:
python Topaz_Video_Merger.py -i1 первичный.mkv -i2 видео_источник.mp4

# Указание выходной директории и 4 потоков:
python Topaz_Video_Merger.py -i1 первичный.mkv -i2 видео_источник.mp4 -o выходная_папка --threads 4

# Настройка качества HEVC (меньше = лучше):
python Topaz_Video_Merger.py -i1 первичный.mkv -i2 видео_источник.mp4 --crf 20

# Отключение вывода прогресса:
python Topaz_Video_Merger.py -i1 первичный.mkv -i2 видео_источник.mp4 --quiet
```

## Архитектура

Оба инструмента используют общий модуль `ffmpeg_utils.py`, который предоставляет унифицированные функции для:

-   Форматирования вывода в консоль
-   Анализа аудиодорожек
-   Построения фильтров нормализации
-   Управления асинхронной обработкой
-   Обработки сигналов прерывания (Ctrl+C)
-   Управления файлами и путями
-   Отображения прогресса выполнения FFmpeg

## Вывод прогресса

Инструменты отображают стандартный прогресс выполнения FFmpeg в реальном времени:

-   Информация о количестве кадров (frame=)
-   Текущая позиция обработки (time=)
-   Размер выходного файла (size=)
-   Скорость кодирования (speed=)

Вывод прогресса для каждого файла обновляется непосредственно из FFmpeg, давая точное представление о ходе кодирования.

## Требования

-   Python 3.7+
-   FFmpeg с поддержкой фильтра loudnorm и кодека x265
-   ffprobe

## Установка FFmpeg

### Windows

```bash
# С помощью Chocolatey
choco install ffmpeg

# Или скачайте статическую сборку с https://ffmpeg.org/download.html
```

### macOS

```bash
# С помощью Homebrew
brew install ffmpeg
```

### Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch
sudo pacman -S ffmpeg
```

## Параметры нормализации аудио

Основные параметры регулировки нормализации:

-   `--target-loudness` - Целевая интегральная громкость в LUFS (по умолчанию: -16.0)
-   `--true-peak` - Максимальный пиковый уровень в dBTP (по умолчанию: -1.5)
-   `--loudness-range` - Целевой диапазон громкости в LU (по умолчанию: 11.0)

## Примечания

-   Скрипты обрабатывают прерывание по Ctrl+C, корректно завершая выполняющиеся задачи
-   Прогресс обработки отображается напрямую из FFmpeg в реальном времени
-   По завершении выводится статистика обработки (успешно, пропущено, ошибки)
-   Для отключения вывода прогресса используйте флаг `--quiet`
