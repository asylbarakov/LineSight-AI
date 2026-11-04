"""Классы объектов и дефектов: что считать дефектом и как называть по-русски.

Точные названия классов зависят от обученной модели (`data.yaml`), поэтому дефект
определяется по ключевым словам в имени класса, а не по жёсткому списку.
"""

from __future__ import annotations

import re

# Если имя класса содержит одно из этих слов — это дефект/проблема, а не просто оборудование.
DEFECT_KEYWORDS = (
    "crack", "damage", "flashover", "breakage", "broken", "loose", "missing", "overheat",
    "aging", "discolor", "breakdown", "nest", "foreign", "vegetation", "chipping",
    "detach", "contact", "defect", "corrosion", "rust",
)

# Русские названия классов оборудования подстанции (подмножество датасета, 18 классов).
RU_EQUIPMENT = {
    "capacitor": "Конденсатор",
    "bus": "Шина",
    "pipe": "Трубопровод",
    "filter": "Фильтр",
    "gis": "КРУЭ",
    "bushing": "Ввод",
    "switch": "Разъединитель",
    "line": "Линия",
    "pt": "Трансформатор напряжения",
    "breaker": "Выключатель",
    "arrester": "Разрядник",
    "insulator": "Изолятор",
    "connecting_port": "Соединительный вывод",
    "ct": "Трансформатор тока",
    "pedestal": "Опорная конструкция",
    "resistor": "Резистор",
    "tower": "Опора",
    "frame": "Рама",
    "low_visibility": "Недостаточная видимость",
}

# Классы подмножества «transmission line object detection» (sxiong/Power-equipment-image-dataset):
# в разметке — пиньинь-коды. Все 14 классов — дефекты или опасные объекты на линии.
# Расшифровка взята из описания датасета на Hugging Face.
DATASET_CLASSES = {
    "blq_jyjc": ("Surge arrester insulation breakdown", "Разрядник: пробой изоляции"),
    "blq_lh": ("Surge arrester aging", "Разрядник: старение"),
    "blq_ps": ("Surge arrester damage", "Разрядник: повреждение"),
    "blq_yxdk": ("Surge arrester ground lead broken", "Разрядник: обрыв заземляющего вывода"),
    "czjyz_lw": ("Porcelain post insulator crack", "Опорный изолятор: трещина"),
    "czjyz_ps": ("Porcelain post insulator damage", "Опорный изолятор: повреждение"),
    "czjyz_sl": ("Porcelain post insulator flashover", "Опорный изолятор: следы перекрытия"),
    "dx_dg": ("Conductor strand breakage", "Провод: обрыв жил"),
    "dx_jypps": ("Conductor insulation damage", "Провод: повреждение изоляции"),
    "dx_sg": ("Conductor strand loosening", "Провод: ослабление скрутки жил"),
    "jj_jxps": ("Line hardware terminal connection damage", "Арматура: повреждение соединения вывода"),
    "nw": ("Bird nest on line", "Гнездо птицы на линии"),
    "yw": ("Foreign object", "Посторонний предмет на линии"),
    "yxdk": ("Ground lead broken", "Обрыв заземляющего вывода"),
}


def normalize(name: str) -> str:
    """'Porcelain post insulator-crack' → 'porcelain_post_insulator_crack'."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def is_defect(name: str) -> bool:
    n = normalize(name)
    if n in DATASET_CLASSES:
        return True
    return any(k in n for k in DEFECT_KEYWORDS)


def ru_name(name: str) -> str:
    """Русское название класса; для неизвестных возвращает исходное имя."""
    n = normalize(name)
    if n in DATASET_CLASSES:
        return DATASET_CLASSES[n][1]
    if n in RU_EQUIPMENT:
        return RU_EQUIPMENT[n]
    return ("Дефект: " if is_defect(n) else "") + name.replace("_", " ")
