import json
import os

# === Конфигурационные переменные ===
INPUT_FILE = r"C:/Users/Artem/Downloads/Telegram Desktop/ChatExport_2025-03-03/result.json"      # Абсолютный путь к входному файлу
OUTPUT_FILE = r"C:/Users/Artem/Downloads/Telegram Desktop/ChatExport_2025-03-03/result_distilled.json"

def main():
    # Проверка существования входного файла
    if not os.path.exists(INPUT_FILE):
        print(f"Входной файл не найден: {INPUT_FILE}")
        return

    # Загрузка JSON-данных из файла
    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Извлечение списка сообщений
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        print("Неверный формат файла: ключ 'messages' должен содержать список")
        return

    new_messages = []
    for message in messages:
        # Получаем блок text_entities (если его нет, считается пустым)
        text_entities = message.get("text_entities", [])
        if not text_entities:  # Пропускаем сообщение, если text_entities пустой
            continue

        # Объединяем все части text_entities в одну строку
        combined_text = ""
        for entity in text_entities:
            # Если элемент является словарём, берем значение ключа "text"
            if isinstance(entity, dict):
                combined_text += entity.get("text", "")
            # Если вдруг элемент уже строка – просто добавляем его
            elif isinstance(entity, str):
                combined_text += entity

        # Формируем новое сообщение с обязательными тегами id, date и photo, а также с объединённым text_entities
        new_message = {
            "id": message.get("id"),
            "date": message.get("date"),
            "photo": message.get("photo"),
            "text_entities": combined_text
        }
        new_messages.append(new_message)

    # Обновляем структуру данных – можно сохранить и другие ключи из исходного файла, если нужно
    data["messages"] = new_messages

    # Запись результата в выходной файл
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    print(f"Результат записан в {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
