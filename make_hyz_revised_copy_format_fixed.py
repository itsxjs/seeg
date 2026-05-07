from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph


SRC = Path("/Users/defanive/Desktop/徐嘉晟-本科毕设-sEEG-短视频-HYZ.docx")
OUT = Path("/Volumes/rmhyw/徐嘉晟-本科毕设-sEEG-短视频-HYZ_批注修订全文副本_格式修复版.docx")
MD_OUT = Path("/Volumes/rmhyw/徐嘉晟-本科毕设-sEEG-短视频-HYZ_批注修订全文副本_格式修复版.md")


doc = Document(SRC)


def find_para_exact(text, start=0):
    for i, p in enumerate(doc.paragraphs[start:], start):
        if p.text.strip() == text:
            return i
    raise ValueError(f"paragraph not found: {text}")


def find_heading(text, start=0):
    return find_para_exact(text, start)


def next_heading_index(start_idx):
    for i in range(start_idx + 1, len(doc.paragraphs)):
        txt = doc.paragraphs[i].text.strip()
        style = doc.paragraphs[i].style.name if doc.paragraphs[i].style else ""
        if style.startswith("Heading") and txt:
            return i
    return len(doc.paragraphs)


def delete_paragraph(paragraph):
    p = paragraph._element
    p.getparent().remove(p)
    paragraph._p = paragraph._element = None


def insert_after(paragraph, text="", style=None):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    p = Paragraph(new_p, paragraph._parent)
    if style:
        p.style = style
    p.add_run(text)
    return p


def replace_section(heading_text, blocks, style="Normal"):
    h_idx = find_heading(heading_text)
    end = next_heading_index(h_idx)
    heading = doc.paragraphs[h_idx]
    for p in list(doc.paragraphs[h_idx + 1:end]):
        delete_paragraph(p)
    cursor = heading
    for block in blocks:
        if isinstance(block, tuple):
            text, block_style = block
        else:
            text, block_style = block, style
        cursor = insert_after(cursor, text, style=block_style)


def replace_between(start_text, end_text, blocks, default_style):
    s_idx = find_para_exact(start_text)
    e_idx = find_para_exact(end_text, s_idx + 1)
    start = doc.paragraphs[s_idx]
    for p in list(doc.paragraphs[s_idx + 1:e_idx]):
        delete_paragraph(p)
    cursor = start
    for block in blocks:
        if isinstance(block, tuple):
            text, style = block
        else:
            text, style = block, default_style
        cursor = insert_after(cursor, text, style=style)


abstract_cn = [
    "短视频是一类以短时长视听内容为基础、依托移动端平台进行连续分发和观看的媒介形式。已有研究指出，短视频平台通常具有个性化推荐、低成本连续浏览、即时满足和多模态呈现等特征。这些特征使用户在观看过程中持续接触快速切换的视听信息，并可能伴随注意分配、情绪反应、主观偏好形成和情境记忆整合等加工过程。既往关于短视频使用及其潜在风险的研究多集中于问卷、行为表现或功能影像层面，对于短视频观看诱发的人脑电生理活动，尤其是相关脑区如何在毫秒级时间尺度上响应短视频内容，仍缺乏直接证据。基于杏仁核在情绪显著性和价值评估中的作用，以及海马在情境记忆和事件结构加工中的作用，本研究聚焦杏仁核—海马系统，考察短视频观看诱发的颅内脑电活动及其与主观偏好的关系。",
    "本研究拟回答三个核心问题：第一，在标准化情绪图片条件下，杏仁核和海马是否能够表现出效价相关的频谱活动；第二，在短视频观看条件下，主观喜欢程度是否能够调制杏仁核和海马的局部场电位功率及放电单元活动；第三，在公开自然视频观看数据集中，杏仁核和海马之间是否存在与自然事件边界或高唤醒片段相关的功能连接和方向性信息流。",
    "研究一采用标准情绪图片和效价判断任务，纳入自采颅内脑电被试中可用于LFP分析的3名被试，以图片呈现为事件零点分析2-100 Hz时频功率。研究二采用66段短视频片段和1-5分主观偏好评分任务，基于3名LFP分析被试和2名放电单元分析被试，探索喜欢与不喜欢条件下杏仁核和海马的频谱活动及事件锁定放电率。研究三基于Keles等人的公开自然视频观看数据集，作为外部自然连续刺激情境下的拓展性分析，进一步计算杏仁核—海马相干性、谱格兰杰因果性以及事件相关放电率。",
    "结果显示，研究一中杏仁核在效价比较中出现cluster校正后的时频簇，主要位于刺激后450-800 ms、5.8-20.2 Hz及1650-1950 ms、2.0-4.1 Hz；海马在cluster校正后未形成稳定显著簇。研究二中，喜欢/不喜欢比较在杏仁核中出现450-1100 ms、4.9-24.2 Hz的偏好相关时频簇，海马中出现700-1200 ms、2.0-28.9 Hz的偏好相关时频簇。",
    "研究三中，场景切割事件锁定分析显示杏仁核—海马组平均相干性在3.9-43.0 Hz范围内约为0.34-0.49；谱格兰杰因果分析显示H→A方向平均值为0.584，A→H方向平均值为0.535，平均方向差为0.049，FDR校正后显著频点主要分布在9.6-13.2 Hz、17.6-20.0 Hz和43.6-44.8 Hz。探索性高唤醒标注中，视觉语言模型扫描477个2 s候选窗口并筛选出19个高唤醒片段。进一步的分频段sGC分析显示，θ频段（4-8 Hz）中A→H与H→A方向差异较小，A→H平均值为319.139，H→A平均值为326.074，FDR校正后未达到显著；β频段（13-30 Hz）则表现出A→H方向优势，A→H平均值为712.473，H→A平均值为282.589，FDR校正后仍显著。",
    "综上，本研究提供了短视频观看诱发杏仁核—海马系统颅内电生理响应的初步证据：杏仁核对情绪效价和主观偏好均表现出敏感性，海马在短视频偏好加工中呈现显著频谱变化；在跨区通信方面，杏仁核—海马系统总体表现为海马到杏仁核方向的信息流更强，且海马活动在时间上领先杏仁核，但这种方向性关系可能具有频段特异性。这些发现为理解短视频偏好加工提供了初步颅内电生理证据，并可作为后续短视频过度使用风险研究的基础线索。",
    "关键字：短视频，颅内脑电，杏仁核，海马，情绪加工",
]

abstract_en = [
    "Short-form video is a media form based on brief audiovisual content that is continuously distributed and viewed through mobile platforms. Previous studies have suggested that short-form video platforms are characterized by personalized recommendation, low-cost continuous browsing, immediate gratification, and multimodal presentation. These features allow users to continuously encounter rapidly changing audiovisual information during viewing, and may be accompanied by attention allocation, emotional responses, subjective preference formation, and contextual memory integration. Existing studies on short-form video use and its potential risks have mainly relied on questionnaires, behavioral measures, or functional imaging. Direct evidence remains limited regarding the electrophysiological activity induced by short-form video viewing, especially how relevant brain regions respond to short-form video content at the millisecond timescale. Given the roles of the amygdala in affective salience and value evaluation, and of the hippocampus in contextual memory and event-structure processing, this study focused on the amygdala-hippocampal system and examined intracranial EEG activity induced by short-form video viewing and its relationship with subjective preference.",
    "This study addressed three main questions. First, do the amygdala and hippocampus show valence-related spectral activity during standardized emotional picture viewing? Second, during short-form video viewing, does subjective liking modulate local field potential power and firing-unit activity in the amygdala and hippocampus? Third, in a public natural video viewing dataset, do amygdala-hippocampal functional connectivity and directional information flow relate to natural event boundaries or high-arousal segments?",
    "Study 1 used standardized emotional pictures and a valence judgment task. In the self-collected intracranial EEG dataset, three participants were included in the LFP analysis, and time-frequency power from 2 to 100 Hz was analyzed time-locked to picture onset. Study 2 used 66 short-form video clips and a 1-5 subjective preference rating task. Based on three LFP participants and two firing-unit participants, it examined spectral activity and event-locked firing rates in the amygdala and hippocampus under liked and disliked conditions. Study 3 used the public natural video viewing dataset from Keles et al. as an external extension in a continuous natural-stimulus setting, and further examined amygdala-hippocampal coherence, spectral Granger causality, and event-related firing rates.",
    "The results showed that, in Study 1, the amygdala exhibited cluster-corrected time-frequency effects in the valence comparison, mainly at 450-800 ms and 5.8-20.2 Hz after stimulus onset, and at 1650-1950 ms and 2.0-4.1 Hz. The hippocampus did not show stable significant clusters after cluster correction. In Study 2, the liked versus disliked comparison revealed preference-related time-frequency clusters in the amygdala at 450-1100 ms and 4.9-24.2 Hz, and in the hippocampus at 700-1200 ms and 2.0-28.9 Hz.",
    "In Study 3, scene-cut-locked analysis showed group-average amygdala-hippocampal coherence of approximately 0.34-0.49 within the 3.9-43.0 Hz range. Spectral Granger causality analysis yielded a mean H→A value of 0.584, a mean A→H value of 0.535, and a mean directional difference of 0.049. After FDR correction, significant frequency points were mainly distributed at 9.6-13.2 Hz, 17.6-20.0 Hz, and 43.6-44.8 Hz. In the exploratory high-arousal annotation analysis, a vision-language model scanned 477 candidate 2-s windows and selected 19 high-arousal segments. Further frequency-specific sGC analysis showed little directional difference between A→H and H→A in the theta band (4-8 Hz), with mean values of 319.139 for A→H and 326.074 for H→A; this difference did not survive FDR correction. By contrast, the beta band (13-30 Hz) showed an A→H directional advantage, with mean values of 712.473 for A→H and 282.589 for H→A, which remained significant after FDR correction.",
    "Taken together, this study provides preliminary evidence for intracranial electrophysiological responses induced by short-form video viewing in the amygdala-hippocampal system. The amygdala showed sensitivity to both emotional valence and subjective preference, whereas the hippocampus exhibited significant spectral changes during preference processing in short-form video viewing. In terms of cross-regional communication, the amygdala-hippocampal system showed a stronger overall information flow from the hippocampus to the amygdala, with hippocampal activity leading amygdala activity in time; however, this directional relationship may be frequency-specific. These findings provide preliminary intracranial electrophysiological evidence for understanding short-form video preference processing and may serve as a foundation for future research on the risk of excessive short-form video use.",
    "Key words: short-form video, intracranial EEG, amygdala, hippocampus, emotional processing",
]

replace_between("摘 要", "Abstract", abstract_cn, "段")
replace_between("Abstract", "目录", abstract_en, "Normal")

replace_section("1.1 短视频的使用现状", [
    "近年来，伴随移动互联网和智能终端的普及，以抖音、快手为代表的短视频平台已经成为中国网民最主要的网络应用形式之一。根据中国互联网络信息中心第56次《中国互联网络发展状况统计报告》，截至2025年6月，我国网络视频用户规模达10.85亿人，占网民整体的96.7%；其中，短视频用户规模达10.68亿人，占网民整体的95.1%（中国互联网络信息中心，2025）。这一数据表明，短视频已经不再是特定群体的娱乐应用，而是高度普及的日常媒介环境。",
    "短视频平台通常以短时长视听内容为基本单元，并通过移动端界面实现连续分发和快速切换。已有研究将短视频平台的核心特征概括为个性化算法推荐、低成本连续浏览、即时满足、多模态呈现和社交互动等（Huang et al., 2022；Xiong et al., 2024）。这些特征使用户能够在较少操作负担下持续接触快速变化的视听片段，并在观看过程中不断形成注意分配、情绪反应、主观偏好和继续观看意愿。",
    "与传统长视频或静态图像材料相比，短视频的关键特点不在于单个视频一定具有更强的情绪强度，而在于平台能够以连续、快速、个性化的方式组织内容。用户在短时间内反复接触不同主题、节奏和情绪线索的视频片段，这种媒介结构为研究自然媒介刺激下的人类情绪、偏好和情境加工提供了重要背景。",
])

replace_section("1.2 短视频过度使用的风险及相关研究背景", [
    "短视频的高普及率本身并不等同于问题性使用，但其平台机制使部分用户更容易形成持续观看和难以中断的行为模式。对于一般使用者而言，个性化推荐和低成本连续浏览提高了内容获取效率和娱乐体验；但对于自我控制能力较弱、情绪调节困难或具有逃避性使用动机的个体而言，连续推荐和快速反馈可能增加过度使用风险。近年来，问题性短视频使用、短视频成瘾倾向以及短视频平台相关的注意、睡眠和情绪调节问题已成为网络行为研究中的重要主题。",
    "从学习理论角度看，短视频平台的连续推荐机制与操作性条件反射中的强化过程具有一定相似性。Skinner提出，行为如果能够反复获得强化结果，其发生概率会增加；而在变比率强化程序中，奖励出现的时间和频率具有不确定性，个体往往更容易持续重复该行为。短视频浏览过程中，用户并不能预知下一条视频是否有趣、惊奇或情绪上吸引人，但每一次上滑都可能带来新的奖励性内容。这种不确定但高频的反馈结构，可能使“继续滑动—获得新刺激—再次滑动”的行为链条不断被强化。",
    "在算法层面，短视频平台通常会根据用户的停留时间、点赞、评论、转发、跳过和重复观看等行为信号持续更新推荐内容。推荐系统通过不断估计用户偏好，提高后续内容与个体兴趣的匹配度。若某些内容能够更有效地引发情绪唤醒、好奇、新奇感或继续观看意愿，算法就可能在后续推送中进一步增加类似内容的出现概率。由此，短视频使用并不仅是被动观看过程，也包含用户行为反馈、算法更新和内容再推荐之间的循环。正是这种“行为反馈—算法推荐—继续观看”的闭环，使短视频过度使用问题具有区别于传统视频观看的机制特征。",
    "需要指出的是，本研究并不直接测量短视频成瘾或过度使用行为，而是关注短视频观看过程中情绪和主观偏好在脑内如何被快速加工。换言之，本文的重点不是诊断问题性使用，而是为后续理解短视频过度使用风险提供基础电生理证据。",
])

replace_section("1.3 杏仁核—海马情绪奖赏加工网络及其振荡通信机制", [
    "在短视频观看过程中，用户需要连续处理快速变化的视觉、听觉、语义和情节信息，并形成对内容的情绪反应和主观偏好。杏仁核和海马均是与情绪、价值和记忆加工密切相关的深部脑区。杏仁核通常被认为参与刺激情绪意义、生物学显著性和价值信息的快速评估；海马则更多参与情境记忆、事件结构和经验关联的编码。短视频片段中的新奇性、冲突性、情绪线索和情节变化，可能同时调动杏仁核对显著性信息的快速反应，以及海马对情境和事件结构的整合。因此，杏仁核—海马系统为理解短视频观看中情绪、偏好和情境加工的神经机制提供了关键切入点。",
    "已有研究表明，杏仁核和海马之间的相互作用并非仅体现为平均激活水平的共同升高，而可能通过频段特异的神经振荡和方向性通信实现。低频振荡，尤其是θ和α频段，通常被认为更适合承担跨脑区协调、情绪记忆整合和时序信息组织等功能；较高频段活动则更接近局部神经元群活动和刺激特征编码。对于短视频这类连续视听刺激而言，不同频段可能分别反映局部显著性编码、情境整合以及跨脑区信息传递。",
    "已有神经影像研究可以从全脑层面揭示短视频或个性化推荐内容相关的脑区激活模式，但fMRI时间分辨率较低，难以刻画视频观看过程中毫秒级的快速神经动态。头皮EEG具有较高时间分辨率，但对杏仁核、海马等深部结构的空间定位能力有限；fNIRS主要反映皮层血氧变化，也难以直接覆盖内侧颞叶深部脑区。相比之下，颅内脑电能够直接记录临床植入电极附近脑区的局部场电位和放电单元活动，同时兼具较高时间分辨率和较高空间特异性。因此，iEEG特别适合用于回答本研究关注的问题：短视频观看是否能够在杏仁核—海马系统中诱发可测量的快速电生理变化，以及这些变化是否与情绪效价、主观偏好和自然视频事件加工相关。",
])

replace_section("1.4 问题提出", [
    "基于上述背景，本研究围绕一个核心科学问题展开：短视频观看诱发的情绪、偏好和情境加工，是否能够在杏仁核—海马系统的局部活动和跨区通信中得到体现。为回答这一问题，本研究设置三个相互递进的分析层次。研究一采用标准化情绪图片任务，考察杏仁核和海马是否能够对基本情绪效价表现出频谱活动差异，从而建立相对明确的情绪效价加工参照。研究二采用平台来源的短视频片段，考察主观喜欢程度是否调制杏仁核和海马的局部场电位功率及放电单元活动。研究三进一步使用公开自然视频观看数据集，将分析拓展到更连续的视频观看情境，考察杏仁核—海马之间的功能连接、方向性信息流以及事件相关放电率变化。",
    "因此，研究三并不是因为自采样本量有限而简单加入的“补充”，而是围绕同一科学问题进行的外部数据拓展：如果研究一和研究二提示杏仁核—海马系统参与情绪效价和短视频偏好加工，那么在连续自然视频观看中，这一系统是否同样表现出与事件边界、高唤醒片段和跨区通信相关的电生理特征。",
])

replace_section("1.4.1 标准情绪图片条件下的效价加工", [
    "研究一旨在利用标准化情绪图片范式，考察杏仁核与海马在相对明确的情绪刺激条件下是否能够表现出效价相关的神经活动差异。标准情绪图片具有刺激属性明确、呈现时间固定、情绪类别相对清晰等特点，适合用于建立基本情绪效价加工的参照。研究一并不试图模拟短视频观看，而是用于确认本研究关注的脑区和分析指标是否能够捕捉情绪效价相关的神经反应。",
    "基于既往关于杏仁核情绪加工和颅内脑电的研究，本研究假设：第一，标准情绪图片能够诱发杏仁核和海马的事件相关频谱变化；第二，杏仁核相较海马可能对情绪效价更敏感，尤其在刺激呈现后的中早期时间窗内表现出正性、负性和中性刺激之间的功率差异；第三，若研究一能够观察到效价相关的频段调制，则可为后续解释短视频刺激下更复杂的偏好相关活动提供基线参照。",
])

replace_section("1.4.2 真实短视频刺激条件下的主观偏好加工", [
    "研究二进一步将刺激材料从静态情绪图片扩展为平台来源的短视频片段，旨在考察短视频观看过程中杏仁核与海马是否表现出与主观偏好相关的神经活动。与标准图片相比，短视频包含动态画面、声音、语义、情节和节奏变化，更接近日常媒介使用情境，也更容易诱发个体的喜欢程度和继续观看欲望。",
    "短视频偏好不能简单等同于传统意义上的正性效价。在真实短视频情境中，一个视频即便包含紧张、冲突或负性内容，也可能因为新奇性、悬念或个人相关性而具有较高吸引力；相反，表面上正性的内容也可能因缺乏兴趣而不被喜欢。因此，研究二以被试对短视频的主观评分为行为指标，将短视频划分为相对喜欢和不喜欢的刺激，考察偏好相关神经活动。",
])

replace_section("1.4.3 公开自然视频数据集中的补充性探索", [
    "研究三基于研究一和研究二的结果进一步展开。研究一显示杏仁核能够在标准情绪图片条件下表现出效价相关频谱活动，研究二显示短视频偏好能够同时调制杏仁核和海马活动。由此产生的进一步问题是：在更连续、更自然的视频观看情境中，杏仁核—海马系统是否也表现出与自然视频事件相关的功能连接和方向性通信。",
    "为回答这一问题，研究三使用Keles等人公开自然视频观看数据集，重点分析场景切割和高唤醒片段锁定条件下杏仁核—海马相干性、谱格兰杰因果性和事件相关放电率。该部分属于围绕同一科学问题的拓展性分析，而非简单因为自采样本量有限而加入的补充验证。",
])

replace_section("3.2.4 数据采集与预处理说明", [
    "研究一以图片呈现时刻为事件零点，提取刺激前0.5 s至刺激后2.0 s的LFP epoch，并将正性、中性和负性图片作为实验条件。最终纳入LFP时频分析的被试为【待填：被试编号】，共包含杏仁核通道【待填】个、海马通道【待填】个；质量控制后保留正性图片epoch【待填】个、中性图片epoch【待填】个、负性图片epoch【待填】个。",
    "通过质量控制后的试次和电极进入时频分析；未覆盖杏仁核或海马、或在质量控制中被判定为异常的通道和试次不纳入后续统计。上述纳入数量建议在表3.1中按被试和脑区列出。",
])

replace_section("3.4 小结", [
    "研究一提示，标准情绪图片能够在杏仁核中诱发明确的效价相关频谱调制。具体而言，杏仁核在正性与负性图片比较中出现两个cluster校正后的显著时频簇：主簇位于刺激后450-800 ms、5.8-20.2 Hz，另一个低频晚期簇位于1650-1950 ms、2.0-4.1 Hz。海马虽然存在局部未校正显著点，但cluster校正后未形成稳定显著簇。",
    "这一结果为后续研究提供两个参照：其一，杏仁核电极信号能够捕捉基本情绪效价加工；其二，若在短视频任务中观察到海马参与增强，则可能反映短视频相较静态图片引入了更强的情境、记忆和连续事件加工需求。",
])

replace_section("4.2.2 刺激材料", [
    "研究二使用的短视频材料来自自建视频库，视频来源于抖音新注册用户界面的随机推荐内容。为控制实验时长、降低临床被试任务负担，并保证不同试次之间的刺激长度可比，本研究统一截取每段短视频开头5 s作为实验刺激。选择开头5 s的原因在于，短视频平台通常需要在视频开端快速呈现主要内容或吸引注意的信息；同时，固定5 s窗口有利于将LFP和spike信号对齐到统一事件时间窗，避免不同视频时长造成分析窗口不一致。",
    "所有视频在纳入实验前经过人工筛选，排除暴力、血腥、强闪烁或可能诱发明显不适及痫性风险的内容。研究二共使用66段短视频片段。",
])

replace_section("4.2.4 LFP与spike预处理说明", [
    "研究二的LFP预处理与统一流程一致，以视频呈现时刻为事件零点提取epoch。研究二以被试自己的喜欢评分作为偏好条件划分依据：喜欢评分为4-5分的试次定义为喜欢条件，评分为1-2分的试次定义为不喜欢条件，评分为3分的试次作为中性或模糊偏好试次，不纳入喜欢/不喜欢二分类比较。",
    "采用被试内评分而非视频类别划分条件，是因为短视频偏好具有较强主观性，同一视频对不同被试可能具有不同吸引力。spike数据的时间戳与视频事件对齐，随后计算事件锁定放电率，具体参数见本节数据分析部分。",
])

replace_section("4.3.3 放电单元活动结果", [
    "研究二的spike分析仅纳入完成spike sorting并通过质量控制的放电单元。最终共有2名被试进入spike分析，原因是仅这两名被试具有可用于研究二事件锁定分析的微电极放电单元，且其单元波形和放电质量满足质量控制标准。共提取45个可分析放电单元，其中杏仁核单元【待填】个，海马单元【待填】个，分别来自【待填：电极/通道名称】。瞬时放电率（instantaneous firing rate, IFR）采用高斯核平滑估计，并以视频呈现为事件零点，比较喜欢和不喜欢条件下事件后放电率变化。",
    "以喜欢评分4-5分、不喜欢评分1-2分为事件条件，K-means聚类得到两个响应模式簇：cluster 0包含22个单元，cluster 1包含23个单元。cluster 1在事件后0.20-0.70 s和1.25-1.65 s出现喜欢与不喜欢条件之间的差异，表现为喜欢条件下基线校正IFR更低，而不喜欢条件下IFR相对更高。该结果提示，短视频偏好相关放电活动并不表现为喜欢条件下整体放电增强；相反，部分单元对不喜欢或高显著性内容表现出更强的事件后反应。",
    "进一步分析喜欢/不喜欢条件下IFR时间曲线之间的耦合强度和响应动态发现，杏仁核和海马的脑区内耦合以及杏仁核—海马脑区间耦合整体均接近零，提示两个脑区在该任务中未观察到明显放电同步。具体而言，脑区内耦合在喜欢条件下的平均相关约为0.008，在不喜欢条件下约为-0.005；脑区间耦合在喜欢条件下约为0.006，在不喜欢条件下约为0.004。在响应动态上，杏仁核不喜欢条件的IFR响应斜率更高，约为0.267 Hz/s，而喜欢条件约为0.102 Hz/s；海马中不喜欢条件也呈正斜率，约为0.137 Hz/s，而喜欢条件略为负斜率，约为-0.023 Hz/s。",
])

replace_section("5.1 研究目的与假设", [
    "研究三基于研究一和研究二的结果进一步展开。研究一显示杏仁核能够在标准情绪图片条件下表现出效价相关频谱活动，研究二显示短视频偏好能够同时调制杏仁核和海马活动。由此产生的进一步问题是：在更连续、更自然的视频观看情境中，杏仁核—海马系统是否也表现出与自然视频事件相关的功能连接和方向性通信。",
    "因此，研究三使用Keles等人公开自然视频观看数据集，将研究一和研究二中关注的杏仁核—海马活动拓展到连续自然视频观看情境。研究三主要回答三个问题：第一，自然视频观看过程中杏仁核和海马之间的低频功能连接是否强于高频连接；第二，视频观看时杏仁核和海马之间是否存在稳定的方向性信息流；第三，在自然事件边界或高唤醒片段锁定条件下，杏仁核和海马是否表现出事件相关放电率调制。",
])

replace_section("5.2.1 数据集", [
    "研究三使用Keles等人构建的公开自然视频观看数据集（Keles et al., 2024）。该数据集包含人类患者在观看自然电影片段时的多模态神经记录数据，包括单单位放电、颅内脑电和功能磁共振等信息。原始神经记录数据、视频观看任务和部分基础事件信息由原作者公开提供。本研究在此基础上进行了本地再分析，包括筛选覆盖杏仁核和海马的NWB run、提取目标脑区通道、进行质量控制、构建场景切割和高唤醒事件锁定epoch，并计算组水平相干性、谱格兰杰因果性和事件相关放电率。",
    "根据本地分析结果，本研究共识别16名被试的29个真实NWB run，其中27个run通过质量控制并进入组水平full-spectrum分析，2个run因无可用clean trial被排除。若原数据集中未提供完整年龄、性别或临床信息，则在被试信息表中标注为“原数据未提供”。相较自采短视频任务，该数据集具有更大的样本规模和更自然的连续观看结构，适合用于拓展分析杏仁核—海马系统在自然视频加工中的活动规律。",
])

replace_section("5.2.3 功能连接和方向性分析", [
    "研究三在杏仁核和海马电极之间计算不同频段的功能连接强度，并进一步使用谱格兰杰因果分析（spectral Granger causality, sGC）估计两个脑区之间的方向性信息流（Granger, 1969; Ding et al., 2000; Barnett & Seth, 2014）。分析重点包括低频与高频连接强度的比较，以及海马到杏仁核和杏仁核到海马两个方向的信息流差异。",
    "纳入功能连接和方向性分析的通道数量按run统计。每个run需同时具有可用的杏仁核通道和海马通道，且事件锁定后保留足够数量的clean trial。最终纳入的杏仁核通道数为【待填】，海马通道数为【待填】；各run通道数量和clean trial数量建议在表5.1中列出。",
    "谱格兰杰因果性采用state-space spectral Granger causality框架计算，该方法可在频域中估计seed信号集合到target信号集合的方向性预测信息（Barnett & Seth, 2015）。具体实现使用MNE-Connectivity中的mne_connectivity.spectral_connectivity_epochs函数，本文使用的MNE-Connectivity版本为【待填版本号】。该工具包为MNE-Python生态中的功能连接分析模块，可用于计算频域相干性、相位同步和谱格兰杰因果性等指标。项目网址：https://mne.tools/mne-connectivity/。",
])

replace_section("5.2.5 基于VLM的高唤醒片段标注", [
    "为补充官方场景切割事件标记，本研究进一步采用本地视觉语言模型Qwen/Qwen2.5-VL-3B-Instruct对自然视频中的高唤醒片段进行探索性自动标注。该分析并不将模型输出视为人工验证的情绪标签，而是用于生成一个可复现的候选高唤醒事件集合，以便后续进行事件锁定的功能连接和方向性分析。完整模型提示词见附录二。",
    "具体而言，本研究将输入视频按2.0 s窗口、1.0 s步长进行滑动切分，因此相邻窗口之间存在1.0 s重叠。输入视频总时长为478.88 s，帧率为25 fps，分辨率为640 × 480，共得到477个候选窗口。每个2 s窗口内按时间均匀抽取4帧作为视觉输入，例如分别覆盖窗口起点、约1/3处、约2/3处和终点附近的画面，而不是抽取连续相邻4帧。模型被要求只评价唤醒强度，即该片段是否可能诱发紧张、惊吓、冲突期待或快速情绪升级，而不评价正性或负性效价。",
    "模型输出包括arousal_score、confidence和reason_tags等字段。随后结合音频显著性特征计算综合评分：final_score = 0.7 × arousal_score + 0.2 × confidence + 0.1 × normalized_audio_salience。其中，arousal_score表示模型对视觉内容唤醒强度的评分，confidence表示模型对该判断的置信度，normalized_audio_salience表示基于音频能量和频谱变化计算的标准化音频显著性。",
    "最终采用高置信优先策略筛选候选片段，窗口需同时满足z_final_score ≥ 1.5、arousal_score ≥ 70、confidence ≥ 60。由于相邻滑动窗口之间存在重叠，时间上重叠或相邻的命中窗口被合并为同一候选簇，并在每个簇内保留综合评分最高的窗口作为最终高唤醒片段。",
])

replace_section("5.3.1 功能连接结果", [
    "场景切割事件锁定的full-spectrum分析显示，杏仁核—海马相干性主要集中在低频范围。组平均相干性在3.9-43.0 Hz范围内约为0.34-0.49，低频段相干性整体高于高频段。该结果提示，在自然视频观看过程中，杏仁核和海马之间的信息整合可能更多依赖低频振荡。",
    "统计展示上，本文将组平均相干性热图和频率曲线合并为图5.2A。图中颜色表示相干性强度，曲线表示跨run平均值，阴影表示均值±SEM。",
])

replace_section("5.3.2 方向性信息流结果", [
    "谱格兰杰因果分析显示，在场景切割锁定的全频谱结果中，海马到杏仁核（H→A）方向的信息流总体高于杏仁核到海马（A→H）方向。组水平平均sGC中，H→A方向为0.584，A→H方向为0.535，平均方向差为0.049。A→H与H→A的配对比较经FDR校正后仍存在显著频点，共21个频率点达到q<0.05，主要分布于9.6-13.2 Hz、17.6-20.0 Hz和43.6-44.8 Hz三个频段。",
    "结合事件相关放电率的时滞分析，多数试次中海马活动领先杏仁核，提示自然视频场景切割附近可能存在以海马到杏仁核方向为主的信息传递趋势。需要注意的是，该方向性关系具有频段特异性，并不意味着所有频率或所有视频事件中均表现为稳定的H→A优势。高唤醒片段分析中的唤醒度评分用于筛选事件集合，并以这些事件为时间锁定点重新进行相干性和sGC分析。",
])

replace_section("5.3.3 事件相关放电率结果", [
    "在Keles公开自然视频数据集中，以场景切割事件为时间锁定点进行spike分析时，杏仁核和海马均显示出事件相关放电率调制。A-H时滞分析的方法如下：首先分别提取杏仁核和海马放电单元在事件前后窗口内的IFR时间曲线；随后在预设响应窗内计算各脑区响应峰值或主要响应变化出现的时间；最后比较两个脑区响应时间的先后关系，以判断单个试次或单元组合中海马领先、杏仁核领先或无明确领先关系。",
    "结果显示，多数试次中海马活动领先杏仁核，但部分试次中也存在杏仁核领先的情况，其中杏仁核中位领先约300 ms，提示该方向性关系存在试次间异质性。后续版本将进一步补充海马领先、杏仁核领先和无明确领先试次的数量和比例。",
    "基于单元IFR时间曲线的聚类分析进一步显示，放电单元可分为两类响应模式：一类为事件后放电率下降的抑制型单元，共899个；另一类为事件后放电率升高的激活型单元，共503个。两类时间曲线在事件发生后迅速分离，并在0-2 s响应窗内保持相反的放电率变化方向，提示自然视频事件并非诱发单一方向的平均放电变化，而是同时包含抑制型和激活型放电单元群。",
    "建议进一步补充两类单元在杏仁核和海马中的分布，例如：抑制型单元中杏仁核【待填】个、海马【待填】个；激活型单元中杏仁核【待填】个、海马【待填】个。若数据允许，可进一步计算单元响应强度与VLM唤醒评分之间的相关，作为探索性分析。图中阴影统一表示均值±SEM；若使用95%置信区间，则需在图注中另行说明。",
])

replace_section("5.3.4 高唤醒事件探索结果", [
    "在高唤醒事件标记的探索性分析中，Qwen/Qwen2.5-VL-3B-Instruct对视频进行2 s窗口、1 s步长扫描，共得到477个候选窗口，并最终筛选出19个高唤醒片段。所选片段与官方场景切割事件的±2 s命中率为68.4%，随机基线为55.2%，富集倍数约为1.24；5000次置换检验显示该邻近关系未达到显著水平（p=0.174）。因此，该结果只能说明AI高唤醒片段与场景切割存在数值上的邻近趋势，不能将其解释为经过人工验证的情绪事件标签。",
    "高唤醒片段标注结果汇总如下：输入视频时长478.88 s；候选窗口长度2.0 s；滑动步长1.0 s；候选窗口总数477；每窗口抽帧数4；最终高唤醒片段数19；parse或inference失败数0；±2 s场景切割命中率68.4%；随机基线55.2%；置换次数5000；置换检验p值0.174。",
    "基于这些高唤醒事件重新进行full-spectrum sGC分析时，共有27个run进入组水平分析，2个run因QC失败被排除。QC标准包括：该run中必须存在可用杏仁核和海马通道，事件锁定后保留足够数量的clean trial，且数据无明显伪迹或缺失。高唤醒事件锁定结果显示，平均相干性为0.380，H→A平均sGC为1.501，A→H平均sGC为1.438，方向差数值上仍表现为H→A更强。",
    "进一步将方向性sGC分解到θ频段（4-8 Hz）和β频段（13-30 Hz）后发现，θ频段中A→H与H→A方向的组水平差异较小，A→H平均值为319.139，H→A平均值为326.074，配对t检验经FDR校正后未达到显著。β频段则表现出A→H方向优势，A→H平均值为712.473，H→A平均值为282.589，配对t检验经FDR校正后仍显著。图中p值表示同一频段内A→H与H→A两个方向之间的配对比较，误差线表示SEM，星号表示FDR校正后显著。",
])

replace_section("5.4 小结", [
    "研究三基于公开自然视频数据集，围绕杏仁核—海马系统在连续视频事件加工中的功能连接、方向性信息流和放电率变化进行了拓展性分析。结果显示，自然视频观看中杏仁核和海马之间低频连接更强，场景切割锁定的全频谱sGC结果中H→A方向数值上更高；同时，高唤醒片段的分频段分析显示β频段A→H方向优势。事件锁定spike分析进一步提示自然视频事件能够诱发杏仁核和海马的放电率调制。",
    "整体而言，研究三支持杏仁核—海马系统参与自然视频事件加工，但这一跨区通信并非固定单向模式，而可能随视频事件类型、唤醒水平和振荡频段发生变化。",
])

doc.save(OUT)

lines = []
for p in doc.paragraphs:
    text = p.text.strip()
    if not text:
        continue
    style = p.style.name if p.style else ""
    if style.startswith("Heading") or style == "附录标识":
        lines.append(f"\\n## {text}\\n")
    else:
        lines.append(text)
MD_OUT.write_text("\\n\\n".join(lines), encoding="utf-8")

print(OUT)
print(MD_OUT)
