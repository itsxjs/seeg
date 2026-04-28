#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph


COMMENT_MARKERS = {
    "短视频偏好加工的探索性颅内电生理证据": (
        "已将论文主线从过度使用/成瘾机制收回到短视频偏好加工。若后续要重新讨论过度使用风险，"
        "建议补充问题性短视频使用量表、持续观看行为或高低风险组数据。"
    ),
    "研究三作为公开自然视频数据的补充性探索": (
        "研究三的刺激、任务、行为指标和统计对象均不同于研究一/二，因此改为补充性探索，不再表述为验证。"
    ),
    "本研究仅将其作为探索性自动标注结果": (
        "AI高唤醒标注缺少人工复核和一致性评估，且与随机基线比较未达显著，不能作为强证据。"
    ),
    "该结果应理解为探索性、描述性的发现": (
        "n=3 的 LFP 分析不宜作稳定组水平推断；建议后续补充每名被试效应图、cluster-level p值和统计单位说明。"
    ),
    "聚类结果后的条件差异检验存在潜在循环分析风险": (
        "如果聚类特征包含条件差异，再在同一数据上检验like/dislike可能放大显著性。建议后续用独立时间窗或交叉验证。"
    ),
    "需要谨慎解释不同尺度下的 sGC 数值": (
        "场景切割、高唤醒全频和分频段sGC数值尺度不同。若分别为均值、积分值或其他统计量，需在方法中明确。"
    ),
}


NEW_REFERENCES = [
    "Bai, S., Chen, K., Liu, X., Wang, J., Ge, W., Song, S., Dang, K., Wang, P., Wang, S., Tang, J., Zhong, H., Zhu, Y., Yang, M., Li, Z., Wan, J., Wang, P., Ding, W., Fu, Z., Xu, Y., Ye, J., Zhang, X., Xie, T., Cheng, Z., Zhang, H., Yang, Z., Xu, H., & Lin, J. (2025). Qwen2.5-VL technical report. arXiv. https://doi.org/10.48550/arXiv.2502.13923",
    "Baldassano, C., Chen, J., Zadbood, A., Pillow, J. W., Hasson, U., & Norman, K. A. (2017). Discovering event structure in continuous narrative perception and memory. Neuron, 95(3), 709-721.e5. https://doi.org/10.1016/j.neuron.2017.06.041",
    "Barnett, L., & Seth, A. K. (2014). The MVGC multivariate Granger causality toolbox: A new approach to Granger-causal inference. Journal of Neuroscience Methods, 223, 50-68. https://doi.org/10.1016/j.jneumeth.2013.10.018",
    "Ding, M., Bressler, S. L., Yang, W., & Liang, H. (2000). Short-window spectral analysis of cortical event-related potentials by adaptive multivariate autoregressive modeling: Data preprocessing, model validation, and variability assessment. Biological Cybernetics, 83(1), 35-45. https://doi.org/10.1007/s004229900137",
    "Granger, C. W. J. (1969). Investigating causal relations by econometric models and cross-spectral methods. Econometrica, 37(3), 424-438. https://doi.org/10.2307/1912791",
    "Lang, P. J., Bradley, M. M., & Cuthbert, B. N. (2008). International affective picture system (IAPS): Affective ratings of pictures and instruction manual. Technical Report A-8. University of Florida.",
    "Magnotti, J. F., Wang, Z., & Beauchamp, M. S. (2020). RAVE: Comprehensive open-source software for reproducible analysis and visualization of intracranial EEG data. NeuroImage, 223, 117341. https://doi.org/10.1016/j.neuroimage.2020.117341",
    "Maris, E., & Oostenveld, R. (2007). Nonparametric statistical testing of EEG- and MEG-data. Journal of Neuroscience Methods, 164(1), 177-190. https://doi.org/10.1016/j.jneumeth.2007.03.024",
    "Oostenveld, R., Fries, P., Maris, E., & Schoffelen, J. M. (2011). FieldTrip: Open source software for advanced analysis of MEG, EEG, and invasive electrophysiological data. Computational Intelligence and Neuroscience, 2011, 156869. https://doi.org/10.1155/2011/156869",
    "Tallon-Baudry, C., & Bertrand, O. (1999). Oscillatory gamma activity in humans and its role in object representation. Trends in Cognitive Sciences, 3(4), 151-162. https://doi.org/10.1016/S1364-6613(99)01299-1",
    "Zacks, J. M., Speer, N. K., Swallow, K. M., Braver, T. S., & Reynolds, J. R. (2007). Event perception: A mind-brain perspective. Psychological Bulletin, 133(2), 273-293. https://doi.org/10.1037/0033-2909.133.2.273",
]


REPLACEMENTS = {
    "摘要": {
        30: "短视频平台以连续、多模态、高奖赏密度和即时反馈为主要特征，已经成为现代日常生活中重要的媒介形式。真实短视频观看通常同时包含情绪显著性评估、主观偏好形成、奖赏价值加工、情境记忆整合以及跨脑区信息传递。既往关于短视频及问题性媒介使用的研究多集中于问卷、行为表现或功能影像层面，对于真实短视频片段观看过程中人类边缘系统如何以毫秒级时间尺度编码情绪和偏好信息仍缺乏直接证据。杏仁核和海马分别在情绪显著性、奖赏价值、情境记忆和事件结构加工中具有重要作用，因此本研究聚焦杏仁核-海马系统在短视频偏好加工中的颅内电生理活动。",
        31: "本研究拟回答三个核心问题：第一，在标准化情绪图片条件下，杏仁核和海马是否能够表现出效价相关的频谱活动；第二，在真实短视频观看条件下，主观喜欢程度是否能够调制杏仁核和海马的局部场电位功率及放电单元活动；第三，在公开自然视频观看数据集中，杏仁核和海马之间是否存在与自然事件边界或高唤醒片段相关的功能连接和方向性信息流。需要强调的是，本研究未直接测量短视频过度使用、成瘾倾向或持续刷屏行为，因此结果主要用于理解短视频偏好加工，并为后续过度使用风险研究提供初步线索。",
        32: "研究一采用标准情绪图片和效价判断任务，纳入自采颅内脑电被试中可用于LFP分析的3名被试和可用于放电单元分析的2名被试，以图片呈现为事件零点分析2-100 Hz时频功率。研究二采用66段真实短视频片段和1-5分主观偏好评分任务，同样基于LFP分析被试和放电单元分析被试，探索喜欢与不喜欢条件下杏仁核和海马的频谱活动及事件锁定放电率。研究三基于Keles等人的公开自然视频观看数据集，作为外部自然连续刺激情境下的补充性探索，进一步计算杏仁核-海马相干性、谱格兰杰因果性以及事件相关放电率。",
        33: "结果显示，研究一中杏仁核在效价比较中出现cluster校正后的时频簇，主要位于刺激后450-800 ms、5.8-20.2 Hz及1650-1950 ms、2.0-4.1 Hz；海马在cluster校正后未形成稳定显著簇。研究二中，喜欢/不喜欢比较在杏仁核中出现450-1100 ms、4.9-24.2 Hz的偏好相关时频簇，海马中出现700-1200 ms、2.0-28.9 Hz的偏好相关时频簇。由于自采LFP分析仅包含3名被试，这些结果应被理解为探索性发现，重点在于效应方向和时间-频率分布，而非显著频点数量本身。",
        34: "研究三中，场景切割事件锁定分析显示杏仁核-海马组平均相干性在3.9-43.0 Hz范围内约为0.34-0.49；谱格兰杰因果分析显示H→A方向平均值为0.584，A→H方向平均值为0.535，平均方向差为0.049，FDR校正后显著频点主要分布在9.6-13.2 Hz、17.6-20.0 Hz和43.6-44.8 Hz。探索性高唤醒标注中，视觉语言模型扫描477个2 s候选窗口并筛选出19个高唤醒片段，其与官方场景切割的2 s命中率为68.4%，随机基线为55.2%，置换检验p=0.174，未达到显著水平。因此，该结果只能说明AI标注与镜头切换之间存在数值趋势，尚不能作为标注有效性的强证据。",
        35: "综上，本研究提示，短视频片段观看中的情绪与偏好加工不能简单等同于传统正负效价判断，而可能与杏仁核-海马系统在局部频谱活动、放电单元活动和跨区方向性通信上的变化有关。标准情绪图片主要揭示杏仁核的效价敏感性，真实短视频进一步提示海马可能参与主观偏好和情境整合，自然视频数据则提供了连续刺激情境下的相关证据。这些发现为理解短视频偏好加工提供了初步颅内电生理证据，并可作为后续短视频过度使用风险研究的基础线索。",
    },
    "Abstract": {
        39: "Short-form videos are continuous, multimodal, reward-dense, and feedback-rich media stimuli that have become deeply embedded in everyday life. Viewing real short-form clips may involve affective salience evaluation, subjective preference formation, reward-value processing, contextual memory integration, and cross-regional information transfer. Existing research on short-form video use and problematic media use has largely relied on questionnaires, behavior, or functional imaging, whereas direct millisecond-scale evidence from human limbic electrophysiology remains limited.",
        40: "This thesis examined amygdala-hippocampal intracranial electrophysiological activity across stimulus contexts with increasing ecological validity. Study 1 tested whether standardized emotional pictures evoke valence-related spectral activity. Study 2 tested whether subjective preference for real short-form video clips modulates local field potentials and firing-unit activity. Study 3 used a public natural movie dataset as a supplementary exploratory analysis of continuous natural viewing. The present data did not directly measure problematic short-form video use, addiction tendency, persistent scrolling, or difficulty interrupting viewing; therefore, the findings should be interpreted as exploratory evidence for short-form video preference processing rather than direct evidence for overuse mechanisms.",
        41: "In Studies 1 and 2, the self-collected intracranial dataset included 3 participants for LFP analyses and 2 participants for firing-unit analyses. Study 2 used 66 real short-form video clips and 1-5 preference ratings. Study 3 identified 16 participants and 29 real NWB runs in the Keles public dataset, of which 27 runs passed quality control for group-level analyses.",
        42: "In Study 3, scene-cut-locked analyses showed group-average amygdala-hippocampal coherence of approximately 0.34-0.49 from 3.9 to 43.0 Hz. Spectral Granger causality was numerically stronger from hippocampus to amygdala than from amygdala to hippocampus in the full-spectrum scene-cut analysis, whereas exploratory high-arousal analyses showed frequency-dependent differences and a beta-band A→H advantage. AI-defined high-arousal windows showed a non-significant numerical enrichment relative to official scene cuts (68.4% vs. 55.2%, permutation p=0.174).",
        43: "Overall, the findings suggest that emotional and preference-related processing during short-form video viewing cannot be reduced to traditional positive-negative valence judgments. Instead, short-form video preference processing may involve coordinated but frequency-specific activity of the amygdala-hippocampal system. Given the small self-collected sample and exploratory external analyses, these findings provide preliminary intracranial electrophysiological evidence for short-form video preference processing and should be tested in future studies with direct measures of problematic use and continued-viewing behavior.",
    },
    "正文": {
        113: "《中国网络视听发展研究报告（2024）》进一步指出，2023年我国短视频用户平均每天的使用时长约为151分钟，短视频应用在网民上网总时长中占比持续提高，已成为一种高时间占用的媒介形式（中国网络视听协会，2024）。在具体平台层面，抖音、快手系应用占据了绝大部分市场份额，用户渗透率高达95.3%左右（中国网络视听协会，2024）。以抖音为例，QuestMobile（2024）的数据显示，截至2024年6月，中国约有7.8亿抖音月活跃用户，月人均使用时长达38.3小时。",
        114: "这些数据表明，短视频已从一种新兴的娱乐形式，演变为深度嵌入日常生活的媒介情境。对大量用户而言，打开短视频应用、以“刷”的方式连续观看数十分钟乃至数小时，已经成为一种日常化行为模式。在这样的社会背景下，采用短视频作为实验情境中的情绪与奖赏刺激材料，具有较高生态效度和现实意义：研究者能够在更接近真实媒介使用的条件下，考察大脑如何处理短视频片段中的情绪、偏好和情境信息。",
        115: "1.2 短视频过度使用的风险及相关研究背景",
        118: "从神经机制角度出发，已有理论和邻近领域证据提示，频繁暴露于高强度情绪、奖赏线索的媒介内容可能与奖赏和动机相关脑区的反复参与有关；随着使用经验增加，个体可能形成更稳定的线索-奖赏联结（Hyman et al., 2006）。不过，本研究并未直接测量短视频过度使用、成瘾倾向、算法推荐反馈或刷屏中断困难，因此不能将颅内脑电结果直接推广为成瘾或问题性使用解释。更谨慎的定位是：通过研究真实短视频片段观看时的偏好相关神经活动，为理解后续问题性短视频使用研究提供基础线索。",
        119: "因此，本研究关注的核心问题并不是临床意义上的短视频成瘾或过度使用，而是在真实短视频片段观看中，杏仁核—海马系统如何参与情绪显著性、主观偏好和情境信息加工。该问题可为后续纳入问题性使用量表、持续观看行为、算法推荐反馈或高低风险组比较的研究提供初步电生理依据。",
        124: "因此，在短视频这一高生态效度、连续且情绪与奖赏线索交织的情境中，将“杏仁核—海马情绪奖赏加工网络”与“频段特异的振荡通信机制”结合起来进行考察，具有理论与方法学意义。一方面，这一视角有助于描述大脑如何在短视频片段中对情绪显著性、主观偏好和情境线索进行快速编码；另一方面，也能够探索情绪价值如何与情境记忆和观看经验相结合，并在神经活动层面表现为可测量的功率变化和跨区同步。基于上述研究脉络，本研究以颅内脑电为手段，重点关注短视频观看过程中杏仁核与海马在不同频段上的探索性变化。",
        126: "尽管短视频使用及其潜在影响已经受到广泛关注，但目前关于真实短视频观看中快速神经加工过程的研究仍较为有限。已有研究多从问卷、行为测量或功能影像角度探讨短视频过度使用与心理健康、注意控制、自我控制等变量之间的关系，而对短视频观看过程中情绪与偏好信息如何被大脑快速加工的理解仍不充分。短视频作为一种动态、多模态、连续变化的自然刺激，既不同于传统情绪研究中常用的静态图片或情绪面孔，也不同于单一奖赏反馈任务；其加工过程往往同时涉及情绪显著性、主观偏好、情境记忆和奖赏价值等多个成分。",
        127: "从研究方法上看，标准情绪图片范式具有较强的实验控制性，适合用于考察杏仁核、海马等边缘系统对基本情绪效价的反应，但其生态效度有限，难以充分模拟真实短视频观看中的连续信息加工过程。相较之下，真实短视频片段更接近日常媒介使用情境，能够诱发个体的主观偏好和继续观看相关评价。然而，由于颅内脑电数据采集难度较高，单一实验样本有限，本研究进一步借助公开自然视频观看数据集，作为自然连续刺激情境下的补充性探索，而非对自采实验的严格验证。",
        128: "基于上述不足，本研究利用颅内脑电技术，围绕杏仁核—海马系统在短视频片段观看中的情绪与偏好加工展开研究。研究一采用标准情绪图片和效价判断任务，建立相对可控的情绪加工参考范式；研究二采用真实短视频片段，并在固定时间窗内采集主观偏好评分，考察短视频刺激下偏好相关的神经活动模式；研究三进一步使用公开自然视频观看数据集，提供连续自然刺激情境下的相关证据。三个研究共同服务于一个核心问题：杏仁核—海马系统如何在不同生态效度的刺激情境中对情绪效价、主观偏好和自然视频信息进行加工。",
        137: "1.4.3 公开自然视频数据集中的补充性探索",
        138: "研究三旨在回答：前两个研究关注的杏仁核—海马活动特征，是否也能在更大规模、更自然的连续视频观看数据中观察到相关证据？由于颅内脑电研究通常受临床电极植入位置和样本量限制，单一实验结果需要在独立数据来源中谨慎比较。Keles等人构建的公开自然视频观看数据集包含多模态神经记录数据，为研究自然视频观看中的脑活动提供了重要资源。基于该数据集，本研究将进一步考察杏仁核、海马及相关边缘结构在连续视频观看过程中的神经活动模式，并探索其与自采实验结果的可能联系。",
        151: "LFP预处理在EEGLAB、自编分析脚本及相关开源工具思想的基础上完成（Oostenveld et al., 2011; Magnotti et al., 2020）。连续信号首先重采样至1000 Hz，随后进行1-200 Hz带通滤波，并使用49-51 Hz陷波滤波去除工频噪声。滤波后数据采用全通道平均重参考。需要说明的是，在sEEG/iEEG研究中，重参考方式可能影响跨脑区连接估计；更常见的替代方案包括双极参考或电极束内平均参考。本研究保留当前流程，但在解释功能连接和方向性结果时采取谨慎态度。",
        158: "伪迹剔除采用自动检测与条件内稳健统计相结合的策略。首先检测平直通道、异常通道、线噪声和爆发性伪迹，主要参数见下列公式化设置。随后在每个epoch内计算基线窗与响应窗的RMS比值及响应窗峰-峰值，并在条件内使用MAD估计robust z-score；当同一试次中至少5个通道被稳健规则标记时剔除该试次。由于不同被试通道数量不同，固定通道数阈值并不完全等价，后续研究应进一步报告每名被试的通道总数、剔除比例，并考虑使用比例阈值进行敏感性分析。",
        167: "此外，本研究在全epoch范围内检测绝对振幅异常和峰-峰值异常。若任一点绝对振幅达到或超过200 μV，则该通道-试次被标记；同时在条件内计算全窗峰-峰值的均值和标准差，并以三倍标准差作为阈值。当同一试次中至少3个通道被该阈值规则标记时剔除该试次。最终剔除集合为稳健规则和阈值规则的并集。由于条件内计算阈值可能使不同条件采用略有差异的剔除标准，相关结果应被理解为探索性发现。",
        177: "spike分析针对放电单元检测和质量控制进行。原始高频数据首先转换为可用于离线分选的格式，使用Kilosort进行自动spike sorting，并在Phy中对放电单元进行人工检查、合并和剔除，以减少噪声单元、多单元混合和明显伪迹对结果的影响。由于本文未系统报告isolation distance、L-ratio、ISI violation、amplitude cutoff等严格单单元质量指标，后文统一使用“放电单元”表述。",
        187: "实验材料选自国际情绪图片系统（International Affective Picture System, IAPS）（Lang et al., 2008），包括正性、负性和中性三类图片。每类图片40张，共120张。标准图片库具有明确的效价标定和较好的实验可控性，适合用于考察边缘系统对基本情绪效价的反应。",
        196: "3.2.5 时频分析",
        197: "时频功率使用复Morlet小波进行估计（Tallon-Baudry & Bertrand, 1999），核心推导如下：",
        207: "行为结果显示，大部分被试能够完成情绪图片效价判断任务，但不同被试之间的反应时和正确率存在一定差异，如图3.2。这可能与颅内脑电被试的临床背景、认知状态以及对图片情绪内容的主观理解差异有关。Sub002的正确率未显著高于随机水平，故舍去。",
        212: "具体而言，研究一采用3名被试的时频数据，并使用1000次置换的cluster-based permutation test进行多重比较校正（Maris & Oostenveld, 2007）。杏仁核在效价条件下形成两个cluster校正后的时频簇：主簇位于刺激后450-800 ms、5.8-20.2 Hz，另一个低频晚期簇位于1650-1950 ms、2.0-4.1 Hz。海马虽然存在未校正p值较低的局部点，但cluster校正后未出现显著簇。考虑到LFP分析仅纳入3名被试，该结果应理解为探索性、描述性的发现，重点在于效应方向和被试内一致性，而非显著时频bin数量本身。",
        224: "研究一提示，标准情绪图片能够在杏仁核中诱发效价相关的频段特异性活动，而海马在该任务中的效价调制相对不明显。这一结果为后续研究提供两个参照：其一，杏仁核电极信号能够捕捉基本情绪效价加工；其二，若在真实短视频任务中观察到海马参与增强，则可能反映短视频相较静态图片引入了更强的情境、记忆和连续事件加工需求。鉴于样本量有限，研究一结果应定位为探索性发现。",
        229: "研究二假设：第一，真实短视频能够在杏仁核和海马中诱发与主观偏好相关的功率变化；第二，杏仁核可能主要反映短视频内容的情绪显著性和价值评价，海马则可能更多参与视频情节、情境和观看经验的整合；第三，若放电单元活动在喜欢和不喜欢条件下存在差异，则说明短视频偏好不仅可能体现在群体场电位层面，也可能体现在局部放电活动水平。",
        232: "研究二使用与研究一相同来源的颅内脑电被试。纳入标准为被试完成短视频观看任务，且目标脑区存在可分析的杏仁核或海马电极。LFP时频分析纳入3名被试；对于放电单元分析，仅纳入完成spike sorting并通过质量控制的放电单元，spike分析纳入2名被试。由于统计单位可能涉及被试、电极、通道、试次和放电单元等多个层级，本文结果解释以被试数量为主要限制，并避免将通道或单元数量等同于独立被试样本量。",
        236: "研究二采用固定观看范式。每个试次开始时，屏幕呈现指导语或注视点，注视点持续1-3 s。随后播放一段真实短视频片段，视频呈现时间为5 s。视频播放结束后，被试依次完成两个主观评分：首先评价对该视频的喜欢程度，随后评价继续观看该视频的渴望程度。两个评分均采用1-5分量表，被试通过按键完成作答。实际数据中，喜欢程度与继续观看渴望两项评分高度一致，二者提供的信息几乎完全重叠，因此后续主分析以喜欢评分作为偏好条件划分指标；继续观看渴望不作为独立神经预测变量。",
        241: "研究二的LFP预处理与第2节所述统一流程一致，以视频呈现时刻为事件零点提取epoch，并根据主观评分划分喜欢、不喜欢和中性条件。spike数据的时间戳与视频事件对齐，随后计算事件锁定放电率，具体参数见第2.4节。",
        243: "研究二首先根据被试的主观喜欢评分，将短视频划分为相对喜欢和不喜欢条件。由于喜欢评分与继续观看渴望评分高度一致，本研究未将二者同时纳入模型，以避免重复解释同一行为维度。随后分别在杏仁核和海马中计算视频呈现后0-1500 ms内2-100 Hz频段的时频功率变化，并比较喜欢和不喜欢条件下的差异。对于spike数据，本研究计算事件锁定的IFR时间曲线，比较喜欢和不喜欢视频在事件后放电率变化、响应斜率和脑区内外耦合程度上的差异。",
        258: "具体而言，研究二同样基于3名被试的时频数据进行1000次置换的cluster校正。杏仁核在喜欢/不喜欢比较中出现450-1100 ms、4.9-24.2 Hz的cluster校正时频簇；海马出现700-1200 ms、2.0-28.9 Hz的cluster校正时频簇。这些结果提示，真实短视频偏好可能同时调制杏仁核和海马活动。考虑到样本量有限，该结果应避免被解释为稳定组水平效应，而应作为后续扩大样本和补充行为维度后的探索性线索。",
        260: "与研究一相比，研究二的结果提示，海马在真实短视频条件下表现出更明显的偏好相关活动。这一差异支持本研究的设想：真实短视频不仅是情绪刺激，也是连续、情境化和具有奖赏价值的自然刺激，因此可能更容易调动海马相关的情境记忆和事件加工机制。该解释仍需在更大样本和更完整行为指标中进一步验证。",
        269: "4.3.3 放电单元活动结果",
        270: "基于IFR的spike分析显示，在两个自采短视频被试中共提取45个可分析放电单元。以喜欢评分4-5分、不喜欢评分1-2分为事件条件，K-means聚类得到两个响应模式簇：cluster 0包含22个单元，cluster 1包含23个单元。cluster 1在事件后0.20-0.70 s和1.25-1.65 s出现喜欢与不喜欢条件之间的差异，表现为喜欢条件下基线校正IFR更低，而不喜欢条件下IFR相对更高。需要注意的是，如果聚类输入特征本身包含条件差异，那么在聚类结果后的条件差异检验存在潜在循环分析风险；因此该结果应视为描述性探索，后续需要使用独立时间窗、留出数据或交叉验证进行确认。",
        275: "这一结果提示，短视频偏好相关的放电活动并不是简单的整体放电增强。相反，部分放电单元在观看喜欢视频后表现为放电率降低，而不喜欢视频可能诱发更强、更持续的事件后放电反应。这与LFP结果中喜欢条件功率降低的趋势相互补充，提示主观偏好可能伴随边缘系统神经活动的选择性变化，而不喜欢或高显著性内容可能诱发更强的快速反应。由于样本和单元质量指标报告有限，该解释应保持谨慎。",
        276: "进一步分析喜欢/不喜欢条件下IFR时间曲线之间的耦合强度和响应动态发现，杏仁核和海马的脑区内耦合以及杏仁核-海马脑区间耦合整体均接近零，提示两个脑区在该任务中未观察到明显放电同步。具体而言，脑区内耦合在喜欢条件下的平均相关约为0.008，在不喜欢条件下约为-0.005；脑区间耦合在喜欢条件下约为0.006，在不喜欢条件下约为0.004。由于缺少置信区间、置换基线和统计检验，这些数值不宜进一步解释为特定功能性同步模式。在响应动态上，杏仁核不喜欢条件的IFR响应斜率更高，约为0.267 Hz/s，而喜欢条件约为0.102 Hz/s；海马中不喜欢条件也呈正斜率，约为0.137 Hz/s，而喜欢条件略为负斜率，约为-0.023 Hz/s。这些结果提示，相比喜欢条件，不喜欢条件可能更容易诱发杏仁核和海马的事件后放电率升高。",
        278: "研究二提示，真实短视频刺激能够在杏仁核和海马中诱发与主观偏好相关的频谱变化，并在放电单元活动层面表现出喜欢和不喜欢条件之间的描述性差异。相较研究一，海马在研究二中的参与更为明显，说明短视频偏好加工可能超越了单纯情绪效价判断，更多涉及情境记忆、事件结构和观看动机的整合。由于LFP和spike样本量均较小，本研究二结果应定位为探索性发现。",
        279: "5 研究三：公开自然视频数据集中的补充性探索",
        281: "研究一和研究二均基于自采颅内脑电数据，分别考察标准情绪图片和真实短视频片段中的杏仁核—海马活动。然而，颅内脑电研究通常受临床电极植入位置和被试数量限制，单一实验结果需要在独立数据来源中谨慎比较。研究三因此引入公开自然视频观看数据集，以分析更连续、更自然的观看情境中杏仁核和海马的神经活动模式。由于该数据集的刺激类型、任务目标、行为指标和统计对象均不同于研究一和研究二，研究三作为公开自然视频数据的补充性探索，而非严格意义上的验证研究。",
        285: "研究三使用Keles等人构建的公开自然视频观看数据集（Keles et al., 2024）。该数据集包含人类患者在观看自然电影片段时的多模态神经记录数据，包括单单位放电、颅内脑电和功能磁共振等信息。根据本地Keles分析结果核查，本研究共识别16名被试的29个真实NWB run，其中27个run通过质量控制并进入组水平full-spectrum分析，2个run因无可用clean trial被跳过。相较自采短视频任务，该数据集具有更大的样本规模和更自然的连续观看结构，适合用于探索杏仁核—海马系统在自然视频加工中的活动规律。",
        289: "首先，本研究采用数据集中已有的场景切割或镜头切换信息作为事件标记，将连续视频划分为若干事件窗口，并分析事件发生前后杏仁核和海马的神经活动变化。事件边界研究表明，连续自然叙事通常会被观察者分割为相对离散的事件单元（Zacks et al., 2007; Baldassano et al., 2017）。不过，镜头切换更接近视觉和情境变化的外部标记，并不必然对应情绪或唤醒强度的变化。",
        297: "为进一步提高事件标记与情绪加工的对应关系，本研究还探索使用视觉语言模型对视频片段进行唤醒度标注。具体而言，可将视频划分为2 s窗口，每个窗口提取若干帧图像并结合音频显著性特征，使用Qwen2.5-VL-3B-Instruct评估片段的arousal score和confidence（Bai et al., 2025）。最终得分可由唤醒评分、模型置信度和标准化音频显著性加权构成。本研究仅将其作为探索性自动标注结果；由于缺少完整prompt报告、人工复核、一致性评估以及模型对情绪/唤醒判断的效度验证，该方法不能替代人工标注或标准化情绪材料验证。",
        299: "研究三在杏仁核和海马电极之间计算不同频段的功能连接强度，并进一步使用谱格兰杰因果分析（spectral Granger causality, sGC）估计两个脑区之间的方向性信息流（Granger, 1969; Ding et al., 2000; Barnett & Seth, 2014）。分析重点包括低频与高频连接强度的比较，以及海马到杏仁核和杏仁核到海马两个方向的信息流差异。",
        310: "对于放电单元数据，本研究围绕事件标记计算事件锁定IFR时间曲线，并比较杏仁核和海马在事件发生前后的放电率变化。同时，通过放电单元响应模式聚类，探索自然视频事件中是否存在激活型和抑制型放电单元，以及这些单元在杏仁核和海马中的空间分布特点。",
        318: "在Keles数据集的场景切割事件锁定分析中，共识别29个真实NWB run，其中27个run通过QC并进入组水平分析，2个run因无可用clean trial被跳过。全频段组水平结果显示，杏仁核-海马连接主要集中在低频范围，组平均相干性在3.9-43.0 Hz范围内约为0.34-0.49。与高频相比，低频连接更稳定，提示自然视频观看中杏仁核和海马之间的信息整合可能主要依赖低频振荡。",
        322: "谱格兰杰因果分析显示，在场景切割锁定的全频谱结果中，海马到杏仁核的信息流强度数值上高于杏仁核到海马的信息流强度。组水平平均sGC中，H→A方向为0.584，A→H方向为0.535，平均方向差为0.049。FDR校正后显著频点主要分布在9.6-13.2 Hz、17.6-20.0 Hz和43.6-44.8 Hz三个频段。该结果提示，在自然视频观看中，海马到杏仁核方向的信息流可能更强，但仍需结合模型阶数选择、平稳性检验、残差白噪声检验、模型稳定性和参考方式等方法细节谨慎解释。",
        323: "上述结果不应被简单概括为固定的海马先行情境加工序列，而更适合被理解为场景切割锁定、全频谱分析下观察到的方向性趋势。与静态图片不同，自然视频需要被试持续追踪场景、人物和事件变化，因此海马的信息整合功能可能更加突出；但在高唤醒片段或特定频段中，杏仁核到海马方向也可能表现出不同优势。",
        325: "在Keles公开自然视频数据集中，以中立场景切割事件为时间锁定点进行spike分析时，杏仁核和海马均显示出事件相关放电率调制。区域感知的spike汇总结果显示，脑区内IFR耦合整体强于杏仁核-海马跨脑区耦合，但总体耦合强度仍然较弱，说明自然视频事件可诱发两个脑区的放电率变化，但这种变化并不表现为强同步放电。A-H时滞分析进一步显示，多数试次中海马领先杏仁核，同时部分试次中也存在杏仁核中位领先约300 ms的情况，说明该方向性关系存在一定试次间异质性。",
        328: "在进一步的探索性分析中，基于单元IFR时间曲线可将放电单元响应模式分为两类：一类为事件后放电率下降的抑制型单元，共899个；另一类为事件后放电率升高的激活型单元，共503个。两类时间曲线在事件发生后迅速分离，并在0-2 s响应窗内保持相反的放电率变化方向，提示自然视频事件并非诱发单一方向的平均放电变化，而是同时包含抑制型和激活型放电单元群。",
        330: "图5.4 Keles数据集中基于IFR时间曲线的单元响应模式聚类。蓝色曲线表示事件后放电率下降的抑制型放电单元群，红色曲线表示事件后放电率上升的激活型放电单元群，阴影为估计误差范围。",
        331: "在高唤醒事件标记的探索性分析中，视觉语言模型Qwen2.5-VL-3B-Instruct对视频进行2秒窗口、1秒步长扫描，共得到477个候选窗口；每个窗口抽取4帧并结合音频显著性特征，最终选择19个高唤醒片段（final score > 70）。模型解析或推理失败数为0。所选片段与官方场景切割的2秒命中率为68.4%，随机基线为55.2%（富集倍数1.24，置换检验p=0.174）。因此，该比较未达到显著水平，只能说明AI标注片段与镜头切换之间存在数值趋势，不能作为AI标注有效性的强证据。",
        332: "基于这些高唤醒事件重新进行full-spectrum sGC分析时，共有27个run进入组水平分析，2个run因QC失败被排除。高唤醒事件锁定结果显示，平均相干性为0.380，H→A平均sGC为1.501，A→H平均sGC为1.438，方向差数值上仍表现为H→A更强。该结果与场景切割事件锁定分析方向相近，但由于AI事件标注有效性仍待验证，且该处sGC数值尺度与场景切割分析不同，应作为探索性结果谨慎解释。",
        333: "进一步将AI高唤醒片段锁定后的方向性sGC结果分解到θ频段（4-8 Hz）和β频段（13-30 Hz）后发现，θ频段中A→H与H→A方向的组水平差异较小，A→H平均值为319.139，H→A平均值为326.074，配对t检验经FDR校正后未达到显著。β频段则表现出A→H方向优势，A→H平均值为712.473，H→A平均值为282.589，配对t检验经FDR校正后仍显著。该结果与全频平均中的H→A数值优势并不完全一致，提示不同频段可能存在方向性差异。需要谨慎解释不同尺度下的 sGC 数值，并在后续版本中明确这些数值是频段积分、均值还是其他统计量。",
        340: "图5.7 AI高唤醒片段锁定条件下θ与β频段的杏仁核-海马方向性sGC结果。柱形图为被试平均sGC值，误差线为SEM；星号表示FDR校正后显著。需注意，β频段显示A→H方向优势，与全频平均H→A数值优势并不完全一致。",
        343: "研究三基于公开自然视频数据集，提供了自然连续刺激情境下的补充性探索证据。结果显示，自然视频观看中杏仁核和海马之间低频连接更强，场景切割锁定的全频谱sGC结果中H→A方向数值上更高；但高唤醒片段的分频段分析又显示β频段A→H方向优势。事件锁定spike分析进一步提示自然视频事件能够诱发杏仁核和海马的放电率调制。整体而言，研究三支持杏仁核—海马系统参与自然视频事件加工，但尚不能作为对自采短视频实验的严格验证。",
        346: "本研究围绕短视频片段观看诱发的杏仁核—海马神经活动展开，采用标准情绪图片、真实短视频片段和公开自然视频观看数据三类材料，逐步提高刺激的生态效度，探索情绪效价、主观偏好和自然视频事件加工中的颅内脑电活动。总体而言，本研究发现：标准情绪图片能够在杏仁核中诱发效价相关的频谱调制；真实短视频能够在杏仁核和海马中诱发偏好相关的功率变化，并在放电单元活动层面表现出喜欢和不喜欢条件之间的描述性差异；公开自然视频数据进一步提示杏仁核和海马之间存在以低频为主的功能连接，且方向性结果可能随事件标记和频段而变化。",
        349: "然而，在研究二中，短视频偏好不仅调制杏仁核活动，也调制海马低频活动。这一结果提示，短视频观看中的“喜欢”并不是简单的正性效价判断。真实短视频包含连续情节、声音、节奏、语义和新奇性等多重信息，个体在观看过程中需要将这些信息整合为主观偏好和继续观看相关评价。由于本研究中喜欢程度与继续观看渴望评分几乎完全一致，当前数据尚不能区分偏好和继续观看欲望两个行为成分；后续研究需要使用更细分的效价、唤醒、熟悉度、兴趣、新奇性和继续观看意愿指标。",
        352: "研究三中场景切割锁定的全频谱结果观察到H→A方向数值更强，为“情境信息可能影响情绪显著性加工”这一解释提供了相关证据。自然视频具有连续性和情境性，海马可能参与场景和事件信息的组织，再与杏仁核的情绪显著性或价值评估过程发生交互。需要注意的是，高唤醒片段分频段结果显示β频段A→H方向优势，因此本文不再将结果概括为固定的海马先行序列。杏仁核和海马之间的相对领先关系可能随刺激类型、唤醒强度、频段和任务要求而变化。",
        355: "研究三中低频功能连接强于高频连接，与这一理论相一致。短视频和自然电影观看需要在较长时间尺度上整合视觉、听觉、语义和情境线索，因此低频振荡可能为杏仁核和海马之间的信息交换提供时间框架。不过，高唤醒片段分频段sGC结果显示β频段方向性与全频平均不完全一致，提示不同频段可能承担不同方向的信息传递功能。未来研究可以进一步区分θ、α、β和HFB等频段在偏好形成、唤醒反应和继续观看决策中的具体作用。",
        357: "除LFP时频活动外，本研究还探索了放电单元活动在短视频观看中的变化。研究二显示，喜欢视频事件后的IFR增量整体低于不喜欢视频，而不喜欢视频可能诱发更陡峭的杏仁核放电响应。该结果提示，不喜欢或高显著性刺激并不一定表现为主观价值较低的“弱刺激”，反而可能因新奇、冲突或不适感而诱发更强的快速反应。鉴于放电单元数量有限且质量指标报告不完整，该结论应保持谨慎。",
        358: "研究三中的聚类结果进一步表明，自然视频事件后存在激活型和抑制型放电单元群。这提示短视频观看诱发的神经反应具有明显异质性。仅使用平均功率或平均放电率可能掩盖不同放电单元群的功能差异，因此未来分析可进一步结合单元质量指标、脑区位置、视频内容特征和主观评分，以更精细地刻画短视频观看中的神经编码模式。",
        360: "在理论层面，本研究将短视频这一高生态效度自然刺激引入杏仁核—海马情绪奖赏加工框架，尝试连接经典情绪图片范式、真实短视频偏好加工和自然视频观看数据。研究结果提示，短视频片段观看中的神经加工不能简单套用传统正负效价模型，而需要同时考虑主观偏好、奖赏期待和情境记忆等因素。与此同时，当前数据并不能直接推论短视频过度使用或成瘾机制。",
        361: "在方法层面，本研究结合LFP时频分析、功能连接、方向性信息流和spike放电率分析，为理解自然媒介刺激下的人类边缘系统活动提供了多层次探索性证据。相较单纯问卷或行为研究，颅内脑电能够以更高时间分辨率揭示短视频观看过程中的快速神经动态；但在小样本颅内脑电研究中，统计单位、通道嵌套结构和多重比较校正均需要谨慎处理。",
        362: "在实践层面，短视频过度使用已成为重要的社会和心理健康问题。本研究并不直接检验临床成瘾机制，也未纳入问题性短视频使用量表或高低风险组比较。因此，本文结果更适合被理解为短视频偏好加工的初步颅内电生理证据，而不是直接提出临床干预对象或持续观看机制的依据。后续研究可在本研究基础上进一步纳入使用强度、问题性使用量表和持续观看行为指标。",
        364: "本研究仍存在若干局限。首先，颅内脑电被试均为临床癫痫患者，样本量较小且电极植入位置由临床需要决定，因此结果的普遍性需要谨慎解释。其次，自采短视频任务中的视频材料虽然更接近日常使用场景，但不同被试对视频类别、内容和节奏的偏好差异较大，可能增加结果变异；同时，本研究未系统采集视频效价、唤醒度、熟悉度、兴趣、新奇性等行为指标，喜欢评分与继续观看渴望评分高度一致，限制了对不同心理成分的区分。第三，当前研究三中对自然视频事件的划分主要依赖场景切割或探索性AI唤醒标注。镜头切换不一定等同于情绪事件，而AI标注的高唤醒片段仍需要人工验证和更严格的信效度评估。第四，sGC分析需要更完整报告时间窗长度、MVAR模型阶数选择标准、平稳性检验、残差白噪声检验、模型稳定性、参考方式以及被试内pair平均流程。最后，本研究目前主要关注杏仁核和海马，未来可进一步纳入伏隔核、眶额皮层、前扣带回等区域，以构建更完整的短视频情绪奖赏加工网络。",
        366: "本研究利用颅内脑电技术，考察了短视频片段观看诱发的杏仁核—海马神经活动特征。通过标准情绪图片、真实短视频片段和公开自然视频数据三个层次的分析，本研究发现：杏仁核能够在标准情绪图片条件下表现出效价相关的频谱调制；真实短视频刺激能够在杏仁核和海马中诱发主观偏好相关的神经活动变化；自然视频观看过程中，杏仁核和海马之间低频连接更强，方向性结果可能随事件标记和频段而变化。",
        367: "上述结果提示，短视频片段观看中的情绪与偏好加工可能依赖杏仁核—海马系统的频段特异性活动和方向性通信。短视频作为一种连续、多模态、高生态效度的自然刺激，其神经加工过程不仅包含基本情绪效价判断，还涉及主观偏好、情境记忆和奖赏经验的整合。由于本研究未直接测量短视频过度使用、成瘾倾向或持续观看行为，因此这些发现应被定位为短视频偏好加工的探索性颅内电生理证据，并为后续自然媒介刺激和问题性短视频使用研究提供参考。",
        370: "本研究所使用的分析代码已公开于GitHub仓库：https://github.com/itsxjs/seeg。该仓库包含颅内脑电数据预处理、电极定位、时频分析、放电单元活动分析、功能连接计算以及谱格兰杰因果分析等相关脚本。",
        395: "附录A汇总各被试的Desikan-Killiany或DKT分区计数。该表用于说明全部植入接触点的解剖分布；正文分析仅纳入杏仁核和海马相关电极或放电单元。由于不同被试电极数量和植入位置差异较大，正文统计推断均需结合被试数量和通道嵌套结构谨慎解释。",
    },
}


TOC_REPLACEMENTS = {
    "1.2 短视频过度使用的危害及其潜在神经机制": "1.2 短视频过度使用的风险及相关研究背景",
    "5 研究三：公开自然视频数据集中的神经活动验证": "5 研究三：公开自然视频数据集中的补充性探索",
}


def set_text(paragraph, text: str) -> None:
    paragraph.text = text
    apply_body_font(paragraph)


def apply_body_font(paragraph) -> None:
    for run in paragraph.runs:
        run.font.name = "宋体"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        run.font.size = Pt(12)


def apply_heading_font(paragraph, level: int = 3) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in paragraph.runs:
        run.font.name = "黑体"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        run.font.bold = True
        run.font.size = Pt(14 if level <= 1 else 12)


def set_paragraph_style(doc: Document) -> None:
    heading_patterns = [
        r"^\d+\s",
        r"^\d+\.\d+\s",
        r"^\d+\.\d+\.\d+\s",
        r"^参考文献$",
        r"^附录$",
        r"^附录A\s",
    ]
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if 110 <= i <= 397 and text:
            if any(re.match(pat, text) for pat in heading_patterns):
                try:
                    p.style = "Heading 3"
                except Exception:
                    pass
                apply_heading_font(p)
            elif text.startswith("图") or text.startswith("表"):
                try:
                    p.style = "Caption"
                except Exception:
                    pass
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.name = "宋体"
                    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
                    run.font.bold = True
                    run.font.size = Pt(10.5)
            elif 371 <= i <= 391:
                apply_body_font(p)
                p.paragraph_format.first_line_indent = None
                p.paragraph_format.left_indent = Cm(0)
            else:
                apply_body_font(p)


def replace_texts(doc: Document) -> list[str]:
    changed = []
    for _, repl in REPLACEMENTS.items():
        for idx, text in repl.items():
            if idx < len(doc.paragraphs):
                set_text(doc.paragraphs[idx], text)
                changed.append(f"P{idx}")
    for p in doc.paragraphs:
        if p.style and p.style.name.startswith("toc"):
            for old, new in TOC_REPLACEMENTS.items():
                if old in p.text:
                    set_text(p, p.text.replace(old, new))
                    changed.append("TOC")
    # Global conservative wording in the main thesis body only.
    for idx in range(110, min(398, len(doc.paragraphs))):
        p = doc.paragraphs[idx]
        txt = p.text
        if not txt:
            continue
        new = txt
        replacements = {
            "神经元放电率": "放电单元活动",
            "神经元群": "放电单元群",
            "神经元响应": "放电单元响应",
            "神经元类型": "单元质量指标",
            "like与dislike": "喜欢/不喜欢",
            "like/dislike": "喜欢/不喜欢",
            "like条件": "喜欢条件",
            "dislike条件": "不喜欢条件",
            "cluster校正": "cluster校正",
        }
        for old, new_word in replacements.items():
            new = new.replace(old, new_word)
        if new != txt:
            set_text(p, new)
            changed.append(f"P{idx}-global")
    return changed


def add_reference_paragraphs(doc: Document) -> None:
    existing = "\n".join(p.text for p in doc.paragraphs)
    ref_anchor = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip().startswith("Zheng, J., Anderson"):
            ref_anchor = i
            break
    if ref_anchor is None:
        return
    anchor = doc.paragraphs[ref_anchor]
    for ref in reversed(NEW_REFERENCES):
        first_author = ref.split(",")[0]
        if first_author in existing and ref[:35] in existing:
            continue
        new_p = insert_paragraph_after(anchor, ref)
        apply_body_font(new_p)
        anchor = new_p


def insert_paragraph_after(paragraph, text: str = "", style=None):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if style is not None:
        new_para.style = style
    if text:
        new_para.add_run(text)
    return new_para


def set_repeat_table_header(row):
    trPr = row._tr.get_or_add_trPr()
    tblHeader = OxmlElement("w:tblHeader")
    tblHeader.set(qn("w:val"), "true")
    trPr.append(tblHeader)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def format_tables(doc: Document) -> None:
    for ti, table in enumerate(doc.tables):
        if ti not in (0, 1):
            continue
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True
        if table.rows:
            set_repeat_table_header(table.rows[0])
        for r_idx, row in enumerate(table.rows):
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                if r_idx == 0:
                    set_cell_shading(cell, "D9EAF7")
                for p in cell.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if r_idx == 0 or ti == 0 else WD_ALIGN_PARAGRAPH.LEFT
                    for run in p.runs:
                        run.font.name = "宋体"
                        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
                        run.font.size = Pt(9 if ti == 1 else 10)
                        if r_idx == 0:
                            run.font.bold = True
        if ti == 0 and len(table.columns) == 4:
            widths = [Cm(2.0), Cm(1.8), Cm(4.0), Cm(7.0)]
            for col_idx, width in enumerate(widths):
                for cell in table.columns[col_idx].cells:
                    cell.width = width
        if ti == 1 and len(table.columns) == 4:
            widths = [Cm(2.0), Cm(3.2), Cm(6.8), Cm(1.8)]
            for col_idx, width in enumerate(widths):
                for cell in table.columns[col_idx].cells:
                    cell.width = width


def mark_fields_dirty(docx_path: Path) -> None:
    import zipfile
    from lxml import etree

    tmp = docx_path.with_suffix(".dirty.tmp.docx")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(docx_path, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/settings.xml":
                root = etree.fromstring(data)
                update = root.find("w:updateFields", namespaces=ns)
                if update is None:
                    update = etree.SubElement(root, qn("w:updateFields"))
                update.set(qn("w:val"), "true")
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
            zout.writestr(item, data)
    tmp.replace(docx_path)


def clear_update_fields(docx_path: Path) -> None:
    import zipfile
    from lxml import etree

    tmp = docx_path.with_suffix(".settings.tmp.docx")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(docx_path, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/settings.xml":
                root = etree.fromstring(data)
                for update in root.findall("w:updateFields", namespaces=ns):
                    root.remove(update)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
            zout.writestr(item, data)
    tmp.replace(docx_path)


def write_report(path: Path, output_final: Path, output_comments: Path, changed: list[str], original_hash: str) -> None:
    report = f"""# 毕业论文正文修订报告

## 输出文件
- 最终版：`{output_final}`
- 批注版：`{output_comments}`
- 原稿 SHA-256：`{original_hash}`（用于确认原稿未被修改）

## 总体修订策略
- 将全文主线从“短视频过度使用/成瘾机制”收回到“有限样本下短视频偏好加工的探索性颅内电生理证据”。
- 对无法由现有文档或本地结果确认的数据不作编造；改为局限说明、谨慎表述或在批注版提示作者补充。
- 研究三从“验证”改为“公开自然视频数据的补充性探索”，避免把不同任务、刺激和统计对象强行串成验证链。

## 对老师意见的逐条回应
1. 结论强度过高：已弱化摘要、引言、研究三、讨论和结论中的过度使用机制、干预靶点、海马领先等表述；明确本研究未直接测量问题性短视频使用、成瘾倾向、持续刷屏或算法反馈。
2. 样本量与统计推断：在研究一、研究二、局限中明确 LFP n=3、spike/放电单元分析 n=2 的探索性质；不再把显著 time-frequency bin 数量作为证据强度。
3. 研究二行为指标：补充喜欢程度与继续观看渴望评分高度一致，解释主分析使用喜欢评分，未将 craving 作为独立神经预测变量。
4. spike 分析：将“神经元”统一改为“放电单元/放电单元群”；补充 K-means 聚类后条件检验的 circularity 风险；接近零的耦合结果改为“未观察到明显同步”。
5. 研究三 sGC 与 AI 标注：明确研究三为补充性探索；写明 AI 高唤醒标注与随机基线比较 p=0.174 未显著；补充不同频段方向不一致和 sGC 数值尺度待核对的问题。
6. 方法缺失：补充 sEEG/iEEG 参考方式、伪迹剔除阈值、统计单位、MVAR/sGC 方法缺口等谨慎说明；批注版在关键位置提醒作者补充。
7. 图表与编号：统一正文图题/表题样式；整理表2.1和附录A表格的字体、表头、列宽和分页友好性。实际图像分辨率未重画，需要作者用原始绘图脚本另行导出高清图。
8. 语言表达：删除“上头”“时间黑洞”等口语表达或改为学术表达；统一 like/dislike 等术语为中文。
9. 参考文献：新增 IAPS、Morlet 小波、cluster-based permutation、FieldTrip/RAVE、Granger/sGC、自然视频事件边界、Qwen2.5-VL 等关键方法和背景文献。

## 新增参考文献
{chr(10).join(f'- {r}' for r in NEW_REFERENCES)}

## 仍建议作者补充或核对
- 每名被试进入研究一/二、LFP、spike分析的状态，及行为/QC排除原因。
- 每名被试的电极数、通道数、试次数、QC后保留比例和 seizure onset zone / epileptiform activity 排除规则。
- cluster-based permutation test 的置换单位、是否保留被试内结构、cluster-level p值和每名被试效应图。
- spike sorting 质量指标：isolation distance、L-ratio、ISI violation、amplitude cutoff 等。
- sGC 的时间窗、MVAR阶数选择、平稳性检验、残差白噪声检验、模型稳定性、参考方式和 pair/run 平均流程。
- AI高唤醒标注的完整 prompt、评分标准、抽帧策略、人工复核与一致性评估。
- 低分辨率图建议用原始脚本重新导出高 DPI 图片，再在 Word 中替换。

## 批注版说明
- 批注版采用文内蓝色“【批注】”段落，而非 Word 原生评论气泡。原因是 Word for Mac 通过自动化打开原生 OOXML 评论版时出现超时；文内批注版更稳，便于直接打开和查看。
- 批注集中在六类关键风险：研究主线降强度、研究三定位、AI标注、n=3统计推断、spike聚类循环分析、sGC数值尺度。

## 格式检查说明
- 已修复第2章以后大量标题为 Normal 样式的问题，并统一图题、表题、正文术语。
- 为避免 Word 打开批注版时因自动更新域代码而变慢，文档未强制设置打开时自动更新目录；如需刷新页码，可在 Word 中右键目录选择“更新域/更新整个目录”。
- 最终格式验收以 Microsoft Word 实际显示为准；artifact-tool 渲染仅作辅助解析检查。

## 自动修改范围
- 程序化替换段落/样式标记数量：{len(changed)}
- 修改范围限定在“第一部分 毕业论文（设计）”正文、参考文献和附录A；后续作者简历、任务书、考核表未主动修改。
"""
    path.write_text(report, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--final", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--hash", required=True)
    args = ap.parse_args()

    doc = Document(args.input)
    changed = replace_texts(doc)
    add_reference_paragraphs(doc)
    set_paragraph_style(doc)
    format_tables(doc)
    final_path = Path(args.final)
    doc.save(final_path)
    clear_update_fields(final_path)
    write_report(Path(args.report), final_path, Path(str(final_path).replace("最终版", "批注版")), changed, args.hash)
    print(json.dumps({"final": str(final_path), "changed": len(changed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
