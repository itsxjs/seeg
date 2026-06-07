import { base, addLogo, t, panel, bullets, C, footer } from "./common.mjs";

export async function slide10(presentation, ctx) {
  const slide = base(presentation, ctx, "整合解释", "三项研究共同指向：MTL 对短视频信息的加工是分层、动态、双通道的");
  await addLogo(slide, ctx);
  const items = [
    ["情绪效价", "杏仁核早期中低频响应", "可控情绪输入"],
    ["主观偏好", "A/H LFP 与海马放电差异", "个体价值评估"],
    ["刺激凸显性", "A-H 连接与方向性变化", "自然情境事件"],
  ];
  items.forEach((it, i) => {
    const x = 95 + i * 382;
    panel(slide, ctx, x, 170, 310, 250, { fill: "#FFFFFF", stroke: [C.rust, C.teal, C.green][i] });
    t(slide, ctx, it[0], x + 24, 204, 250, 36, { size: 29, bold: true, color: [C.rust, C.teal, C.green][i] });
    t(slide, ctx, it[1], x + 24, 270, 250, 56, { size: 22, bold: true, color: C.ink });
    t(slide, ctx, it[2], x + 24, 354, 250, 34, { size: 18, color: C.muted });
  });
  ctx.addShape(slide, { left: 250, top: 458, width: 780, height: 2, fill: C.line, line: ctx.line() });
  bullets(slide, ctx, ["杏仁核更敏感于情绪/显著性信号，海马更参与情境组织与偏好相关放电", "短视频观看不是单一奖赏反应，而是情绪、偏好与事件结构共同塑造的动态过程"], 180, 515, 905, { size: 20, lineH: 40, dot: C.rust });
  footer(slide, ctx, 10);
  return slide;
}
