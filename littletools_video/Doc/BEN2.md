Вот сводная, пошаговая инструкция по установке и использованию BEN2 с автоматической загрузкой весов и пакетной обработкой видео:

---

## 1. Подготовка окружения

```bash
# Клонируем репозиторий и переходим в папку
git clone https://github.com/PramaLLC/BEN2.git
cd BEN2

# Устанавливаем зависимости
pip install -r requirements.txt      # PyTorch, OpenCV, ffmpeg и пр.
pip install huggingface_hub         # для автозагрузки весов
sudo apt update && sudo apt install ffmpeg   # если ffmpeg не установлен
```

---

## 2. Автозагрузка весов из Hugging Face Hub

```python
from huggingface_hub import hf_hub_download
import torch
from ben2 import BEN2

# 1) Загружаем файл весов (кэшируется в ~/.cache/huggingface/hub)
weights_path = hf_hub_download(
    repo_id="PramaLLC/BEN2",
    filename="BEN2_Base.pth"
)

# 2) Инициализируем модель
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = BEN2.BEN_Base().to(device).eval()

# 3) Загружаем веса в модель
model.loadcheckpoints(weights_path)
```

---

## 3. Обработка одного видео

```python
model.segment_video(
    video_path="input.mp4",      # ваш входной файл
    output_path="output_dir/",   # папка для результатов
    fps=0,                       # 0 — сохраняет fps исходника
    batch=1,                     # оптимально: 1–3
    refine_foreground=False,     # True → чуть более аккуратные края
    webm=True,                   # True → .webm с альфа‑каналом
    rgb_value=(0, 0, 0),         # фоновой цвет, если webm=False
    print_frames_processed=True
)
```

* В `output_dir/` появится `foreground.webm` (или `foreground.mp4`), где главный объект вырезан на прозрачном или заданном фоне.

---

## 4. Пакетная обработка «кучи» видео

```python
import os

# Список файлов
videos = ["a.mp4", "b.mp4", "c.mp4"]

for vid in videos:
    name, _ = os.path.splitext(os.path.basename(vid))
    out_dir = f"processed/{name}/"
    os.makedirs(out_dir, exist_ok=True)

    model.segment_video(
        video_path=vid,
        output_path=out_dir,
        webm=True,
        batch=1
    )
```

* Итог: для каждого `vid` создаётся своя папка `processed/<имя>/` с вырезанным видео.

---

## 5. Рекомендации по параметрам

* **batch=1–3**: больше батч → выше нагрузка на VRAM, но чуть быстрее.
* **refine\_foreground=True**: добавляет дополнительную тонкую дообработку краёв (порядка +10 % времени).
* **webm vs mp4**:

  * `webm=True` → итог с альфа‑каналом (прозрачность).
  * `webm=False` → mp4, фон окрашивается в `rgb_value`.
* **fps=0**: сохранять fps оригинала; можно задать число, если нужно понизить/повысить частоту.

---

Теперь вы можете «скармливать» BEN2 любое количество видео и автоматически получать результат с отделённым главным объектом. Удачной работы!
