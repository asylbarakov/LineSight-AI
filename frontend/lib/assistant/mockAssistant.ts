import { findingTimecode } from "../timeline";
import type { AssistantContext, AssistantRequest, AssistantService } from "./types";

export const suggestedQuestions: Record<AssistantContext["page"], string[]> = {
  dashboard: ["С чего начать проверку инспекций?", "Чем находка отличается от дефекта?", "Как читать показатели обзора?"],
  inspection: ["Как проверить находку?", "Когда нужна повторная съёмка?", "Как оформить решение инженера?"],
  metrics: ["Как читать время обработки?", "Что показывает средний FPS?", "Как оценивать тренд дефектов?"],
};
function response({prompt, context}: AssistantRequest) {
  const text = prompt.toLocaleLowerCase("ru-RU");
  const label = "Демо-ответ · AI не подключён.\n\n";
  if (context.page === "inspection") {
    const moment = context.timecodeSec != null && Number.isFinite(context.timecodeSec) ? ` Таймкод запроса: ${findingTimecode(context.timecodeSec)}.` : "";
    if (/момент|кадр|видео|провер|наход|съём|решени|дефект/.test(text)) return label + `Я не просматриваю видео и не определяю дефекты.${moment}\n\nДля ручной проверки остановите запись, откройте ключевой кадр и сопоставьте находку с соседними кадрами. Подтвердите или отклоните её во вкладке «Находки». Если детали неразличимы, рассмотрите повторную съёмку. Это общий порядок работы, а не заключение по текущему видео.`;
  } else if (context.page === "metrics" && /врем|обработ|fps|метрик|статист|тренд|дефект/.test(text)) {
    return label + "Время обработки и FPS описывают производительность, а не качество распознавания. Сравнивайте сопоставимые записи по длительности и разрешению; этапы помогают понять, где затрачено время.\n\nЯ не проверяю текущие значения и не рассчитываю тренды. Для выводов по дефектам понадобится подключение к данным и реальному AI-агенту.";
  } else if (context.page === "dashboard" && /инспек|провер|дефект|показател|метрик|наход/.test(text)) {
    return label + "Начните со списка инспекций: выберите обработанную запись и проверьте находки на видео. Находка модели требует решения инженера; недостаточная видимость сама по себе не означает дефект оборудования.\n\nЧисла в обзоре поступают из существующего API. Этот демо-чат не получает и не подтверждает их, не выполняет анализ и не меняет решения.";
  }
  return label + "AI-интеграция пока не подключена. Я могу показать только заранее подготовленные рекомендации по работе с инспекциями и метриками. Ответить на этот вопрос или выполнить действие сейчас не могу.";
}
export const mockAssistant: AssistantService = {
  respond(request, signal) {
    return new Promise((resolve, reject) => {
      if (signal.aborted) { reject(new DOMException("Cancelled", "AbortError")); return; }
      if (!request.prompt.trim() || request.prompt.length > 4000) { reject(new Error("Invalid message")); return; }
      const cancel = () => { clearTimeout(timer); reject(new DOMException("Cancelled", "AbortError")); };
      const timer = setTimeout(() => { signal.removeEventListener("abort", cancel); resolve(response(request)); }, 700);
      signal.addEventListener("abort", cancel, {once: true});
    });
  },
};
