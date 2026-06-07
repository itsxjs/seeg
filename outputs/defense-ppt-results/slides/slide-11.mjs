import { base, addLogo, t, panel, bullets, C, footer } from "./common.mjs";

export async function slide11(presentation, ctx) {
  const slide = base(presentation, ctx, "结论", "本研究从颅内脑电层面刻画了短视频相关信息加工的关键环节");
  await addLogo(slide, ctx);
  panel(slide, ctx, 92, 158, 500, 330, { fill: "#FFFFFF", stroke: C.teal });
  t(slide, ctx, "主要贡献", 126, 196, 360, 42, { size: 30, bold: true, color: C.teal });
  bullets(slide, ctx, [
    "串联标准情绪刺激、真实短视频与自然电影",
    "同时使用 LFP、放电和连接性指标",
    "将刺激凸显性作为独立探索"
  ], 128, 260, 390, { size: 19, lineH: 43, dot: C.rust });
  panel(slide, ctx, 690, 158, 420, 330, { fill: "#FFFFFF", stroke: C.rust });
  t(slide, ctx, "局限与展望", 724, 196, 320, 42, { size: 30, bold: true, color: C.rust });
  bullets(slide, ctx, [
    "样本量有限，部分分析仍偏探索",
    "高唤醒标注仍需人工与行为检验",
    "后续可结合多模态特征与更大样本"
  ], 724, 260, 330, { size: 19, lineH: 43, dot: C.teal });
  t(slide, ctx, "谢谢各位老师，请批评指正", 326, 575, 630, 42, { size: 34, bold: true, color: C.ink, align: "center" });
  footer(slide, ctx, 11);
  return slide;
}
