/**
 * Recognizer Web — Dibujo de landmarks y HUD en canvas.
 * Funciones puras: reciben contexto y datos, no guardan estado.
 */

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
];

const LABEL_FONT = 'bold 14px monospace';
const GESTURE_FONT = 'bold 16px monospace';
const HUD_FONT = '12px monospace';
const LABEL_COLOR = '#FFD600';
const HUD_COLOR = '#94A3B8';

export function syncCanvasSize(canvas, video) {
  const dpr = window.devicePixelRatio || 1;
  const rect = video.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width * dpr));
  const height = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, width: rect.width, height: rect.height };
}

export function drawScene(ctx, { landmarks, handednesses, gesture, fps, width, height, colors }) {
  ctx.clearRect(0, 0, width, height);

  landmarks.forEach((hand, index) => {
    ctx.strokeStyle = colors.connectionColor;
    ctx.lineWidth = colors.connectionWidth;
    for (const [start, end] of HAND_CONNECTIONS) {
      const a = hand[start];
      const b = hand[end];
      if (!a || !b) continue;
      ctx.beginPath();
      ctx.moveTo(a.x * width, a.y * height);
      ctx.lineTo(b.x * width, b.y * height);
      ctx.stroke();
    }

    ctx.fillStyle = colors.landmarkColor;
    for (const point of hand) {
      ctx.beginPath();
      ctx.arc(point.x * width, point.y * height, colors.landmarkSize, 0, Math.PI * 2);
      ctx.fill();
    }

    const wrist = hand[0];
    const handedness = handednesses[index]?.[0]?.categoryName;
    if (wrist && handedness) {
      ctx.font = LABEL_FONT;
      ctx.fillStyle = colors.handednessColor;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillText(handedness, wrist.x * width + 6, wrist.y * height + 6);
    }
  });

  if (gesture) {
    ctx.font = GESTURE_FONT;
    ctx.fillStyle = LABEL_COLOR;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    const pct = Math.round((gesture.confidence ?? 0) * 100);
    ctx.fillText(`${gesture.name} ${pct}%`, 10, height - 8);
  }

  ctx.font = HUD_FONT;
  ctx.fillStyle = HUD_COLOR;
  ctx.textAlign = 'right';
  ctx.textBaseline = 'top';
  ctx.fillText(`FPS ${fps}`, width - 10, 8);
}
