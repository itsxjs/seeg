import { base, addLogo, imgPanel, stat, bullets, A, C, footer } from "./common.mjs";

export async function slide06(presentation, ctx) {
  const slide = base(presentation, ctx, "研究二｜单神经元放电", "偏好相关放电呈现相反响应类型，并集中在早期与中期时间窗");
  await addLogo(slide, ctx);
  await imgPanel(slide, ctx, `${A}/study2_spike_clusters.png`, 58, 143, 718, 442, "核心结果图：喜欢/不喜欢条件下的 antagonistic clusters");
  stat(slide, ctx, "可分析单元", "45 units", 822, 154, 300, { color: C.rust });
  stat(slide, ctx, "聚类规模", "n = 22 / 23", 822, 242, 300, { color: C.teal });
  stat(slide, ctx, "显著时间窗", "0.20–0.70 s；1.25–1.65 s", 822, 330, 300, { color: C.rust, size: 18 });
  bullets(slide, ctx, ["喜欢条件放电较低，不喜欢条件较高", "效应主要集中于海马单元", "与 LFP 结果共同支持偏好调制"], 822, 436, 342, { size: 18, lineH: 34, dot: C.teal });
  footer(slide, ctx, 6);
  return slide;
}
