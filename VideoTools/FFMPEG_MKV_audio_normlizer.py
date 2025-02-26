import os
import math
import asyncio

# =========================
# Конфигурационные переменные
# =========================
INPUT_FOLDER = r"C:\Path\To\InputFolder"       # путь к папке с исходными .mkv файлами
OUTPUT_FOLDER = r"C:\Path\To\OutputFolder"       # путь к папке для сохранения результатов
# Определяем количество потоков: половина ядер или 4, если не удалось получить число ядер
cpu_count = os.cpu_count() if os.cpu_count() is not None else 4
MAX_WORKERS = cpu_count // 2 if cpu_count // 2 > 0 else 4

# =========================
# Асинхронная обработка файла
# =========================
async def process_file(filename, semaphore):
    async with semaphore:
        input_path = os.path.join(INPUT_FOLDER, filename)
        output_path = os.path.join(OUTPUT_FOLDER, filename)

        print(f"Обработка файла: {filename}")
        
        # Получаем список аудиодорожек через ffprobe
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=index", "-of", "csv=p=0", f'"{input_path}"'
        ]
        # ffprobe не требует shell-интерпретации, поэтому можно объединить команду в строку
        ffprobe_proc = await asyncio.create_subprocess_shell(
            " ".join(ffprobe_cmd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await ffprobe_proc.communicate()
        audio_indices = stdout.decode().strip().splitlines()
        
        # Если аудиодорожек нет, копируем файл без изменений
        if not audio_indices:
            print(f"Файл {filename} не содержит аудио. Копирование без изменений.")
            copy_cmd = f'ffmpeg -i "{input_path}" -c copy "{output_path}"'
            proc = await asyncio.create_subprocess_shell(copy_cmd)
            await proc.communicate()
            return
        
        # Строим фильтр для каждой аудиодорожки
        filter_complex = ""
        audio_map = ""
        for i in range(len(audio_indices)):
            filter_complex += f"[0:a:{i}]loudnorm=I=-16:TP=-1.5:LRA=11[a{i}];"
            audio_map += f" -map [a{i}]"
        # Удаляем завершающую точку с запятой, если она есть
        if filter_complex.endswith(";"):
            filter_complex = filter_complex[:-1]
        
        # Собираем команду ffmpeg:
        # -map 0:v? копирует все видеодорожки (если они есть)
        # -map 0:s? копирует все дорожки субтитров (если они есть)
        ffmpeg_cmd = (
            f'ffmpeg -i "{input_path}" '
            f'-filter_complex "{filter_complex}" '
            f'-map 0:v?{audio_map} -map 0:s? '
            f'-c:v copy -c:s copy -c:a aac '
            f'"{output_path}"'
        )
        
        print("Выполняется команда:", ffmpeg_cmd)
        proc = await asyncio.create_subprocess_shell(ffmpeg_cmd)
        await proc.communicate()

# =========================
# Основная функция
# =========================
async def main():
    # Создаём выходную папку, если её нет
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # Сбор списка .mkv файлов из входной папки
    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".mkv")]
    if not files:
        print("Входная папка не содержит файлов с расширением .mkv")
        return

    semaphore = asyncio.Semaphore(MAX_WORKERS)
    tasks = [asyncio.create_task(process_file(filename, semaphore)) for filename in files]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
