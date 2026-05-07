%% Created on 2025.7.16 by Chenglu 

% 需要确保EEG 已加载
ms_per_sample = 1000 / EEG.srate;
latencies = [EEG.event.latency];

% 初始化event list
keep_indices = [];
last_latency = -Inf;

for i = 1:length(latencies)
    current_latency = latencies(i);
    interval_ms = (current_latency - last_latency) * ms_per_sample;

    if interval_ms >= 300 % 满足≥300ms，保留
        keep_indices(end+1) = i;
        last_latency = current_latency;
    end
end

% 创建新的 EEG.event
EEG.event = EEG.event(keep_indices);
EEG.event(strcmp({EEG.event.type}, 'boundary')) = [];
EEG = eeg_checkset(EEG)