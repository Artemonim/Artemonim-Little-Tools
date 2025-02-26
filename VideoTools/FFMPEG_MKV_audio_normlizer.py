import os
import subprocess

# Задайте пути к входной и выходной папкам
input_folder = r"C:\Path\To\InputFolder"    # замените на путь к вашей папке с файлами .mkv
output_folder = r"C:\Path\To\OutputFolder"  # замените на путь к выходной папке

# Если выходная папка не существует, создаём её
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Проходим по всем файлам во входной папке
for filename in os.listdir(input_folder):
    if filename.lower().endswith(".mkv"):
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)
        
        # Получаем список аудиодорожек через ffprobe
        ffprobe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=index", "-of", "csv=p=0", input_path
        ]
        result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        audio_indices = result.stdout.strip().splitlines()
        
        # Если аудиодорожек нет, можно просто копировать файл
        if not audio_indices:
            print(f"Файл {filename} не содержит аудио. Копирование без изменений.")
            copy_cmd = f'ffmpeg -i "{input_path}" -c copy "{output_path}"'
            subprocess.run(copy_cmd, shell=True)
            continue
        
        # Строим фильтр для каждой аудиодорожки
        filter_complex = ""
        audio_map = ""
        for i in range(len(audio_indices)):
            filter_complex += f"[0:a:{i}]loudnorm=I=-16:TP=-1.5:LRA=11[a{i}];"
            audio_map += f" -map [a{i}]"
        # Удаляем завершающую точку с запятой (если необходимо)
        if filter_complex.endswith(";"):
            filter_complex = filter_complex[:-1]
        
        # Собираем команду ffmpeg:
        # -map 0:v? копирует все видеодорожки (если они есть)
        # -map 0:s? копирует все дорожки субтитров (если они есть)
        # Для аудио используем обработанные потоки из фильтра
        ffmpeg_cmd = (
            f'ffmpeg -i "{input_path}" '
            f'-filter_complex "{filter_complex}" '
            f'-map 0:v?{audio_map} -map 0:s? '
            f'-c:v copy -c:s copy -c:a aac '
            f'"{output_path}"'
        )
        
        print("Выполняется команда:", ffmpeg_cmd)
        subprocess.run(ffmpeg_cmd, shell=True)
