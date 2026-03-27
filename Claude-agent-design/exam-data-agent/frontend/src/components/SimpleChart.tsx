import { useRef, useEffect } from "react";

const PRIMARY = "#00B4D8";
const ACCENT = "#66FFD1";
const GRID_COLOR = "#F1F5F9";
const LABEL_COLOR = "#6E7E85";

interface Props {
  type: "line" | "bar";
  labels: string[];
  data: number[];
}

function drawLineChart(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  labels: string[],
  data: number[],
) {
  const padL = 50, padR = 20, padT = 20, padB = 36;
  const cw = w - padL - padR;
  const ch = h - padT - padB;
  const max = Math.max(...data) * 1.15 || 1;
  const min = 0;
  const range = max - min;

  ctx.clearRect(0, 0, w, h);

  // Grid lines
  ctx.strokeStyle = GRID_COLOR;
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (ch / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
    // Y-axis labels
    ctx.fillStyle = LABEL_COLOR;
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    const val = max - (range / 4) * i;
    ctx.fillText(val >= 1000 ? `${(val / 1000).toFixed(1)}k` : Math.round(val).toString(), padL - 8, y + 4);
  }

  if (data.length < 2) return;

  const stepX = cw / (data.length - 1);
  const points = data.map((v, i) => ({
    x: padL + stepX * i,
    y: padT + ch - ((v - min) / range) * ch,
  }));

  // Area fill
  const grad = ctx.createLinearGradient(0, padT, 0, h - padB);
  grad.addColorStop(0, "rgba(0, 180, 216, 0.18)");
  grad.addColorStop(1, "rgba(0, 180, 216, 0.01)");
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(points[0].x, h - padB);
  points.forEach((p) => ctx.lineTo(p.x, p.y));
  ctx.lineTo(points[points.length - 1].x, h - padB);
  ctx.closePath();
  ctx.fill();

  // Line
  ctx.strokeStyle = PRIMARY;
  ctx.lineWidth = 2.5;
  ctx.lineJoin = "round";
  ctx.beginPath();
  points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.stroke();

  // Dots
  points.forEach((p) => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.strokeStyle = PRIMARY;
    ctx.lineWidth = 2;
    ctx.stroke();
  });

  // X-axis labels
  ctx.fillStyle = LABEL_COLOR;
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  labels.forEach((label, i) => {
    const x = padL + stepX * i;
    // Skip some labels if too dense
    if (labels.length > 10 && i % Math.ceil(labels.length / 8) !== 0 && i !== labels.length - 1) return;
    ctx.fillText(label.length > 6 ? label.slice(-5) : label, x, h - padB + 18);
  });
}

function drawBarChart(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  labels: string[],
  data: number[],
) {
  const padL = 50, padR = 20, padT = 20, padB = 36;
  const cw = w - padL - padR;
  const ch = h - padT - padB;
  const max = Math.max(...data) * 1.15 || 1;

  ctx.clearRect(0, 0, w, h);

  // Grid lines
  ctx.strokeStyle = GRID_COLOR;
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (ch / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
    ctx.fillStyle = LABEL_COLOR;
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    const val = max - (max / 4) * i;
    ctx.fillText(val >= 1000 ? `${(val / 1000).toFixed(1)}k` : Math.round(val).toString(), padL - 8, y + 4);
  }

  const barGap = cw * 0.15 / data.length;
  const barW = (cw - barGap * (data.length + 1)) / data.length;

  const grad = ctx.createLinearGradient(0, padT, 0, h - padB);
  grad.addColorStop(0, PRIMARY);
  grad.addColorStop(1, ACCENT);

  data.forEach((v, i) => {
    const x = padL + barGap + (barW + barGap) * i;
    const barH = (v / max) * ch;
    const y = padT + ch - barH;

    // Bar with rounded top
    ctx.fillStyle = grad;
    const r = Math.min(4, barW / 2);
    ctx.beginPath();
    ctx.moveTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.arcTo(x + barW, y, x + barW, y + r, r);
    ctx.lineTo(x + barW, padT + ch);
    ctx.lineTo(x, padT + ch);
    ctx.closePath();
    ctx.fill();
  });

  // X-axis labels
  ctx.fillStyle = LABEL_COLOR;
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  labels.forEach((label, i) => {
    const x = padL + barGap + (barW + barGap) * i + barW / 2;
    if (labels.length > 10 && i % Math.ceil(labels.length / 8) !== 0 && i !== labels.length - 1) return;
    ctx.fillText(label.length > 6 ? label.slice(-5) : label, x, h - padB + 18);
  });
}

export default function SimpleChart({ type, labels, data }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || data.length === 0) return;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = 200;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    if (type === "bar") {
      drawBarChart(ctx, w, h, labels, data);
    } else {
      drawLineChart(ctx, w, h, labels, data);
    }
  }, [type, labels, data]);

  if (data.length === 0) return null;

  return (
    <div ref={containerRef} className="chart-container">
      <canvas ref={canvasRef} />
    </div>
  );
}
