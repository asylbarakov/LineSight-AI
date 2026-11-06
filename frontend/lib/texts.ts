import type { ErrorCode, FindingStatus, InspectionStatus, Priority } from "./types";

export const STATUS_RU: Record<InspectionStatus, string> = {
  queued: "В очереди",
  processing: "Обрабатывается",
  done: "Обработано",
  failed: "Ошибка",
};

export const PRIORITY_RU: Record<Priority, string> = {
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
  insufficient_data: "Недостаточно данных",
};

export const FINDING_STATUS_RU: Record<FindingStatus, string> = {
  new: "Новая",
  confirmed: "Подтверждена",
  rejected: "Отклонена",
  reshoot: "Переснять",
};

export const ERROR_RU: Record<ErrorCode, string> = {
  E_VIDEO_INVALID: "Файл не открывается как видео. Проверьте формат (MP4) и целостность файла.",
  E_DECODE: "Не удалось декодировать кадры видео. Попробуйте перекодировать файл.",
  E_MODEL: "Модель недоступна: нет файла весов или сбой инференса.",
  E_TIMEOUT: "Обработка заняла слишком много времени и была остановлена.",
};

const TYPE_RU: Record<string, string> = {
  low_visibility: "Недостаточная видимость",
  insulator: "Изолятор",
  tower: "Опора",
  line: "Линия",
  breaker: "Выключатель",
  arrester: "Разрядник",
  bushing: "Ввод",
  capacitor: "Конденсатор",
  // классы обученной модели (датасет sxiong, подмножество «transmission line object detection»)
  blq_jyjc: "Разрядник: пробой изоляции",
  blq_lh: "Разрядник: старение",
  blq_ps: "Разрядник: повреждение",
  blq_yxdk: "Разрядник: обрыв заземляющего вывода",
  czjyz_lw: "Опорный изолятор: трещина",
  czjyz_ps: "Опорный изолятор: повреждение",
  czjyz_sl: "Опорный изолятор: следы перекрытия",
  dx_dg: "Провод: обрыв жил",
  dx_jypps: "Провод: повреждение изоляции",
  dx_sg: "Провод: ослабление скрутки жил",
  jj_jxps: "Арматура: повреждение соединения вывода",
  nw: "Гнездо птицы на линии",
  yw: "Посторонний предмет на линии",
  yxdk: "Обрыв заземляющего вывода",
};

/** Название типа находки по-русски; для неизвестных классов — исходное имя без подчёркиваний. */
export function typeRu(type: string): string {
  const key = type.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  return TYPE_RU[key] ?? type.replace(/_/g, " ");
}

export function errorText(code: string | null | undefined, fallback?: string | null): string {
  if (code && code in ERROR_RU) return ERROR_RU[code as ErrorCode];
  return fallback || "Неизвестная ошибка обработки.";
}
