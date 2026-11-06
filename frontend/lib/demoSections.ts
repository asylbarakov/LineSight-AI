/** Display-only examples. Never infer a section association from a real inspection title. */
export interface DemoSection { id: string; title: string; description: string }
export const DEMO_SECTIONS: DemoSection[] = [
  { id: "demo-north", title: "Участок №001 · Северная ЛЭП", description: "Пример карточки северного направления линии." },
  { id: "demo-east", title: "Участок №002 · Восточная ЛЭП", description: "Пример карточки восточного направления линии." },
  { id: "demo-south", title: "Участок №003 · Южная ЛЭП", description: "Пример карточки южного направления линии." },
];
