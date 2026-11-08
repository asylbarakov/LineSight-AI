"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { AssistantPanel } from "./AssistantPanel";
import { Icon } from "../Icon";
import type { AssistantContext } from "@/lib/assistant/types";
import styles from "./assistant.module.css";

/** Render the trigger in each page's toolbar; one reusable in-flow drawer/rail. */
export function AssistantDock({context, children}: {context: AssistantContext; children: (trigger: ReactNode) => ReactNode}) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const pane = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!open) return;
    const element = pane.current;
    const rect = element?.getBoundingClientRect();
    if (element && rect && (rect.top < 76 || rect.bottom > window.innerHeight)) element.scrollIntoView({block: "start"});
    element?.querySelector<HTMLTextAreaElement>("textarea")?.focus({preventScroll: true});
  }, [open]);
  const paneId = `assistant-${context.page}`;
  return <div className={styles.dock}><div className={styles.dockGrid} data-assistant-open={open}>
    <div className={styles.content}>{children(<button ref={trigger} type="button" className="btn" aria-expanded={open} aria-controls={paneId} onClick={() => setOpen(value => !value)}><Icon name="sparkles" />ИИ-помощник</button>)}</div>
    <aside ref={pane} id={paneId} hidden={!open} className={styles.dockPane} aria-label="Панель помощника">
      <AssistantPanel context={context} onClose={() => {setOpen(false); trigger.current?.focus();}} />
    </aside>
  </div></div>;
}
