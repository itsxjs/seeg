import { base, addLogo, stat, bullets, C, footer } from "./common.mjs";

export async function slide09(presentation, ctx) {
  const slide = base(presentation, ctx, "研究三｜刺激凸显性：单元响应", "场景切换后的放电变化提示海马相对领先，并伴随激活/抑制型响应");
  await addLogo(slide, ctx);
  stat(slide, ctx, "A-H 中位滞后", "-35 ms", 92, 165, 245, { color: C.rust, size: 28 });
  stat(slide, ctx, "IQR", "-82.5–0 ms", 374, 165, 245, { color: C.teal, size: 28 });
  stat(slide, ctx, "海马领先", "16 / 27 runs", 656, 165, 245, { color: C.green, size: 28 });
  stat(slide, ctx, "QC 后数据", "27 runs", 938, 165, 245, { color: C.ink, size: 28 });
  ctx.addShape(slide, { left: 154, top: 360, width: 420, height: 16, fill: C.tealSoft, line: ctx.line() });
  ctx.addShape(slide, { left: 154, top: 360, width: 270, height: 16, fill: C.teal, line: ctx.line() });
  ctx.addShape(slide, { left: 706, top: 360, width: 420, height: 16, fill: "#F2E2D8", line: ctx.line() });
  ctx.addShape(slide, { left: 706, top: 360, width: 238, height: 16, fill: C.rust, line: ctx.line() });
  stat(slide, ctx, "抑制型响应", "413 个 cluster｜Amy 270 / Hip 143", 132, 420, 455, { color: C.teal, size: 20 });
  stat(slide, ctx, "激活型响应", "290 个 cluster｜Amy 182 / Hip 108", 692, 420, 455, { color: C.rust, size: 20 });
  bullets(slide, ctx, ["放电结果补充连接性分析：自然事件后，海马信息可能更早进入 A-H 系统", "激活与抑制并存，说明凸显性加工不是单向增强"], 164, 550, 900, { size: 19, lineH: 36, dot: C.green });
  footer(slide, ctx, 9);
  return slide;
}
