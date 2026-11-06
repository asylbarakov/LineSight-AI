"use client";

import { useState } from "react";
import styles from "./LineScan.module.css";

// A decorative schematic only. No inspection data, model results or API state.
const SCAN_PATH = "M-20 142 Q28 180 81.6 153.2 Q184 257 303.2 118.9 Q441 243 562.4 153.3 Q617 192 660 176";

function Tower({ x, y, scale = 1 }: { x: number; y: number; scale?: number }) {
  return <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <path d="M0 0 -13 46 -17 94 -37 250 M0 0 13 46 17 94 37 250 M-37 250H37 M-13 46H13 M-17 94H17 M-27 170H27 M-9 22H9 M-28 38H28 M-42 60H42 M-56 88H56 M-28 38 -12 28 M28 38 12 28 M-42 60 -14 48 M42 60 14 48 M-56 88 -17 72 M56 88 17 72 M-17 94 27 170 -37 250 M17 94 -27 170 37 250 M-13 46 17 94 M13 46 -17 94" />
    <g className={styles.insulators}><path d="M-28 38v11 M28 38v11 M-42 60v12 M42 60v12 M-56 88v13 M56 88v13" /></g>
    <path d="M-47 253H47" />
  </g>;
}

export function LineScan() {
  const [paused, setPaused] = useState(false);
  return <section className={styles.scene} data-paused={paused} aria-labelledby="line-scan-title">
    <div className={styles.sceneHeader}>
      <div><p className={styles.sceneLabel}>Сканирование линии</p><p className={styles.sceneMeta}>Иллюстрация видеоинспекции</p></div>
      <button type="button" className={styles.motionControl} aria-pressed={paused}
        aria-label={paused ? "Включить анимацию" : "Приостановить анимацию"} onClick={() => setPaused(value => !value)}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          {paused ? <path d="m9 5 10 7-10 7Z" /> : <path d="M9 5v14M15 5v14" />}
        </svg>
      </button>
    </div>
    <div className={styles.drawing}>
      <svg className={styles.schematic} viewBox="0 0 640 440" fill="none" aria-hidden="true" focusable="false">
        <g className={styles.ground}><path d="M24 374H616 M24 369v10 M616 369v10 M276 369v10" /><path d="M51 392H117 M237 392H315 M519 392H581" /></g>
        <g className={styles.wires}>
          <path d="M-20 161Q27 196 70.4 171.6Q175 283 287.8 144.2Q426 269 552.6 169.4Q608 209 660 192" />
          <path d="M-20 184Q23 222 59.2 194.8Q160 313 272.4 176.1Q412 299 542.8 189.7Q602 232 660 216" />
          <path d="M126.4 153.2Q237 254 364.8 118.9Q487 243 601.6 153.3 M137.6 171.6Q250 281 380.2 144.2Q499 269 611.4 169.4 M148.8 194.8Q267 311 395.6 176.1Q516 299 621.2 189.7" />
          <path d={SCAN_PATH} />
        </g>
        <g className={styles.towers}>
          <Tower x={104} y={114} scale={0.8} />
          <Tower x={334} y={65} scale={1.1} />
          <g opacity="0.65"><Tower x={582} y={119} scale={0.7} /></g>
        </g>
        <path className={styles.scanHalo} d={SCAN_PATH} pathLength="1000" />
        <path className={styles.scanPulse} d={SCAN_PATH} pathLength="1000" />
        <g className={`${styles.detection} ${styles.firstDetection}`} transform="translate(188.2 196.5)">
          <path d="M-10-4v-6h6 M4-10h6v6 M10 4v6H4 M-4 10h-6V4" /><circle r="2" />
        </g>
        <g className={`${styles.detection} ${styles.secondDetection}`} transform="translate(436.9 189.6)">
          <path d="M-10-4v-6h6 M4-10h6v6 M10 4v6H4 M-4 10h-6V4" /><circle r="2" />
        </g>
      </svg>
    </div>
    <div className={styles.sceneCaption}>
      <h2 id="line-scan-title">Видеоданные. Находки. Решения.</h2>
      <p>От просмотра линии до отчёта инженера.</p>
    </div>
  </section>;
}
