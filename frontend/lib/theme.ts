export type Theme = "dark" | "light";
export const THEME_STORAGE_KEY = "ls_theme";

export function parseTheme(value: unknown): Theme | null {
  return value === "dark" || value === "light" ? value : null;
}

export function resolveTheme(preference: unknown, _systemDark = false): Theme {
  return parseTheme(preference) ?? "dark";
}

/** Synchronous head script: apply the preference before any page content can paint. */
export const THEME_INIT_SCRIPT = `(function(){
  var saved=null;
  try{saved=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});}catch(e){}
  var theme=saved==='dark'||saved==='light'?saved:'dark';
  document.documentElement.setAttribute('data-theme',theme);
})();`;
