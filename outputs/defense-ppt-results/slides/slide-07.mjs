import { base, addLogo, imgPanel, stat, bullets, A, C, footer } from "./common.mjs";

export async function slide07(presentation, ctx) {
  const slide = base(presentation, ctx, "研究三｜刺激凸显性：场景切换", "自然电影场景切换后，杏仁核-海马连接呈低频增强与方向性差异");
  await addLogo(slide, ctx);
  await imgPanel(slide, ctx, `${A}/study3_coherence.png`, 52, 138, 530, 360, "Coherence：场景切换锁定的 A-H 同步");
  await imgPanel(slide, ctx, `${A}/study3_sgc.png`, 610, 138, 530, 360, "sGC：H→A 与 A→H 方向性比较");
  stat(slide, ctx, "Coherence", "约 0.34–0.49｜低频更强", 76, 536, 330, { color: C.teal, size: 18 });
  stat(slide, ctx, "sGC 均值", "H→A 0.584｜A→H 0.535", 456, 536, 330, { color: C.rust, size: 18 });
  bullets(slide, ctx, [
    "FDR 显著频段：9.6–13.2 Hz",
    "另见 17.6–20.0、43.6–44.8 Hz",
    "H→A 信息驱动更强"
  ], 824, 520, 360, { size: 16.5, lineH: 32, dot: C.green });
  footer(slide, ctx, 7);
  return slide;
}
