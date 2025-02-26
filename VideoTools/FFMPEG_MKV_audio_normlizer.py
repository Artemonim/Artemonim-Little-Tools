import os
import asyncio
import signal
import json
import platform

# =========================
# Конфигурационные переменные
# =========================
INPUT_FOLDER = r"D:/Закачка видео/Сериалы/Evangelion"
OUTPUT_FOLDER = r"G:/Temp/Eva01"
MANUAL_THREAD_LIMIT = 2
AUTO_THREAD_LIMIT_DIVIDER = 3
cpu_count = os.cpu_count() or MANUAL_THREAD_LIMIT
MAX_WORKERS = max(cpu_count // AUTO_THREAD_LIMIT_DIVIDER, MANUAL_THREAD_LIMIT)

# =========================
# Асинхронная обработка файла
# =========================
async def process_file(filename, semaphore):
    async with semaphore:
        input_path = os.path.join(INPUT_FOLDER, filename)
        output_path = os.path.join(OUTPUT_FOLDER, filename)
        proc = None # Для отслеживания запущенных процессов

        try:
            print(f"Обработка файла: {filename}")
            
            # Получаем информацию об аудиодорожках через ffprobe
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
                print(f"Ошибка ffprobe для {filename}: {stderr.decode()}")
                return

            try:
                audio_info = json.loads(stdout.decode())
            except json.JSONDecodeError as e:
                print(f"Ошибка парсинга JSON для {filename}: {e}")
                return

            audio_tracks = []
            for stream in audio_info.get('streams', []):
                index = stream.get('index')
                title = stream.get('tags', {}).get('title', '')
                audio_tracks.append({'index': index, 'title': title})

            if not audio_tracks:
                print(f"Файл {filename} не содержит аудио. Копирование.")
                copy_cmd = f'ffmpeg -i "{input_path}" -c copy "{output_path}"'
                proc = await asyncio.create_subprocess_shell(copy_cmd)
                await proc.communicate()
                return

            # Собираем фильтры и метаданные
            filter_complex = ""
            audio_map = ""
            metadata_options = []
            for i, track in enumerate(audio_tracks):
                filter_complex += f"[0:a:{i}]loudnorm=I=-16:TP=-1.5:LRA=11[a{i}];"
                audio_map += f" -map [a{i}]"
                if track['title']:
                    metadata_options.append(f"-metadata:s:a:{i} title=\"{track['title']}\"")
            filter_complex = filter_complex.rstrip(';')

            # Формируем команду ffmpeg
            ffmpeg_cmd = (
                f'ffmpeg -i "{input_path}" '
                f'-filter_complex "{filter_complex}" '
                f'-map 0:v?{audio_map} -map 0:s? '
                f'-c:v copy -c:s copy -c:a aac '
                f'{" ".join(metadata_options)} '
                f'"{output_path}"'
            )
            print(f"Выполняется: {ffmpeg_cmd}")
            proc = await asyncio.create_subprocess_shell(ffmpeg_cmd)
            await proc.communicate()

        except asyncio.CancelledError:
            print(f"Отмена обработки {filename}")
            if proc and proc.returncode is None:
                proc.terminate()
                await proc.wait()
            raise

# =========================
# Основная функция
# =========================
async def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".mkv")]
    if not files:
        print("Нет MKV файлов для обработки\a")
        return

    # Настройка обработки прерываний
    loop = asyncio.get_running_loop()
    tasks = []
    stop_event = asyncio.Event()

    def signal_handler():
        print("\nПрерывание: остановка задач...")
        stop_event.set()
        for task in tasks:
            task.cancel()

    # Платформозависимая настройка обработчика сигналов
    if platform.system() == 'Windows':
        signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(signal_handler))
    else:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

    semaphore = asyncio.Semaphore(MAX_WORKERS)
    tasks = [asyncio.create_task(process_file(f, semaphore)) for f in files]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        if platform.system() != 'Windows':
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)

    print("Обработка завершена\a" if not stop_event.is_set() else "Прервано пользователем\a")

if __name__ == "__main__":
    asyncio.run(main())