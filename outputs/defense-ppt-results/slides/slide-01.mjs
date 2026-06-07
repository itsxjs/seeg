import { base, addLogo, t, panel, C, footer } from "./common.mjs";

export async function slide01(presentation, ctx) {
  const slide = base(presentation, ctx, "", "", { noHeader: true, dark: true, accent: C.rust });
  await addLogo(slide, ctx, 1040, 38, 165, 54);
  t(slide, ctx, "本科毕业论文答辩", 66, 54, 300, 26, { size: 20, bold: true, color: "#BBDADC" });
  t(slide, ctx, "短视频观看诱发的\n颅内脑电研究", 64, 150, 760, 140, { size: 54, bold: true, color: "#FFFFFF" });
  t(slide, ctx, "情绪效价 · 主观偏好 · 刺激凸显性", 68, 318, 610, 36, { size: 24, color: "#DDE9E8" });
  panel(slide, ctx, 70, 430, 710, 86, { fill: "#18383D", stroke: "#44656A" });
  t(slide, ctx, "基于 sEEG/LFP、单神经元放电与杏仁核-海马连接性的三项研究", 94, 448, 650, 58, { size: 22, bold: true, color: "#FFFFFF" });
  t(slide, ctx, "徐嘉晟｜浙江大学｜2026", 70, 610, 520, 28, { size: 20, color: "#C7D8D8" });
  footer(slide, ctx, 1);
  return slide;
}
