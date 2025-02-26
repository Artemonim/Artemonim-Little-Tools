import os
import asyncio
import signal
import json
import platform
import time
from collections import defaultdict

# =========================
# Конфигурационные переменные
# =========================
INPUT_FOLDER = r"D:/Закачка видео/Сериалы/[Beatrice-Raws] Neon Genesis Evangelion - The End of Evangelion [BDRip 1920x1080 HEVC TrueHD].mkv"
OUTPUT_FOLDER = r"G:/Temp/Eva01"
MANUAL_THREAD_LIMIT = 2
AUTO_THREAD_LIMIT_DIVIDER = 3
OVERWRITE_OUTPUT = False  # Флаг перезаписи существующих файлов
cpu_count = os.cpu_count() or MANUAL_THREAD_LIMIT
MAX_WORKERS = max(cpu_count // AUTO_THREAD_LIMIT_DIVIDER, MANUAL_THREAD_LIMIT)

# Статистика выполнения
stats = defaultdict(int)
start_time = time.monotonic()

# =========================
# Вспомогательные функции
# =========================
def print_separator():
    print("\n" + "═" * 50 + "\n")

def print_file_info(filename, current, total):
    print(f"Обработка файла [{current}/{total}]: {filename}")
    print(f"Осталось задач: {total - current}")

def print_final_stats():
    duration = time.monotonic() - start_time
    print_separator()
    print("ИТОГОВАЯ СТАТИСТИКА:")
    print(f"Всего файлов: {stats['total']}")
    print(f"Успешно обработано: {stats['processed']}")
    print(f"Пропущено: {stats['skipped']}")
    print(f"Ошибок: {stats['errors']}")
    print(f"Затраченное время: {duration:.2f} секунд")
    print_separator()

# =========================
# Асинхронная обработка файла
# =========================
async def process_file(filename, semaphore, file_num, total_files):
    async with semaphore:
        stats['total'] += 1
        if os.path.isdir(INPUT_FOLDER):
            input_path = os.path.join(INPUT_FOLDER, filename)
        else:
            input_path = INPUT_FOLDER
        if os.path.isdir(INPUT_FOLDER):
            output_path = os.path.join(OUTPUT_FOLDER, filename)
        else:
            output_path = os.path.join(OUTPUT_FOLDER, os.path.basename(INPUT_FOLDER))
        proc = None

        print_separator()
        print_file_info(filename, file_num, total_files)

        try:
            # Проверка существования файла
            if os.path.exists(output_path):
                if OVERWRITE_OUTPUT:
                    print(f"Файл существует, перезаписываем: {filename}")
                else:
                    print(f"Файл существует, пропускаем: {filename}")
                    stats['skipped'] += 1
                    return

            # Получаем информацию об аудиодорожках
            ffprobe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index:stream_tags=title",
                "-print_format", "json", f'"{input_path}"'
            ]
            ffprobe_proc = await asyncio.create_subprocess_shell(
                " ".join(ffprobe_cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await ffprobe_proc.communicate()
            
            if ffprobe_proc.returncode != 0:
                print(f"Ошибка ffprobe: {stderr.decode()}")
                stats['errors'] += 1
                return

            try:
                audio_info = json.loads(stdout.decode())
            except json.JSONDecodeError as e:
                print(f"Ошибка парсинга JSON: {e}")
                stats['errors'] += 1
                return

            audio_tracks = audio_info.get('streams', [])
            if not audio_tracks:
                print(f"Нет аудиодорожек. Копирование файла: {filename}")
                copy_cmd = f'ffmpeg -y -i "{input_path}" -c copy "{output_path}"' if OVERWRITE_OUTPUT \
                    else f'ffmpeg -i "{input_path}" -c copy "{output_path}"'
                proc = await asyncio.create_subprocess_shell(copy_cmd)
                await proc.communicate()
                stats['processed'] += 1
                return

            # Формирование команды FFmpeg
            filter_complex = "".join(
                f"[0:a:{i}]loudnorm=I=-16:TP=-1.5:LRA=11[a{i}];"
                for i in range(len(audio_tracks))
            )
            filter_complex = filter_complex.rstrip(';')

            metadata_options = []
            for i, track in enumerate(audio_tracks):
                title = track.get('tags', {}).get('title', '')
                if title:
                    metadata_options.append(f"-metadata:s:a:{i} title=\"{title}\"")

            overwrite_flag = "-y " if OVERWRITE_OUTPUT else ""
            ffmpeg_cmd = (
                f'ffmpeg {overwrite_flag}-i "{input_path}" '
                f'-filter_complex "{filter_complex}" '
                f'-map 0:v? -map 0:s? '
                f'{" ".join(["-map [a" + str(i) + "]" for i in range(len(audio_tracks))])} '
                f'-c:v copy -c:s copy -c:a aac '
                f'{" ".join(metadata_options)} '
                f'"{output_path}"'
            )

            print(f"Выполняется команда:\n{ffmpeg_cmd}")
            proc = await asyncio.create_subprocess_shell(ffmpeg_cmd)
            await proc.communicate()
            
            if proc.returncode == 0:
                stats['processed'] += 1
            else:
                stats['errors'] += 1

        except Exception as e:
            print(f"Ошибка при проверке файла: {e}")
            stats['errors'] += 1
            return

        except asyncio.CancelledError:
            print(f"Отмена обработки: {filename}")
            if proc and proc.returncode is None:
                proc.terminate()
                await proc.wait()
            stats['errors'] += 1
            raise

# =========================
# Основная функция
# =========================
async def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    if os.path.isdir(INPUT_FOLDER):
        files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".mkv")]
    else:
        files = [os.path.basename(INPUT_FOLDER)]
    total_files = len(files)
    if not files:
        print("Нет MKV файлов для обработки\a")
        return

    # Настройка обработки прерываний
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        print("\nПрерывание: остановка задач...")
        stop_event.set()
        for task in tasks:
            task.cancel()

    if platform.system() == 'Windows':
        signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(signal_handler))
    else:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

    semaphore = asyncio.Semaphore(MAX_WORKERS)
    tasks = [
        asyncio.create_task(process_file(f, semaphore, i+1, total_files))
        for i, f in enumerate(files)
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        if platform.system() != 'Windows':
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)

    print_final_stats()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_final_stats()