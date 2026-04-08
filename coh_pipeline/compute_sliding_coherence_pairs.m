function [C_tf, freq_vec, time_vec, meta] = compute_sliding_coherence_pairs(X, Y, srate, times_sec, params)
% compute_sliding_coherence_pairs
% Time-varying linear coherence with Welch averaging INSIDE each big window.
%
% X: [nX x nTime x nTrial]
% Y: [nY x nTime x nTrial]
% srate: Hz
% times_sec: [nTime x 1] seconds
%
% Required params fields:
%   win_ms, step_ms, freq_range, detrend_each_window, nfft_mode, verbose
%   subwin_ms, sub_ovlp  (Welch sub-window within each big window)

[nX, nTime, nTrial] = size(X);
[nY, nTime2, nTrial2] = size(Y);
assert(nTime==nTime2 && nTrial==nTrial2, 'X/Y 维度不一致');

%% ===== big sliding window =====
win_samp  = round(params.win_ms  * srate / 1000);
step_samp = round(params.step_ms * srate / 1000);
if win_samp < 10
    error('win_ms 太短导致 win_samp < 10，不合理。');
end

start_idx  = 1;
end_idx    = nTime - win_samp + 1;
win_starts = start_idx:step_samp:end_idx;
nWin       = numel(win_starts);

time_vec = zeros(1,nWin);
for w = 1:nWin
    st = win_starts(w);
    ed = st + win_samp - 1;
    time_vec(w) = mean(times_sec(st:ed));
end

%% ===== Welch sub-window (critical to avoid coherence==1) =====
if ~isfield(params,'subwin_ms') || ~isfield(params,'sub_ovlp')
    error('缺少 params.subwin_ms 或 params.sub_ovlp。建议 subwin_ms=200, sub_ovlp=0.5');
end

subwin_samp   = round(params.subwin_ms * srate / 1000);
subwin_samp   = max(8, subwin_samp);            % 防呆：至少几个点
subwin_samp   = min(subwin_samp, win_samp-1);   % 必须 < win_samp，否则仍是 1 段

noverlap_samp = round(subwin_samp * params.sub_ovlp);
noverlap_samp = min(max(noverlap_samp,0), subwin_samp-1);

% nfft 跟 subwin 走更合理
if ischar(params.nfft_mode) && strcmpi(params.nfft_mode,'nextpow2')
    nfft = 2^nextpow2(subwin_samp);
else
    nfft = params.nfft_mode;
end

%% ===== pair list =====
[pair_i, pair_j] = ndgrid(1:nX, 1:nY);
pair_i = pair_i(:);
pair_j = pair_j(:);
nPairs = numel(pair_i);

if isfield(params,'verbose') && params.verbose
    fprintf('  compute_sliding_coherence_pairs: nTrial=%d, nPairs=%d, nWin=%d, bigwin=%d samp, step=%d samp, subwin=%d samp, ovlp=%d samp\n', ...
        nTrial, nPairs, nWin, win_samp, step_samp, subwin_samp, noverlap_samp);
end

%% ===== freq vector (use the SAME settings as main computation) =====
test_x = squeeze(X(1, 1:win_samp, 1));
test_y = squeeze(Y(1, 1:win_samp, 1));
if params.detrend_each_window
    test_x = detrend(test_x);
    test_y = detrend(test_y);
end

[~, f] = mscohere(test_x, test_y, subwin_samp, noverlap_samp, nfft, srate);

freq_vec_full = f(:);
keep = freq_vec_full >= params.freq_range(1) & freq_vec_full <= params.freq_range(2);
freq_vec = freq_vec_full(keep);

nFreq = numel(freq_vec);
C_tf  = nan(nFreq, nWin);

%% ===== main loop: window -> trial -> pair =====
for w = 1:nWin
    st = win_starts(w);
    ed = st + win_samp - 1;

    C_sum = zeros(nFreq,1);
    count = 0;

    for tr = 1:nTrial
        x_seg_all = squeeze(X(:, st:ed, tr)); % [nX x win_samp]
        y_seg_all = squeeze(Y(:, st:ed, tr)); % [nY x win_samp]

        if params.detrend_each_window
            x_seg_all = detrend(x_seg_all')'; % per-channel detrend
            y_seg_all = detrend(y_seg_all')';
        end

        for p = 1:nPairs
            xi = pair_i(p);
            yj = pair_j(p);

            x_seg = x_seg_all(xi, :).';
            y_seg = y_seg_all(yj, :).';

            % ✅ 关键：这里必须用 subwin/noverlap 做 Welch 平均
            cxy = mscohere(x_seg, y_seg, subwin_samp, noverlap_samp, nfft, srate);
            cxy = cxy(keep);

            C_sum = C_sum + cxy;
            count = count + 1;
        end
    end

    C_tf(:,w) = C_sum / max(count,1);
end

%% ===== meta =====
meta = struct();
meta.n_pairs_used   = nPairs;
meta.n_trials       = nTrial;
meta.win_ms         = params.win_ms;
meta.step_ms        = params.step_ms;
meta.subwin_ms      = params.subwin_ms;
meta.sub_ovlp       = params.sub_ovlp;
meta.freq_range     = params.freq_range;
meta.method         = params.method;
meta.nfft           = nfft;
meta.win_samp       = win_samp;
meta.subwin_samp    = subwin_samp;
meta.noverlap_samp  = noverlap_samp;
end
