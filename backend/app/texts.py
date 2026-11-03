"""Русские шаблоны описаний находок для интерфейса и PDF (задача 7)."""

from __future__ import annotations

from ml.classes import is_defect, ru_name

PRIORITY_RU = {
    "high": "высокий",
    "medium": "средний",
    "low": "низкий",
    "insufficient_data": "недостаточно данных",
}

STATUS_RU = {
    "new": "новая",
    "confirmed": "подтверждена",
    "rejected": "отклонена",
    "reshoot": "переснять",
}

INSPECTION_STATUS_RU = {
    "queued": "в очереди",
    "processing": "обрабатывается",
    "done": "готово",
    "failed": "ошибка",
}

ERROR_RU = {
    "E_VIDEO_INVALID": "Файл не открывается как видео. Проверьте формат (MP4) и целостность файла.",
    "E_DECODE": "Не удалось декодировать кадры видео. Попробуйте перекодировать файл.",
    "E_MODEL": "Модель недоступна: нет файла весов или сбой инференса.",
    "E_TIMEOUT": "Обработка заняла слишком много времени и была остановлена.",
}

LOW_VISIBILITY_NOTE = "Участок снят нечётко, рекомендуется повторная съёмка"
DISCLAIMER = "Решение остаётся за инженером"


def fmt_timecode(sec: float) -> str:
    """73.4 → '01:13'."""
    total = max(0, int(sec))
    return f"{total // 60:02d}:{total % 60:02d}"


def type_ru(finding_type: str) -> str:
    return ru_name(finding_type)


def describe(finding_type: str, priority: str, confidence: float, timecode_sec: float) -> str:
    """«{тип} на отметке {мм:сс}, приоритет {…}, уверенность {…}%»."""
    return (
        f"{type_ru(finding_type)} на отметке {fmt_timecode(timecode_sec)}, "
        f"приоритет {PRIORITY_RU.get(priority, priority)}, "
        f"уверенность {round(confidence * 100)}%"
    )


def recommendation(finding_type: str, priority: str) -> str:
    """Одна фраза-рекомендация инженеру."""
    if finding_type == "low_visibility" or priority == "insufficient_data":
        return LOW_VISIBILITY_NOTE
    if is_defect(finding_type):
        if priority == "high":
            return "Проверить место в первую очередь и при подтверждении запланировать осмотр на опоре"
        if priority == "medium":
            return "Проверить по кадру и включить в план ближайшего осмотра"
        return "Просмотреть кадр; срочных действий не требуется"
    return "Объект обнаружен; проверить положение и состояние по ключевому кадру"
