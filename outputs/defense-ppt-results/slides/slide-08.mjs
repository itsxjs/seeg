import { base, addLogo, imgPanel, stat, bullets, A, C, footer } from "./common.mjs";

export async function slide08(presentation, ctx) {
  const slide = base(presentation, ctx, "研究三｜刺激凸显性：高唤醒片段", "AI 标注的高唤醒窗口中，δ/α 频段方向性差异更突出");
  await addLogo(slide, ctx);
  await imgPanel(slide, ctx, `${A}/study3_arousal_select.png`, 50, 138, 500, 350, "高唤醒窗口与场景切换事件的时间关系");
  await imgPanel(slide, ctx, `${A}/study3_arousal_sgc_current.png`, 582, 138, 560, 350, "按正文统计数值重绘：高唤醒方向性 sGC");
  stat(slide, ctx, "VLM 筛选", "477 个 2 s 窗口 → 19 个高唤醒片段", 68, 528, 410, { color: C.teal, size: 18 });
  stat(slide, ctx, "总体 sGC", "H→A 1.501｜A→H 1.438", 520, 528, 300, { color: C.rust, size: 18 });
  bullets(slide, ctx, [
    "δ：2.406 > 2.187，p = 0.011",
    "α：1.917 > 1.723，p = 0.003",
    "均为 H→A 高于 A→H"
  ], 852, 518, 360, { size: 17, lineH: 34, dot: C.green });
  footer(slide, ctx, 8);
  return slide;
}
