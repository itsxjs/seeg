disp('Step 1: Adding markers from channel 50...');
triggerSignal = EEG.data(triggerChan, :);
aboveThreshold = triggerSignal > threshold;
eventOnsets = find(diff([0 aboveThreshold]) == 1);
EEG.event = [];
for i = 1:length(eventOnsets)
EEG.event(i).type = 'Stimulus';
EEG.event(i).latency = eventOnsets(i);
EEG.event(i).duration = 0;
end
EEG = eeg_checkset(EEG, 'eventconsistency');
ms_per_sample = 1000 / EEG.srate;
latencies = [EEG.event.latency];
keep_indices = [];
last_latency = -Inf;
for i = 1:length(latencies)
current_latency = latencies(i);
interval_ms = (current_latency - last_latency) * ms_per_sample;
if interval_ms >= min_interval_ms
keep_indices(end+1) = i;
last_latency = current_latency;
end
end
EEG.event = EEG.event(keep_indices);
EEG.event(strcmp({EEG.event.type}, 'boundary')) = [];
EEG = eeg_checkset(EEG);
% ===== 保存结果 =====
EEG.setname = sprintf('%s_01_AddMarker', id);
pop_saveset(EEG, 'filename', [EEG.setname '.set'], 'filepath', save_path);