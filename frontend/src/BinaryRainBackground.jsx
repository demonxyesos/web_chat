import { useEffect, useRef } from "react";

const BG = "#050505";
const FONT_SIZE = 14;
const COLUMN_STEP = 15;

function buildColumns(width, height) {
  const n = Math.max(1, Math.ceil(width / COLUMN_STEP));
  const cols = [];
  for (let i = 0; i < n; i++) {
    const trail = 12 + Math.floor(Math.random() * 28);
    cols.push({
      x: i * COLUMN_STEP + 1,
      y: Math.random() * (height + trail * FONT_SIZE) - trail * FONT_SIZE,
      speed: 0.25 + Math.random() * 0.55,
      trail,
      phase: Math.floor(Math.random() * 1000),
    });
  }
  return cols;
}

function drawStaticGrid(ctx, width, height) {
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, width, height);
  ctx.font = `${FONT_SIZE}px ui-monospace, "Cascadia Code", Consolas, monospace`;
  const stepY = FONT_SIZE + 2;
  for (let x = 0; x < width; x += COLUMN_STEP) {
    for (let y = FONT_SIZE; y < height; y += stepY) {
      const bit = ((x / COLUMN_STEP + y / stepY) & 1) === 0 ? "0" : "1";
      ctx.fillStyle = "rgba(255,255,255,0.035)";
      ctx.fillText(bit, x + 1, y);
    }
  }
}

export function BinaryRainBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reducedMotion = motionQuery.matches;

    let rafId = 0;
    let visible = document.visibilityState !== "hidden";
    let width = 0;
    let height = 0;
    let dpr = 1;
    let columns = [];

    function syncSize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      columns = buildColumns(width, height);
    }

    function onMotionChange() {
      reducedMotion = motionQuery.matches;
      cancelAnimationFrame(rafId);
      rafId = 0;
      syncSize();
      if (reducedMotion) {
        drawStaticGrid(ctx, width, height);
      } else if (visible) {
        loop();
      }
    }

    function onVisibility() {
      visible = document.visibilityState !== "hidden";
      if (reducedMotion) return;
      if (!visible) {
        cancelAnimationFrame(rafId);
        rafId = 0;
      } else if (!rafId) {
        loop();
      }
    }

    function charAt(colIndex, rowIndex, frame) {
      const v = (colIndex * 17 + rowIndex * 3 + frame + colIndex * rowIndex) & 1;
      return v === 0 ? "0" : "1";
    }

    function loop() {
      if (!visible || reducedMotion) return;

      ctx.fillStyle = "rgba(5, 5, 5, 0.18)";
      ctx.fillRect(0, 0, width, height);

      ctx.font = `${FONT_SIZE}px ui-monospace, "Cascadia Code", Consolas, monospace`;
      ctx.textBaseline = "top";

      const frame = Math.floor(performance.now() / 120);

      for (let ci = 0; ci < columns.length; ci++) {
        const c = columns[ci];
        c.y += c.speed;
        const maxY = c.trail * FONT_SIZE;
        if (c.y > height + maxY) {
          c.y = -maxY - Math.random() * height * 0.4;
          c.speed = 0.25 + Math.random() * 0.55;
          c.trail = 12 + Math.floor(Math.random() * 28);
        }

        for (let j = 0; j < c.trail; j++) {
          const cy = c.y - j * FONT_SIZE;
          if (cy < -FONT_SIZE || cy > height + FONT_SIZE) continue;
          const alpha = 0.018 + (1 - j / c.trail) * 0.045;
          ctx.fillStyle = `rgba(255,255,255,${alpha})`;
          const ch = charAt(ci, j + c.phase, frame);
          ctx.fillText(ch, c.x, cy);
        }
      }

      rafId = requestAnimationFrame(loop);
    }

    syncSize();

    if (reducedMotion) {
      drawStaticGrid(ctx, width, height);
    } else {
      ctx.fillStyle = BG;
      ctx.fillRect(0, 0, width, height);
      rafId = requestAnimationFrame(loop);
    }

    const onResize = () => {
      cancelAnimationFrame(rafId);
      rafId = 0;
      syncSize();
      if (reducedMotion) {
        drawStaticGrid(ctx, width, height);
      } else {
        ctx.fillStyle = BG;
        ctx.fillRect(0, 0, width, height);
        if (visible) rafId = requestAnimationFrame(loop);
      }
    };

    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVisibility);
    motionQuery.addEventListener("change", onMotionChange);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      motionQuery.removeEventListener("change", onMotionChange);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="binary-rain-canvas"
      aria-hidden="true"
    />
  );
}
