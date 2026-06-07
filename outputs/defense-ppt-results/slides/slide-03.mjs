import { base, addLogo, t, panel, stat, C, footer } from "./common.mjs";

export async function slide03(presentation, ctx) {
  const slide = base(presentation, ctx, "数据与方法", "同一脑区系统内，结合 LFP、放电与连接性指标");
  await addLogo(slide, ctx);
  const rows = [
    ["研究一", "IAPS 图片 120 张", "LFP 时间-频率", "LME + cluster-based permutation"],
    ["研究二", "短视频 66 段", "LFP + IFR/聚类", "喜欢/不喜欢评分分组"],
    ["研究三", "Keles 公开自然电影", "Coherence + sGC + spike", "场景切换与高唤醒事件锁定"],
  ];
  const x = 82, y = 180, w = 1116;
  panel(slide, ctx, x, y, w, 282, { fill: "#FFFFFF", stroke: C.line });
  ["研究", "刺激/数据", "核心指标", "统计策略"].forEach((h, i) => t(slide, ctx, h, x + [26, 206, 500, 770][i], y + 24, [80, 180, 170, 210][i], 24, { size: 17, bold: true, color: C.teal }));
  rows.forEach((r, idx) => {
    const yy = y + 72 + idx * 66;
    ctx.addShape(slide, { left: x + 18, top: yy - 10, width: w - 36, height: 1, fill: C.line, line: ctx.line() });
    r.forEach((cell, i) => t(slide, ctx, cell, x + [26, 206, 500, 770][i], yy, [140, 245, 245, 315][i], 40, { size: 18, bold: i === 0, color: i === 0 ? C.rust : C.ink }));
  });
  stat(slide, ctx, "研究三 QC", "27 个 run 纳入", 98, 506, 250, { color: C.teal });
  stat(slide, ctx, "单元层面", "45 个可分析 units", 386, 506, 250, { color: C.rust });
  stat(slide, ctx, "事件锁定", "场景切换 / 高唤醒", 674, 506, 250, { color: C.green });
  stat(slide, ctx, "答辩取舍", "只展示核心结果", 962, 506, 250, { color: C.ink });
  footer(slide, ctx, 3);
  return slide;
}
