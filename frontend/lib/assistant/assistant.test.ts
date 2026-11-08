import { afterEach, expect, it, vi } from "vitest";
import { mockAssistant } from "./mockAssistant";
import { assistantReducer, emptyConversation } from "./conversation";
import type { AssistantRequest } from "./types";
afterEach(() => vi.useRealTimers());
const request: AssistantRequest = {prompt: "Как проверить этот момент?", context: {page: "inspection", inspection: {id: "one", title: "Облёт"}, timecodeSec: 26.64}, history: []};
it("replies asynchronously without claiming to inspect video or invent results", async () => {
  vi.useFakeTimers(); let finished = false;
  const result = mockAssistant.respond(request, new AbortController().signal).then(text => {finished = true; return text;});
  expect(finished).toBe(false); await vi.advanceTimersByTimeAsync(800);
  const text = await result;
  expect(text).toContain("Демо"); expect(text).toContain("не просматриваю видео"); expect(text).toContain("00:26.64");
});
it("explains unsupported questions and never returns fabricated metrics", async () => {
  vi.useFakeTimers();
  const reply = mockAssistant.respond({...request, prompt: "Погода завтра", context: {page: "metrics"}}, new AbortController().signal);
  await vi.runAllTimersAsync(); expect(await reply).toContain("не подключён");
});
it.each([
  ["dashboard", "Как читать показатели?", "не получает и не подтверждает"],
  ["metrics", "Как читать время обработки?", "не проверяю текущие значения"],
] as const)("provides safe contextual help on %s", async (page, prompt, expected) => {
  vi.useFakeTimers();
  const reply = mockAssistant.respond({...request, context: {page}, prompt}, new AbortController().signal);
  await vi.runAllTimersAsync(); expect(await reply).toContain(expected);
});
it("cancels a pending local reply without leaving its timer alive", async () => {
  vi.useFakeTimers(); const controller = new AbortController();
  const result = mockAssistant.respond(request, controller.signal).catch(error => error.name);
  controller.abort(); expect(await result).toBe("AbortError"); expect(vi.getTimerCount()).toBe(0);
});
it("keeps draft state and ignores a reply after the conversation is cleared", () => {
  const draft = assistantReducer(emptyConversation, {type: "draft", value: "Не терять текст"});
  expect(draft.draft).toBe("Не терять текст");
  const busy = assistantReducer(draft, {type: "send", id: "r1", request, retry: false});
  expect(busy.messages).toHaveLength(1);
  const cleared = assistantReducer(busy, {type: "clear"});
  expect(assistantReducer(cleared, {type: "reply", id: "r1", text: "late"})).toEqual(emptyConversation);
});
it("retries a failed request without duplicating the user message", () => {
  const busy = assistantReducer(emptyConversation, {type: "send", id: "r1", request, retry: false});
  const failed = assistantReducer(busy, {type: "failure", id: "r1"});
  expect(failed.error).toBeTruthy(); expect(failed.failedRequest).toEqual(request);
  const retry = assistantReducer(failed, {type: "send", id: "r2", request, retry: true});
  const done = assistantReducer(retry, {type: "reply", id: "r2", text: "Демо-ответ"});
  expect(done.messages.map(m => m.role)).toEqual(["user", "assistant"]); expect(done.pendingId).toBeNull();
});
