const pptxgen = require("/Users/defanive/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/pptxgenjs/dist/pptxgen.cjs.js");
const fs = require("fs");
const path = require("path");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "徐嘉晟";
pptx.subject = "短视频观看诱发的颅内脑电研究";
pptx.title = "0505讨论xjs";
pptx.company = "Zhejiang University";
pptx.lang = "zh-CN";
pptx.theme = {
  headFontFace: "Microsoft YaHei",
  bodyFontFace: "Microsoft YaHei",
  lang: "zh-CN",
};
pptx.defineLayout({ name: "LAYOUT_WIDE", width: 13.333, height: 7.5 });

const C = {
  navy: "0E2F44",
  blue: "176B9A",
  pale: "EAF3F7",
  ink: "1E2933",
  muted: "5C6B73",
  gray: "E4E8EB",
  red: "C95C67",
  rose: "F5D8DE",
  green: "5B9E72",
  gold: "C69C3A",
  white: "FFFFFF",
};

const media = "/Volumes/rmhyw/ppt_media_extract";
const keles = "/Volumes/rmhyw/keles_ah_nwb_pipeline/results";
const img = {
  zjuLogo: path.join(media, "image35.png"),
  zjuCampus: path.join(media, "image36.png"),
  mechanism: path.join(media, "image4.png"),
  overview: path.join(media, "image5.png"),
  pipeline: path.join(media, "image14.png"),
  behRt: path.join(media, "image17.png"),
  behAcc: path.join(media, "image18.png"),
  behLike: path.join(media, "image16.png"),
  behRating: path.join(media, "image15.png"),
  sceneAmyAvg: path.join(media, "image19.png"),
  sceneAmyStat: path.join(media, "image20.png"),
  sceneHipAvg: path.join(media, "image21.png"),
  sceneHipStat: path.join(media, "image22.png"),
  videoAmyAvg: path.join(media, "image23.png"),
  videoAmyStat: path.join(media, "image24.png"),
  videoHipAvg: path.join(media, "image25.png"),
  videoHipStat: path.join(media, "image26.png"),
  ifrLike: path.join(media, "image27.png"),
  coupling: path.join(media, "image28.png"),
  slope: path.join(media, "image29.png"),
  slopeDist: path.join(media, "image30.png"),
  fullCombined: path.join(media, "image31.png"),
  fullSgc: path.join(media, "image32.png"),
  kelesSpike: path.join(media, "image33.png"),
  kelesCluster: path.join(media, "image34.png"),
  arousalTimeline: path.join(keles, "arousal_short_local_3b_fix_full/arousal_vs_scenecut.png"),
  arousalSgc: path.join(keles, "full_spectrum_arousal_all_subjects/connectivity_arousal_fullspectrum/group_fullspectrum_arousal_sgc_overlay_sigshade.png"),
  thetaBeta: path.join(keles, "sgc_arousal_all_subjects/arousal_sgc_direction_theta_beta_maxlag3.png"),
};

function exists(p) {
  return fs.existsSync(p);
}

function base(slide, section, n) {
  slide.background = { color: "FFFFFF" };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 13.333, h: 0.22, fill: { color: C.navy }, line: { color: C.navy } });
  slide.addText(section, { x: 0.42, y: 0.31, w: 2.3, h: 0.25, fontSize: 8.5, bold: true, color: C.blue, margin: 0 });
  slide.addText(String(n).padStart(2, "0"), { x: 12.25, y: 0.27, w: 0.55, h: 0.25, fontSize: 10, bold: true, color: C.blue, align: "right", margin: 0 });
}

function title(slide, t, sub) {
  slide.addText(t, { x: 0.55, y: 0.65, w: 11.6, h: 0.42, fontSize: 24, bold: true, color: C.ink, margin: 0 });
  if (sub) slide.addText(sub, { x: 0.58, y: 1.1, w: 11.4, h: 0.26, fontSize: 10.5, color: C.muted, margin: 0 });
  slide.addShape(pptx.ShapeType.line, { x: 0.56, y: 1.43, w: 1.25, h: 0, line: { color: C.blue, width: 2 } });
}

function textBox(slide, lines, x, y, w, h, opts = {}) {
  const color = opts.color || C.ink;
  const fs = opts.fontSize || 12;
  slide.addText(lines.join("\n"), {
    x, y, w, h,
    fontSize: fs,
    color,
    breakLine: false,
    fit: "shrink",
    valign: "mid",
    margin: 0.05,
    paraSpaceAfterPt: 4,
    bullet: opts.bullet ? { type: "ul" } : undefined,
  });
}

function imageBox(slide, p, x, y, w, h, label) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: 0.03,
    fill: { color: "FFFFFF" },
    line: { color: C.gray, width: 0.7 },
  });
  if (exists(p)) {
    slide.addImage({ path: p, x: x + 0.04, y: y + 0.04, w: w - 0.08, h: h - 0.08, sizing: { type: "contain", x: x + 0.04, y: y + 0.04, w: w - 0.08, h: h - 0.08 } });
  } else {
    slide.addText("图像缺失\n" + p, { x: x + 0.15, y: y + 0.3, w: w - 0.3, h: h - 0.6, fontSize: 9, color: C.red, fit: "shrink" });
  }
  if (label) slide.addText(label, { x, y: y + h + 0.05, w, h: 0.18, fontSize: 8, color: C.muted, align: "center", margin: 0 });
}

function metric(slide, value, label, x, y, w, color = C.blue) {
  slide.addText(value, { x, y, w, h: 0.34, fontSize: 21, bold: true, color, align: "center", margin: 0 });
  slide.addText(label, { x, y: y + 0.38, w, h: 0.32, fontSize: 8.2, color: C.muted, align: "center", fit: "shrink", margin: 0 });
}

function chip(slide, txt, x, y, w, color = C.pale) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h: 0.34, rectRadius: 0.06, fill: { color }, line: { color, transparency: 100 } });
  slide.addText(txt, { x: x + 0.08, y: y + 0.07, w: w - 0.16, h: 0.16, fontSize: 8.5, bold: true, color: C.ink, align: "center", margin: 0, fit: "shrink" });
}

function addCover() {
  const s = pptx.addSlide();
  s.background = { color: C.navy };
  if (exists(img.zjuCampus)) s.addImage({ path: img.zjuCampus, x: 7.55, y: 0, w: 5.78, h: 7.5, transparency: 18, sizing: { type: "cover", x: 7.55, y: 0, w: 5.78, h: 7.5 } });
  s.addShape(pptx.ShapeType.rect, { x: 7.05, y: 0, w: 6.28, h: 7.5, fill: { color: C.navy, transparency: 18 }, line: { color: C.navy, transparency: 100 } });
  s.addText("0505 讨论汇报", { x: 0.75, y: 0.72, w: 5, h: 0.3, fontSize: 14, color: "A9D3E7", bold: true, margin: 0 });
  s.addText("短视频观看诱发的\n颅内脑电研究", { x: 0.72, y: 1.55, w: 6.8, h: 1.35, fontSize: 34, color: C.white, bold: true, breakLine: false, margin: 0 });
  s.addShape(pptx.ShapeType.line, { x: 0.76, y: 3.15, w: 2.0, h: 0, line: { color: "82C3E0", width: 2.5 } });
  s.addText("基于当前毕业论文正文补全分析页，并将每页说明更新为可汇报的统计结果", { x: 0.78, y: 3.45, w: 6.2, h: 0.42, fontSize: 14, color: "D7EAF2", margin: 0 });
  s.addText("徐嘉晟  |  心理与行为科学系  |  浙江大学", { x: 0.78, y: 6.75, w: 6.2, h: 0.25, fontSize: 11, color: "D7EAF2", margin: 0 });
  if (exists(img.zjuLogo)) s.addImage({ path: img.zjuLogo, x: 11.4, y: 6.3, w: 1.1, h: 1.1 });
}

function addSlide(section, n, t, sub, bodyLines, pictures = []) {
  const s = pptx.addSlide();
  base(s, section, n);
  title(s, t, sub);
  if (pictures.length === 0) {
    textBox(s, bodyLines, 0.78, 1.85, 11.6, 4.7, { bullet: true, fontSize: 14 });
  } else if (pictures.length === 1) {
    imageBox(s, pictures[0].path, pictures[0].x || 0.72, pictures[0].y || 1.75, pictures[0].w || 7.05, pictures[0].h || 4.85, pictures[0].label);
    textBox(s, bodyLines, pictures[0].tx || 8.05, pictures[0].ty || 1.9, pictures[0].tw || 4.45, pictures[0].th || 4.45, { bullet: true, fontSize: 11.5 });
  } else {
    pictures.forEach(p => imageBox(s, p.path, p.x, p.y, p.w, p.h, p.label));
    if (bodyLines && bodyLines.length) textBox(s, bodyLines, 0.75, 6.42, 11.9, 0.62, { fontSize: 9.5 });
  }
  return s;
}

addCover();

let n = 2;
let s = addSlide("研究背景", n++, "短视频是连续分发的短时长视听刺激", "从平台特征转向颅内脑电问题：快速变化的视听片段如何诱发边缘系统活动", [
  "已有研究将短视频特征概括为个性化推荐、低成本连续浏览、即时满足和多模态呈现。",
  "本研究不把短视频简单视为“标准图片的自然版本”，而是关注其连续视听信息、主观偏好和事件结构共同诱发的颅内脑电活动。",
  "现有研究多依赖问卷、行为或fMRI；本研究用iEEG/LFP/spike在毫秒尺度分析杏仁核—海马系统。",
], [{ path: img.mechanism, x: 7.45, y: 1.95, w: 4.45, h: 3.2, tx: 0.78, ty: 1.9, tw: 6.1, th: 4.2, label: "情绪、奖赏与记忆相关脑区示意" }]);
metric(s, "3个研究", "标准图片 → 真实短视频 → 公开自然视频", 0.9, 5.75, 2.4);
metric(s, "毫秒级", "颅内脑电时间分辨率", 3.65, 5.75, 2.4);
metric(s, "A-H系统", "杏仁核—海马局部与跨区活动", 6.4, 5.75, 2.7);
metric(s, "偏好评分", "1-5分主观喜欢/渴望", 9.55, 5.75, 2.35);

addSlide("研究问题", n++, "三个问题对应三类证据", "每个研究只回答一个核心层次：效价基线、短视频偏好、自然视频跨区通信", [
  "研究一：标准化情绪图片条件下，杏仁核/海马是否表现出效价相关频谱活动？",
  "研究二：真实短视频观看中，主观喜欢程度是否调制LFP功率和放电单元活动？",
  "研究三：公开自然视频数据中，A-H之间是否存在与场景切割或高唤醒片段相关的功能连接和方向性信息流？",
], [{ path: img.overview, x: 0.9, y: 1.75, w: 5.6, h: 3.7, tx: 7.0, ty: 1.9, tw: 5.0, th: 3.6, label: "论文当前三研究结构" }]);

addSlide("实验范式", n++, "研究一与研究二：从效价判断到主观偏好", "同一套自采iEEG来源，任务目标从情绪效价推进到真实短视频偏好", [
  "研究一：IAPS标准图片120张，正/中/负各40张；图片呈现后进行1/2/3效价按键判断。",
  "研究二：66段真实短视频，每段截取开头5 s；观看后完成1-5分喜欢程度和继续观看渴望评分。",
  "后续主分析以喜欢评分划分like/dislike，因为喜欢程度与继续观看渴望高度一致，避免重复解释同一行为维度。",
]);
chip(pptx._slides[pptx._slides.length - 1], "LFP分析 N=3", 0.88, 5.76, 2.0);
chip(pptx._slides[pptx._slides.length - 1], "spike分析 N=2", 3.12, 5.76, 2.0);
chip(pptx._slides[pptx._slides.length - 1], "短视频 66段 × 5 s", 5.36, 5.76, 2.35);
chip(pptx._slides[pptx._slides.length - 1], "评分 1-5分", 8.0, 5.76, 1.65);

addSlide("数据预处理", n++, "LFP与spike使用统一事件锁定流程", "重点不是“做了预处理”，而是保证不同任务结果可比较", [
  "LFP：降采样至1000 Hz，1-200 Hz带通，49-51 Hz陷波；对齐行为事件后提取epoch。",
  "QC：robust RMS/峰值规则与幅度规则取交集，降低伪迹试次对时频结果的影响。",
  "spike：kilosort排序、phy人工QC；spike time对齐事件窗，用高斯核平滑估计IFR。",
], [{ path: img.pipeline, x: 0.9, y: 1.7, w: 6.3, h: 4.55, tx: 7.65, ty: 1.9, tw: 4.55, th: 4.0, label: "spike sorting与事件对齐示意" }]);

addSlide("研究一、二结果", n++, "行为结果：评分标准存在明显个体差异", "行为层面支持使用被试内评分定义条件，而不是按视频类别先验分组", [
  "情境判别任务：各被试能够完成效价判断，但反应时和正确率存在较大个体差异。",
  "固定观看任务：like/dislike数量与评分分布在被试间差异明显，符合真实短视频偏好的主观性。",
  "分析策略：研究二以被试自身喜欢评分定义like/dislike条件，避免将群体类别误当作个体偏好。",
], [
  { path: img.behRt, x: 0.7, y: 1.7, w: 2.95, h: 1.9, label: "情境判别反应时" },
  { path: img.behAcc, x: 3.95, y: 1.7, w: 2.95, h: 1.9, label: "情境判别正确率" },
  { path: img.behLike, x: 7.2, y: 1.7, w: 2.55, h: 1.9, label: "like/dislike数量" },
  { path: img.behRating, x: 10.05, y: 1.7, w: 2.55, h: 1.9, label: "评分分布" },
]);

addSlide("研究一结果", n++, "标准情绪图片：杏仁核出现效价相关时频簇", "cluster-based permutation test揭示杏仁核效价敏感性，海马未形成稳定显著簇", [
  "杏仁核：1000次置换cluster校正后出现两个显著簇；主簇位于刺激后450-800 ms、5.8-20.2 Hz。",
  "杏仁核晚期低频簇：1650-1950 ms、2.0-4.1 Hz。",
  "海马：存在未校正p值较低的局部点，但cluster校正后未出现显著簇。",
  "解释：研究一建立情绪效价加工参照，主要支持杏仁核对标准图片效价更敏感。",
], [
  { path: img.sceneAmyAvg, x: 0.7, y: 1.7, w: 2.95, h: 2.0, label: "Amygdala平均时频" },
  { path: img.sceneAmyStat, x: 3.95, y: 1.7, w: 2.95, h: 2.0, label: "Amygdala cluster统计" },
  { path: img.sceneHipAvg, x: 7.2, y: 1.7, w: 2.95, h: 2.0, label: "Hippocampus平均时频" },
  { path: img.sceneHipStat, x: 10.45, y: 1.7, w: 2.2, h: 2.0, label: "Hippocampus统计" },
]);

addSlide("研究二结果", n++, "真实短视频：偏好同时调制杏仁核和海马频谱", "相较研究一，海马在真实短视频偏好加工中参与更明显", [
  "杏仁核：like/dislike比较出现450-1100 ms、4.9-24.2 Hz的cluster校正时频簇。",
  "海马：出现700-1200 ms、2.0-28.9 Hz的cluster校正时频簇，时间窗晚于杏仁核。",
  "方向性解释：喜欢视频并非简单正性效价，而可能涉及情境、事件结构和观看动机整合。",
  "注意：LFP分析基于3名被试，结果应作为小样本探索性证据，不扩大为稳定组水平结论。",
], [
  { path: img.videoAmyAvg, x: 0.7, y: 1.7, w: 2.95, h: 2.0, label: "Amygdala平均时频" },
  { path: img.videoAmyStat, x: 3.95, y: 1.7, w: 2.95, h: 2.0, label: "Amygdala cluster统计" },
  { path: img.videoHipAvg, x: 7.2, y: 1.7, w: 2.95, h: 2.0, label: "Hippocampus平均时频" },
  { path: img.videoHipStat, x: 10.45, y: 1.7, w: 2.2, h: 2.0, label: "Hippocampus统计" },
]);

addSlide("研究二结果", n++, "短视频spike：like事件后IFR增量低于dislike", "放电单元结果支持“偏好不是整体放电增强”", [
  "两个短视频被试共提取45个可分析放电单元。",
  "K-means得到两个响应模式簇：cluster 0为22个单元，cluster 1为23个单元。",
  "cluster 1在事件后0.20-0.70 s和1.25-1.65 s出现like/dislike差异：like条件基线校正IFR更低，dislike条件IFR更高。",
  "全脑区Wilcoxon检验p=0.128，提示趋势性差异，需谨慎解释。",
], [{ path: img.ifrLike, x: 0.8, y: 1.75, w: 6.8, h: 4.65, tx: 8.05, ty: 1.75, tw: 4.45, th: 4.55, label: "like/dislike条件IFR时间曲线" }]);

addSlide("研究二结果", n++, "短视频spike：耦合弱，但dislike响应斜率更高", "IFR耦合与响应斜率提供局部放电层面的补充证据", [
  "脑区内耦合：like约0.008，dislike约-0.005；脑区间耦合：like约0.006，dislike约0.004，整体接近零。",
  "杏仁核响应斜率：dislike约0.267 Hz/s，高于like约0.102 Hz/s。",
  "海马响应斜率：dislike约0.137 Hz/s，like约-0.023 Hz/s。",
  "结论：不喜欢或高显著性内容可能诱发更陡峭的事件后放电反应。",
], [
  { path: img.coupling, x: 0.75, y: 1.7, w: 3.75, h: 2.55, label: "耦合强度" },
  { path: img.slope, x: 4.8, y: 1.7, w: 3.75, h: 2.55, label: "响应斜率/早晚期" },
  { path: img.slopeDist, x: 8.85, y: 1.7, w: 3.55, h: 2.55, label: "斜率分布" },
]);

addSlide("研究三方法", n++, "Keles公开自然视频数据：更大样本、更连续的外部探索", "研究三不是严格验证，而是将A-H分析扩展到自然连续视频观看", [
  "数据集：Keles et al.公开自然视频观看数据；本地分析共识别16名被试、29个真实NWB run。",
  "full-spectrum组分析：27个run通过QC，2个run因无可用clean trial被跳过。",
  "事件标记：官方场景切割事件 + 探索性AI高唤醒片段。",
  "分析指标：A-H相干性、spectral Granger causality、事件锁定IFR与响应模式聚类。",
]);
chip(pptx._slides[pptx._slides.length - 1], "16名被试", 1.05, 5.75, 1.7);
chip(pptx._slides[pptx._slides.length - 1], "29个真实NWB run", 3.05, 5.75, 2.2);
chip(pptx._slides[pptx._slides.length - 1], "27个run进入组分析", 5.6, 5.75, 2.35);
chip(pptx._slides[pptx._slides.length - 1], "2个run QC跳过", 8.3, 5.75, 2.0);

addSlide("研究三结果", n++, "5.3.1 功能连接：A-H相干性集中在低频范围", "自然视频场景切割附近，低频连接更稳定", [
  "场景切割事件锁定后，杏仁核—海马组平均相干性在3.9-43.0 Hz范围内约为0.34-0.49。",
  "全频段结果显示连接强度主要集中在低频范围。",
  "解释：自然视频观看需要跨时间整合场景、人物和事件信息，低频振荡可能提供跨区协调框架。",
], [{ path: img.fullCombined, x: 0.65, y: 1.65, w: 7.15, h: 4.9, tx: 8.15, ty: 1.9, tw: 4.4, th: 4.1, label: "Keles场景切割锁定A-H相干性与sGC" }]);

addSlide("研究三结果", n++, "5.3.2 方向性信息流：总体H→A更强，并具有频段特异性", "这页补入正文新增的全频谱A→H/H→A对比结果", [
  "组水平平均sGC：H→A=0.584，A→H=0.535，平均方向差=0.049。",
  "A→H与H→A配对比较经FDR校正后，共21个频率点达到q<0.05。",
  "显著频段集中在9.6-13.2 Hz、17.6-20.0 Hz和43.6-44.8 Hz。",
  "结合时滞分析：多数试次中海马活动领先杏仁核，但方向性并非所有频段固定一致。",
], [{ path: img.fullSgc, x: 0.7, y: 1.65, w: 7.1, h: 4.9, tx: 8.05, ty: 1.72, tw: 4.7, th: 4.7, label: "Group Full-Spectrum Spectral GC" }]);

addSlide("研究三结果", n++, "5.3.3 事件相关放电率：场景切割诱发A-H放电调制", "spike层面支持自然视频事件能够调制两个脑区活动，但同步性较弱", [
  "以场景切割为事件零点，杏仁核和海马均显示事件相关放电率调制。",
  "区域感知spike汇总显示：脑区内IFR耦合整体强于A-H跨脑区耦合，但总体耦合强度较弱。",
  "A-H时滞分析显示多数试次中海马领先杏仁核；同时也存在部分试次杏仁核中位领先约300 ms。",
  "解释：方向性关系存在试次间异质性，不能概括为固定单向序列。",
], [{ path: img.kelesSpike, x: 0.7, y: 1.7, w: 6.9, h: 4.7, tx: 8.05, ty: 1.75, tw: 4.55, th: 4.55, label: "Keles spike summary" }]);

addSlide("研究三结果", n++, "5.3.3 响应模式聚类：事件后同时存在抑制型与激活型单元", "平均放电率会掩盖不同放电单元群的相反响应方向", [
  "基于单元IFR时间曲线聚类得到两类响应模式。",
  "抑制型单元：n=899，事件后放电率下降。",
  "激活型单元：n=503，事件后放电率升高。",
  "两类曲线在事件发生后迅速分离，并在0-2 s响应窗保持相反变化方向。",
], [{ path: img.kelesCluster, x: 0.78, y: 1.72, w: 7.0, h: 4.65, tx: 8.15, ty: 1.8, tw: 4.4, th: 4.45, label: "IFR响应模式聚类" }]);

addSlide("新增分析页", n++, "5.2.5 VLM高唤醒标注：为自然视频提供可复现事件集合", "当前PPT原先没有这一分析流程页，需补入方法逻辑", [
  "模型：Qwen2.5-VL-3B-Instruct，本地零样本标注；temperature=0，max_new_tokens=128。",
  "窗口：2.0 s窗口、1.0 s步长；每个窗口抽取4帧，并结合音频显著性。",
  "评分：final_score = 0.7 × arousal_score + 0.2 × confidence + 0.1 × normalized_audio_salience。",
  "筛选：z_final_score ≥ 1.5，arousal_score ≥ 70，confidence ≥ 60；相邻命中窗口合并。",
]);
chip(pptx._slides[pptx._slides.length - 1], "477个候选窗口", 1.0, 5.75, 2.0, C.rose);
chip(pptx._slides[pptx._slides.length - 1], "19个高唤醒片段", 3.35, 5.75, 2.1, C.rose);
chip(pptx._slides[pptx._slides.length - 1], "parse/inference失败=0", 5.82, 5.75, 2.35, C.rose);
chip(pptx._slides[pptx._slides.length - 1], "5000次置换检验", 8.55, 5.75, 2.1, C.rose);

addSlide("新增分析页", n++, "5.3.4 高唤醒片段与官方场景切割存在时间邻近", "AI标注用于探索高唤醒事件是否贴近自然视频事件边界", [
  "VLM共扫描477个2 s候选窗口，筛选出19个高唤醒片段。",
  "所选片段与官方场景切割的±2 s命中率为68.4%。",
  "随机基线为55.2%，富集倍数约1.24；置换检验p=0.174。",
  "结论：高唤醒片段与场景切割有数值邻近趋势，但未达到显著，不能把AI标注当作人工验证标签。",
], [{ path: img.arousalTimeline, x: 0.65, y: 1.72, w: 7.25, h: 4.55, tx: 8.25, ty: 1.8, tw: 4.35, th: 4.45, label: "AI高唤醒窗口与官方shot starts" }]);

addSlide("新增分析页", n++, "高唤醒事件锁定full-spectrum sGC：数值上仍为H→A更强", "补足正文中高唤醒事件下的全频谱方向性分析", [
  "高唤醒事件锁定后，27个run进入组水平full-spectrum分析，2个run因QC失败排除。",
  "平均相干性=0.380。",
  "H→A平均sGC=1.501，A→H平均sGC=1.438。",
  "方向差数值上仍为H→A更强，但该全频平均不能概括所有频段。",
], [{ path: img.arousalSgc, x: 0.75, y: 1.72, w: 7.0, h: 4.65, tx: 8.15, ty: 1.82, tw: 4.5, th: 4.4, label: "High-arousal full-spectrum sGC" }]);

addSlide("新增分析页", n++, "θ/β分频段sGC：方向性关系具有频段特异性", "这页补上正文5.3.4中最关键的频段对比结果", [
  "θ频段（4-8 Hz）：A→H=319.139，H→A=326.074，方向差较小；FDR校正后不显著。",
  "β频段（13-30 Hz）：A→H=712.473，H→A=282.589；配对t检验FDR校正后仍显著。",
  "与全频平均H→A优势不完全一致，说明A-H通信方向会随频段和事件类型改变。",
], [{ path: img.thetaBeta, x: 0.75, y: 1.72, w: 7.0, h: 4.65, tx: 8.15, ty: 1.92, tw: 4.55, th: 4.15, label: "AI高唤醒片段锁定θ/β方向性sGC" }]);

addSlide("综合结论", n++, "三类证据共同指向：短视频诱发A-H系统可测量电生理变化", "结论改为报告结果，而不是泛泛说“可能有关”", [
  "研究一：杏仁核对标准图片效价敏感，cluster校正显著簇位于450-800 ms、5.8-20.2 Hz；海马未出现稳定显著簇。",
  "研究二：真实短视频偏好同时调制杏仁核和海马频谱，杏仁核450-1100 ms、4.9-24.2 Hz；海马700-1200 ms、2.0-28.9 Hz。",
  "研究三：自然视频场景切割锁定下，A-H低频相干性更稳定，full-spectrum sGC总体H→A更强，且海马多数试次领先杏仁核。",
  "补充：高唤醒片段分频段分析显示β频段A→H优势，提示方向性通信具有频段特异性。",
]);

addSlide("讨论与局限", n++, "结果解释需要同时保留“总体趋势”和“频段特异性”", "当前最稳妥的论文表述：初步证据、探索性分析、避免过度机制化", [
  "机制解释：自然视频需要持续追踪场景和事件，海马可能先组织情境信息，再影响杏仁核的显著性/价值加工。",
  "频段限制：β频段高唤醒结果显示A→H优势，因此不能写成固定的海马先行序列。",
  "样本限制：自采iEEG样本小，通道/单元不能等同于独立被试；研究三数据集任务目标与短视频任务不同。",
  "方法限制：AI高唤醒标注是可复现探索性事件集合，仍需要人工验证和信效度评估。",
]);

addSlide("References & Code", n++, "关键参考与代码可用性", "保留原PPT参考页功能，更新为与当前正文最相关的引用", [
  "短视频与推荐：Su et al., 2021; Zhang et al., 2019; Huang et al., 2022; Xiong et al., 2024。",
  "杏仁核—海马与情绪/显著性：Zheng et al., 2017; Manssuer et al., 2022; Sonkusare et al., 2023。",
  "方法：Lang et al., 1997; Granger, 1969; Barnett & Seth, 2014, 2015; Binns et al., 2026。",
  "代码仓库：https://github.com/itsxjs/seeg",
]);

const thanks = pptx.addSlide();
thanks.background = { color: C.navy };
thanks.addText("谢 谢", { x: 0.8, y: 2.15, w: 5.0, h: 0.7, fontSize: 42, bold: true, color: C.white, margin: 0 });
thanks.addText("敬请各位老师批评指正", { x: 0.85, y: 3.05, w: 5.2, h: 0.35, fontSize: 18, color: "D7EAF2", margin: 0 });
thanks.addText("短视频观看诱发的颅内脑电研究  |  0505讨论", { x: 0.88, y: 6.65, w: 6.0, h: 0.25, fontSize: 10.5, color: "B9DDEB", margin: 0 });
if (exists(img.zjuCampus)) thanks.addImage({ path: img.zjuCampus, x: 7.15, y: 0, w: 6.18, h: 7.5, transparency: 10, sizing: { type: "cover", x: 7.15, y: 0, w: 6.18, h: 7.5 } });
if (exists(img.zjuLogo)) thanks.addImage({ path: img.zjuLogo, x: 11.4, y: 6.25, w: 1.1, h: 1.1 });

pptx.writeFile({ fileName: "/Volumes/rmhyw/0505讨论xjs.pptx" });
