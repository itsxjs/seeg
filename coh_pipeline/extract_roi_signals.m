function X = extract_roi_signals(EEG, chan_labels)
% extract_roi_signals
% 输入：
%   EEG         : EEGLAB epoched struct (EEG.data: chan x time x trial)
%   chan_labels : cellstr，ROI 内通道名列表
% 输出：
%   X : [nChan x nTime x nTrial] double

all_labels = string({EEG.chanlocs.labels});
want = string(chan_labels);

[tf, loc] = ismember(want, all_labels);
if any(~tf)
    missing = want(~tf);
    warning('缺少通道（将跳过这些）：%s', strjoin(missing, ', '));
end
loc = loc(tf);

if isempty(loc)
    error('ROI 中没有任何通道在 EEG.chanlocs.labels 里匹配到。');
end

X = double(EEG.data(loc,:,:));
end
