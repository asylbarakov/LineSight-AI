"use client";

import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { cablePaths, lineScanOffset, smoothScanOffset, type ScanOffset } from "@/lib/lineScan";
import styles from "./LineScan.module.css";

function Tower({ x, y, scale }: {x: number; y: number; scale: number}) {
  return <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <g className={styles.rearSteel} transform="translate(11 -3)"><path d="M0 0 -12 100 -22 190 -37 300 -55 390 -78 500 M0 0 12 100 22 190 40 300 60 400 80 516 M-78 500 60 400 -37 300 22 190 -12 100 0 0 M80 516 -55 390 40 300 -22 190 12 100" /></g>
    <path d="M0 0 -12 100 -22 190 -37 300 -55 390 -78 500 M0 0 12 100 22 190 40 300 60 400 80 516 M-12 100H12 M-22 190H22 M-37 300H40 M-55 390 60 400 M-78 500 80 516" />
    <path d="M0 0 12 100 -22 190 40 300 -55 390 80 516 M0 0 -12 100 22 190 -37 300 60 400 -78 500 M-7 60 7 60 M-17 145H17 M-29 240H30 M-46 345 49 350 M-66 445 70 455" />
    <g className={styles.secondarySteel}><path d="M-12 100 8 60 -7 24 M12 100 -8 60 7 24 M-22 190 17 145 -12 100 M22 190 -17 145 12 100 M-37 300 30 240 -22 190 M40 300 -29 240 22 190 M-55 390 49 350 -37 300 M60 400 -46 345 40 300 M-78 500 70 455 -55 390 M80 516 -66 445 60 400" /></g>
    <path d="M-90 100H90L12 67 M-90 100 -12 67 M-110 190H110L22 157 M-110 190 -22 157 M-90 104H90 M-110 194H110 M-90 100 -59 88 -29 100 M90 100 59 88 29 100 M-110 190 -77 178 -44 190 M110 190 77 178 44 190" />
    <g className={styles.insulators}>{[[-90,100],[90,100],[-110,190],[110,190]].map(([a,b]) => <g key={`${a}-${b}`} transform={`translate(${a} ${b})`}><path d="M0 0v26" />{[3,7,11,15,19,23].map(y => <path key={y} d={`M-3 ${y}h6`} />)}</g>)}</g>
    <path d="M-86 501 -70 502 M73 516 89 518" />
  </g>;
}

/** Decorative SVG only. Pointer motion is isolated from the stationary form. */
export function LineScan() {
  const scene = useRef<HTMLElement>(null);
  const frame = useRef<number | null>(null);
  const current = useRef<ScanOffset>({x: 0, y: 0});
  const target = useRef<ScanOffset>({x: 0, y: 0});
  const lastFrame = useRef(0);
  const [enabled, setEnabled] = useState(false);
  const [offset, setOffset] = useState<ScanOffset>({x: 0, y: 0});

  useEffect(() => {
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => {
      setEnabled(fine.matches && !reduce.matches);
      setOffset({x: 0, y: 0});
      current.current = target.current = {x: 0, y: 0};
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
    };
    sync(); fine.addEventListener("change", sync); reduce.addEventListener("change", sync);
    return () => {
      fine.removeEventListener("change", sync); reduce.removeEventListener("change", sync);
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, []);

  function animate(time: number) {
    current.current = smoothScanOffset(current.current, target.current, Math.min(32, time - lastFrame.current));
    lastFrame.current = time;
    const settled = Math.abs(current.current.x - target.current.x) + Math.abs(current.current.y - target.current.y) < .01;
    if (settled) current.current = {...target.current};
    setOffset({...current.current});
    frame.current = settled ? null : requestAnimationFrame(animate);
  }
  function start() {
    if (frame.current === null) { lastFrame.current = performance.now(); frame.current = requestAnimationFrame(animate); }
  }
  function reset() {
    target.current = {x: 0, y: 0};
    if (enabled) start();
  }
  function move(event: PointerEvent<HTMLElement>) {
    if (!enabled || event.pointerType !== "mouse" || !scene.current) return;
    target.current = lineScanOffset(event.clientX, event.clientY, scene.current.getBoundingClientRect(), true);
    start();
  }
  const paths = cablePaths(offset);
  const depth = {"--near-x": `${offset.x}px`, "--near-y": `${offset.y}px`, "--far-x": `${offset.x * .4}px`, "--far-y": `${offset.y * .4}px`, "--terrain-x": `${offset.x * .25}px`, "--terrain-y": `${offset.y * .25}px`} as CSSProperties;
  return <aside ref={scene} className={styles.scene} style={depth} aria-label="Иллюстрация линии электропередачи"
    onPointerMove={move} onPointerLeave={reset}>
    <svg className={styles.schematic} viewBox="0 0 800 900" fill="none" aria-hidden="true" focusable="false">
      <g className={styles.nightSky}>
        <path className={styles.moon} transform="translate(590 140)" d="M12 0a12 12 0 1 0 12 16A10 10 0 0 1 12 0Z" />
        <g className={styles.stars}>
          <circle cx="158" cy="108" r="1" /><circle cx="365" cy="172" r="1.2" />
          <circle cx="465" cy="95" r="1" /><circle cx="690" cy="112" r="1.1" />
          <circle cx="652" cy="262" r=".9" />
        </g>
      </g>
      <g className={styles.daySky}>
        <path d="M493 162c-9 0-10-14 0-16 1-17 27-21 34-5 10-6 24 1 23 12 14-3 21 9 11 9Z" />
        <path className={styles.distantCloud} d="M104 119c-8 0-9-11-1-13 2-13 20-15 26-3 9-4 18 2 17 10 11-2 15 6 7 6Z" />
      </g>
      <g className={styles.terrainLayer}>
        <path className={styles.terrainBack} d="M-2000 630H-40Q30 593 111 616T260 635 430 650 590 625 840 655H2800V5000H-2000Z" />
        <path className={styles.terrainMiddle} d="M-2000 694H-40Q90 651 220 675T440 675Q585 632 682 614T840 650H2800V5000H-2000Z" />
      </g>
      <g className={styles.wires}>{paths.map((d,i) => <path key={i} d={d} />)}</g>
      <g className={styles.wires}><path d={`M-100 335Q20 387 ${125 + offset.x} ${316 + offset.y}`} /><path d={`M-100 405Q10 454 ${105 + offset.x} ${406 + offset.y}`} /></g>
      <g className={`${styles.tower} ${styles.farLayer}`}><Tower x={682} y={440} scale={.35} /></g>
      <g className={`${styles.tower} ${styles.nearLayer}`}>
        <Tower x={215} y={190} scale={1} />
        <g className={styles.focusBrackets}><path d="M259 277v-12h16 M321 265h16v12 M337 336v12h-16 M275 348h-16v-12" /></g>
      </g>
      <g className={styles.terrainLayer}><path className={styles.terrainFront} d="M-2000 661H-40C70 672 130 674 215 690S360 730 460 744 640 782 840 766H2800V5000H-2000Z" /></g>
      {paths.map((d,i) => <path key={i} d={d} pathLength="1000" className={`${styles.pulse} ${styles[`pulse${i}`]}`} />)}
    </svg>
  </aside>;
}
