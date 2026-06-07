import { base, addLogo, imgPanel, stat, bullets, A, C, footer } from "./common.mjs";

export async function slide05(presentation, ctx) {
  const slide = base(presentation, ctx, "研究二｜主观偏好 LFP", "喜欢/不喜欢短视频在杏仁核与海马均诱发时间-频率差异");
  await addLogo(slide, ctx);
  await imgPanel(slide, ctx, `${A}/study2_amy_fstats.png`, 54, 140, 515, 360, "杏仁核：like / dislike LFP 差异");
  await imgPanel(slide, ctx, `${A}/study2_hip_fstats.png`, 595, 140, 515, 360, "海马：like / dislike LFP 差异");
  stat(slide, ctx, "杏仁核显著窗", "450–1100 ms｜4.9–24.2 Hz", 78, 535, 345, { color: C.rust, size: 19 });
  stat(slide, ctx, "海马显著窗", "700–1200 ms｜2.0–28.9 Hz", 468, 535, 345, { color: C.teal, size: 19 });
  bullets(slide, ctx, ["偏好效应不是单一脑区现象", "海马效应更晚，提示情境加工参与"], 850, 535, 350, { size: 18, lineH: 35, dot: C.green });
  footer(slide, ctx, 5);
  return slide;
}
