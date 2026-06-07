import { base, addLogo, t, panel, tag, C, footer } from "./common.mjs";

export async function slide02(presentation, ctx) {
  const slide = base(presentation, ctx, "研究框架", "用三类自然观看信息拆解短视频诱发的杏仁核-海马动态");
  await addLogo(slide, ctx);
  const cols = [
    ["研究一", "情绪效价", "标准化图片刺激", "正性/负性情绪是否在内侧颞叶产生可分辨的时间-频率响应？", C.rust],
    ["研究二", "主观偏好", "真实短视频", "个体喜欢/不喜欢是否调制 LFP 与单神经元放电？", C.teal],
    ["研究三", "刺激凸显性", "公开自然电影数据", "场景切换与高唤醒片段是否牵引 A-H 连接方向？", C.green],
  ];
  cols.forEach((c, i) => {
    const x = 72 + i * 392;
    panel(slide, ctx, x, 165, 336, 390, { fill: "#FFFFFF", stroke: c[4] });
    tag(slide, ctx, c[0], x + 24, 190, 88, c[4]);
    t(slide, ctx, c[1], x + 24, 242, 280, 38, { size: 31, bold: true, color: c[4] });
    t(slide, ctx, c[2], x + 24, 293, 280, 26, { size: 19, bold: true, color: C.ink });
    t(slide, ctx, c[3], x + 24, 355, 276, 100, { size: 20, color: C.ink });
    ctx.addShape(slide, { left: x + 24, top: 495, width: 288, height: 8, fill: c[4], line: ctx.line() });
  });
  t(slide, ctx, "答辩主线：刺激属性从“可控情绪”推进到“真实偏好”与“自然情境凸显性”。", 78, 604, 940, 32, { size: 22, bold: true, color: C.ink });
  footer(slide, ctx, 2);
  return slide;
}
