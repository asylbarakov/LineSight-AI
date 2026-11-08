export interface AssistantContext {
  page: "dashboard" | "inspection" | "metrics";
  inspection?: {id: string; title: string};
  timecodeSec?: number | null;
}
export interface AssistantMessage {id: string; role: "user" | "assistant"; text: string; context?: AssistantContext}
export interface AssistantRequest {prompt: string; context: AssistantContext; history: readonly AssistantMessage[]}
/** Replace this boundary with a real client later; the UI owns no transport logic. */
export interface AssistantService {respond(request: AssistantRequest, signal: AbortSignal): Promise<string>}
