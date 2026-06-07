export const C = {
  bg: "#F5F7F6",
  paper: "#FFFFFF",
  ink: "#11272B",
  muted: "#5E6F72",
  line: "#D6E0DE",
  teal: "#126C75",
  tealSoft: "#DCEDEE",
  rust: "#B65B3D",
  amber: "#D49A3C",
  blue: "#507FA9",
  green: "#6D8A52",
};

export const A = "/Volumes/rmhyw/outputs/defense-ppt-results/assets";

export function base(presentation, ctx, kicker, title, opts = {}) {
  const slide = presentation.slides.add();
  ctx.addShape(slide, { left: 0, top: 0, width: 1280, height: 720, fill: opts.dark ? C.ink : C.bg, line: ctx.line() });
  ctx.addShape(slide, { left: 0, top: 0, width: 1280, height: 8, fill: opts.accent || C.teal, line: ctx.line() });
  if (!opts.noHeader) {
    ctx.addText(slide, { text: kicker, left: 54, top: 24, width: 330, height: 24, fontSize: 15, bold: true, color: opts.dark ? "#BBDADC" : C.teal, typeface: "PingFang SC" });
    ctx.addText(slide, { text: title, left: 54, top: 52, width: 1040, height: 46, fontSize: 30, bold: true, color: opts.dark ? "#FFFFFF" : C.ink, typeface: "PingFang SC" });
    ctx.addShape(slide, { left: 54, top: 112, width: 1172, height: 1.5, fill: opts.dark ? "#345054" : C.line, line: ctx.line() });
  }
  return slide;
}

export async function addLogo(slide, ctx, x = 1115, y = 28, w = 106, h = 34) {
  await ctx.addImage(slide, { path: `${A}/logo_zju.png`, left: x, top: y, width: w, height: h, fit: "contain", alt: "Zhejiang University logo" });
}

export function t(slide, ctx, text, x, y, w, h, opts = {}) {
  return ctx.addText(slide, {
    text,
    left: x,
    top: y,
    width: w,
    height: h,
    fontSize: opts.size || 20,
    bold: !!opts.bold,
    color: opts.color || C.ink,
    align: opts.align || "left",
    valign: opts.valign || "top",
    typeface: opts.face || "PingFang SC",
    fill: opts.fill || "#00000000",
    line: opts.line || ctx.line(),
    insets: opts.insets || { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function panel(slide, ctx, x, y, w, h, opts = {}) {
  return ctx.addShape(slide, {
    left: x,
    top: y,
    width: w,
    height: h,
    fill: opts.fill || C.paper,
    line: opts.line || { style: "solid", fill: opts.stroke || C.line, width: opts.weight || 1.2 },
  });
}

export async function imgPanel(slide, ctx, path, x, y, w, h, caption) {
  panel(slide, ctx, x, y, w, h, { fill: "#FFFFFF", stroke: "#CAD7D5" });
  await ctx.addImage(slide, { path, left: x + 14, top: y + 14, width: w - 28, height: h - 48, fit: "contain", alt: caption || "" });
  if (caption) t(slide, ctx, caption, x + 18, y + h - 28, w - 36, 18, { size: 12.5, color: C.muted });
}

export function stat(slide, ctx, label, value, x, y, w, opts = {}) {
  panel(slide, ctx, x, y, w, 72, { fill: opts.fill || "#FFFFFF", stroke: opts.stroke || C.line });
  t(slide, ctx, label, x + 14, y + 11, w - 28, 18, { size: 13.5, color: C.muted, bold: true });
  t(slide, ctx, value, x + 14, y + 31, w - 28, 38, { size: opts.size || 21, color: opts.color || C.ink, bold: true });
}

export function bullets(slide, ctx, items, x, y, w, opts = {}) {
  const lineH = opts.lineH || 34;
  items.forEach((item, i) => {
    const cy = y + i * lineH + 9;
    ctx.addShape(slide, { left: x, top: cy, width: 8, height: 8, geometry: "ellipse", fill: opts.dot || C.rust, line: ctx.line() });
    t(slide, ctx, item, x + 18, y + i * lineH, w - 18, lineH, { size: opts.size || 18, color: opts.color || C.ink });
  });
}

export function footer(slide, ctx, n) {
  t(slide, ctx, String(n).padStart(2, "0"), 1160, 668, 60, 22, { size: 14, color: C.muted, align: "right" });
}

export function tag(slide, ctx, text, x, y, w, color = C.teal) {
  panel(slide, ctx, x, y, w, 30, { fill: "#FFFFFF", stroke: color, weight: 1.4 });
  t(slide, ctx, text, x + 12, y + 6, w - 24, 18, { size: 13.5, bold: true, color });
}
