import type { Config } from "tailwindcss";

// Цвета берутся из CSS-переменных (app/globals.css): тема меняется в одном месте.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontSize: {
        xs: ["var(--text-meta)", {lineHeight: "var(--leading-meta)"}],
        sm: ["var(--text-control)", {lineHeight: "var(--leading-control)"}],
        base: ["var(--text-body)", {lineHeight: "var(--leading-body)"}],
        lg: ["var(--text-section)", {lineHeight: "var(--leading-section)"}],
        xl: ["var(--text-section-large)", {lineHeight: "var(--leading-section)"}],
        "2xl": ["var(--text-page)", {lineHeight: "var(--leading-page)"}],
        label: ["var(--text-label)", {lineHeight: "var(--leading-label)"}],
        readout: ["var(--text-readout)", {lineHeight: "var(--leading-readout)"}],
      },
      colors: {
        bg: "rgb(var(--bg-rgb) / <alpha-value>)",
        surface: "rgb(var(--surface-rgb) / <alpha-value>)",
        surface2: "rgb(var(--surface-2-rgb) / <alpha-value>)",
        field: "rgb(var(--field-rgb) / <alpha-value>)",
        line: "rgb(var(--line-rgb) / <alpha-value>)",
        control: "rgb(var(--control-rgb) / <alpha-value>)",
        fg: "rgb(var(--fg-rgb) / <alpha-value>)",
        muted: "rgb(var(--muted-rgb) / <alpha-value>)",
        accent: "rgb(var(--accent-rgb) / <alpha-value>)",
        "accent-fg": "rgb(var(--accent-fg-rgb) / <alpha-value>)",
        "accent-soft": "rgb(var(--accent-soft-rgb) / <alpha-value>)",
        ok: "rgb(var(--ok-rgb) / <alpha-value>)",
        "ok-soft": "rgb(var(--ok-soft-rgb) / <alpha-value>)",
        warn: "rgb(var(--warn-rgb) / <alpha-value>)",
        "warn-soft": "rgb(var(--warn-soft-rgb) / <alpha-value>)",
        danger: "rgb(var(--danger-rgb) / <alpha-value>)",
        "danger-soft": "rgb(var(--danger-soft-rgb) / <alpha-value>)",
        info: "rgb(var(--muted-rgb) / <alpha-value>)",
        media: "rgb(var(--media-rgb) / <alpha-value>)",
        overlay: "rgb(var(--overlay-rgb) / <alpha-value>)",
        sidebar: "rgb(var(--sidebar-rgb) / <alpha-value>)",
        "sidebar-fg": "rgb(var(--sidebar-fg-rgb) / <alpha-value>)",
        "sidebar-muted": "rgb(var(--sidebar-muted-rgb) / <alpha-value>)",
        "sidebar-active": "rgb(var(--sidebar-active-rgb) / <alpha-value>)",
        "sidebar-line": "rgb(var(--sidebar-line-rgb) / <alpha-value>)",
        chart: "rgb(var(--chart-rgb) / <alpha-value>)",
      },
      boxShadow: { sm: "var(--shadow-sm)", lg: "var(--shadow-lg)", xl: "var(--shadow-xl)" },
      fontFamily: { sans: ["LineSight Proxima Nova", "Onest", "Segoe UI", "Arial", "sans-serif"] },
    },
  },
  plugins: [],
};

export default config;
