"use client";

import { useEffect, useId, useReducer, useRef, useState } from "react";
import { assistantReducer, emptyConversation } from "@/lib/assistant/conversation";
import { mockAssistant, suggestedQuestions } from "@/lib/assistant/mockAssistant";
import type { AssistantContext, AssistantRequest, AssistantService } from "@/lib/assistant/types";
import { findingTimecode } from "@/lib/timeline";
import { fmtTimecode } from "@/lib/format";
import { Icon } from "../Icon";
import styles from "./assistant.module.css";

export function AssistantPanel({context, onClose, getCurrentTime, service = mockAssistant}: {
  context: AssistantContext; onClose: () => void; getCurrentTime?: () => number | null; service?: AssistantService;
}) {
  const [state, dispatch] = useReducer(assistantReducer, emptyConversation);
  const [confirmClear, setConfirmClear] = useState(false);
  const [draftMoment, setDraftMoment] = useState<number | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const history = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const clearButton = useRef<HTMLButtonElement>(null);
  const confirmButton = useRef<HTMLButtonElement>(null);
  const sequence = useRef(0);
  const id = useId();
  const busy = state.pendingId !== null;
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { if (stick.current && history.current) history.current.scrollTop = history.current.scrollHeight; }, [state.messages.length, busy, state.error]);
  useEffect(() => { if (confirmClear) confirmButton.current?.focus({preventScroll: true}); }, [confirmClear]);

  async function send(retry = false) {
    if (controller.current || confirmClear) return;
    const prompt = state.draft.trim();
    if (!retry && !prompt) return;
    const request: AssistantRequest | null = retry ? state.failedRequest : {prompt, history: state.messages,
      context: {...context, timecodeSec: draftMoment ?? context.timecodeSec}};
    if (!request) return;
    const active = new AbortController(); controller.current = active;
    const requestId = `${id}-${++sequence.current}`;
    stick.current = true;
    dispatch({type: "send", id: requestId, request, retry});
    if (!retry) setDraftMoment(null);
    try {
      const text = await service.respond(request, active.signal);
      if (!active.signal.aborted) dispatch({type: "reply", id: requestId, text});
    } catch {
      if (!active.signal.aborted) dispatch({type: "failure", id: requestId});
    } finally { if (controller.current === active) controller.current = null; }
  }
  function clear() {
    controller.current?.abort(); controller.current = null;
    dispatch({type: "clear"}); setDraftMoment(null); setConfirmClear(false);
    input.current?.focus({preventScroll: true});
  }
  function askMoment() {
    const seconds = getCurrentTime?.();
    if (seconds == null || !Number.isFinite(seconds)) return;
    setDraftMoment(seconds);
    const question = `Что проверить на ${findingTimecode(seconds)}?`;
    dispatch({type: "draft", value: (state.draft ? `${state.draft}\n${question}` : question).slice(0,4000)});
    input.current?.focus({preventScroll: true});
  }
  return <section className={styles.panel} data-assistant-context={context.page} aria-label="Чат ИИ-помощника" onKeyDown={event => {
    if (event.key === "Escape") { event.stopPropagation(); if (confirmClear) {setConfirmClear(false); clearButton.current?.focus();} else onClose(); }
  }}>
    <header className={styles.header}>
      <div className={styles.heading}><Icon name="sparkles" /><h2 className="text-base font-semibold">ИИ-помощник</h2><span className={styles.demo}>Демо</span></div>
      <div className="flex shrink-0">
        <button ref={clearButton} type="button" className="icon-button" aria-label="Очистить разговор" title="Очистить разговор" disabled={!state.messages.length && !state.draft && !busy} onClick={() => setConfirmClear(true)}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6m4-6v6" /></svg>
        </button>
        <button type="button" className="icon-button" aria-label="Закрыть помощника" title="Закрыть помощника" onClick={onClose}><Icon name="close" /></button>
      </div>
    </header>
    <div className={styles.context}>
      <p className="break-words text-sm font-medium">{context.inspection ? context.inspection.title : context.page === "dashboard" ? "Обзор инспекций" : "Технические метрики"}</p>
      {context.page === "inspection" && <p className="text-xs tabular-nums text-muted">Видео · {context.timecodeSec != null ? fmtTimecode(context.timecodeSec) : "Время недоступно"}</p>}
      <p id={`${id}-demo`} className="mt-1 text-xs text-muted">Демо-ответы. AI и анализ данных не подключены.</p>
      {getCurrentTime && <button type="button" className="quiet-link text-accent" disabled={context.timecodeSec == null || busy} onClick={askMoment}>Спросить об этом моменте</button>}
    </div>
    {confirmClear && <div className={styles.clearPrompt} role="group" aria-label="Подтверждение очистки">
      <p className="text-sm">Очистить историю и черновик?</p><div className="mt-2 flex gap-2">
        <button ref={confirmButton} type="button" className="btn" onClick={clear}>Очистить</button>
        <button type="button" className="btn" onClick={() => {setConfirmClear(false); clearButton.current?.focus();}}>Отмена</button>
      </div>
    </div>}
    <div ref={history} className={styles.history} onScroll={event => {const el=event.currentTarget; stick.current=el.scrollHeight-el.scrollTop-el.clientHeight<64;}}>
      {state.messages.length === 0 && <div className={styles.empty}>
        <p className="text-base font-medium">С чего начать?</p>
        <p className="mt-1 text-sm text-muted">Выберите вопрос или напишите свой. Здесь показан пример будущего помощника.</p>
        {!state.draft && <div className="mt-4 grid gap-2">{suggestedQuestions[context.page].map(question => <button key={question} type="button" className={styles.suggestion}
          onClick={() => {dispatch({type: "draft", value: question}); input.current?.focus({preventScroll: true});}}>{question}</button>)}</div>}
      </div>}
      <ol className={styles.messages} role="log" aria-label="История разговора" aria-live="polite" aria-relevant="additions text">
        {state.messages.map(message => <li key={message.id} className={message.role === "user" ? styles.user : styles.assistant}>
          <p className="mb-1 text-xs font-medium text-muted">{message.role === "user" ? "Вы" : "Помощник · Демо"}{message.role === "user" && message.context?.page === "inspection" && message.context.timecodeSec != null ? ` · ${findingTimecode(message.context.timecodeSec)}` : ""}</p>
          <p className={styles.messageText}>{message.text}</p>
        </li>)}
      </ol>
      {busy && <p role="status" className={styles.typing}><span className="skeleton inline-block h-2 w-2" aria-hidden="true" />Готовим демо-ответ…</p>}
      {state.error && <div className="mt-3 text-sm text-danger" role="alert"><p>{state.error}</p><button type="button" className="btn mt-2" disabled={busy} onClick={() => void send(true)}>Повторить ответ</button></div>}
    </div>
    <form className={styles.composer} onSubmit={event => {event.preventDefault(); void send();}}>
      <label htmlFor={`${id}-message`} className="sr-only">Сообщение помощнику</label>
      <textarea ref={input} id={`${id}-message`} name="assistant-message" autoComplete="off" rows={3} maxLength={4000}
        placeholder="Напишите вопрос…" value={state.draft} onChange={event => dispatch({type: "draft", value: event.target.value})}
        aria-describedby={`${id}-demo ${id}-hint`} onKeyDown={event => {if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {event.preventDefault(); void send();}}} />
      <div className="flex items-center justify-between gap-2"><p id={`${id}-hint`} className="text-xs text-muted">Enter — отправить<br />Shift+Enter — новая строка</p>
        <button type="submit" className="icon-button border border-line text-accent disabled:opacity-40" aria-label="Отправить сообщение" disabled={!state.draft.trim() || busy || confirmClear}><Icon name="send" /></button></div>
    </form>
  </section>;
}
