import { base, addLogo, imgPanel, t, stat, bullets, A, C, footer } from "./common.mjs";

export async function slide04(presentation, ctx) {
  const slide = base(presentation, ctx, "研究一｜情绪效价", "杏仁核在早期中低频段区分正性与负性情绪");
  await addLogo(slide, ctx);
  await imgPanel(slide, ctx, `${A}/study1_valence_fstats.png`, 62, 145, 708, 456, "核心结果图：情绪效价的时间-频率 F 统计量与显著簇");
  stat(slide, ctx, "刺激", "IAPS 120 张", 820, 154, 310, { color: C.rust });
  stat(slide, ctx, "分析窗", "0–2 s｜2–100 Hz", 820, 242, 310, { color: C.teal });
  stat(slide, ctx, "显著簇 1", "450–800 ms｜5.8–20.2 Hz", 820, 330, 310, { color: C.rust, size: 19 });
  stat(slide, ctx, "显著簇 2", "1650–1950 ms｜2.0–4.1 Hz", 820, 418, 310, { color: C.rust, size: 19 });
  bullets(slide, ctx, ["cluster 校正后杏仁核效应稳定", "海马未出现稳定显著簇", "为真实短视频偏好分析提供脑区假设"], 820, 526, 355, { size: 18, lineH: 32, dot: C.teal });
  footer(slide, ctx, 4);
  return slide;
}
