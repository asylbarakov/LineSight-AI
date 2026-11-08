import type { AssistantMessage, AssistantRequest } from "./types";
export interface Conversation {messages: AssistantMessage[]; draft: string; pendingId: string | null; error: string | null; failedRequest: AssistantRequest | null; request: AssistantRequest | null}
export const emptyConversation: Conversation = {messages: [], draft: "", pendingId: null, error: null, failedRequest: null, request: null};
type Action = {type: "draft"; value: string} | {type: "send"; id: string; request: AssistantRequest; retry: boolean} | {type: "reply"; id: string; text: string} | {type: "failure"; id: string} | {type: "clear"};
export function assistantReducer(state: Conversation, action: Action): Conversation {
  if (action.type === "clear") return emptyConversation;
  if (action.type === "draft") return {...state, draft: action.value};
  if (action.type === "send") return state.pendingId ? state : {...state, draft: action.retry ? state.draft : "", pendingId: action.id, request: action.request, failedRequest: null, error: null,
    messages: action.retry ? state.messages : [...state.messages, {id: `${action.id}-user`, role: "user", text: action.request.prompt, context: action.request.context}]};
  if (action.id !== state.pendingId) return state;
  if (action.type === "failure") return {...state, pendingId: null, error: "Не удалось получить демо-ответ. Повторите попытку.", failedRequest: state.request};
  return {...state, pendingId: null, error: null, request: null, messages: [...state.messages, {id: `${action.id}-reply`, role: "assistant", text: action.text}]};
}
