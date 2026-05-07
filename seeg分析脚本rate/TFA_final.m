%% TFA

%% ---- 参数 ----
subj_id  = 'Sub005';
data_dir = pwd;  % EEG .set 文件所在路径
epoch_files = { ...
    sprintf('%s_cue_epoch_clean.set', subj_id), ...
    sprintf('%s_target_epoch_clean.set', subj_id) ...
};
lock_types = {'cue','target'};

freqs = logspace(log10(1), log10(192), 24);  % 24 log-spaced freqs
n_freqs = length(freqs);

baseline_win_cue = [-500 0]; % cue-locked baseline
analysis_win_cue = [0 2400]; % cue-locked epochs
analysis_win_target = [0 2500]; % target-locked epochs

target_ms = 4000; % zero-padded length (ms)

n_bs = 1000; % bootstrap次数
ds_ms = 50;  % downsample to 50 ms

%% ===== 循环 cue / target =====
for iL = 1:2
    lock_type = lock_types{iL};
    EEG = pop_loadset('filename', epoch_files{iL}, 'filepath', data_dir);
    srate = EEG.srate;
    n_trials = EEG.trials;
    n_chans  = EEG.nbchan;
    tms = EEG.times;

    if strcmp(lock_type,'cue')
        baseline_win = baseline_win_cue;
        analysis_win = analysis_win_cue;
    else
        baseline_win = []; % target 不直接用
        analysis_win = analysis_win_target;
    end

    target_points = round(target_ms / 1000 * srate);
    time_idx = find(tms >= analysis_win(1) & tms <= analysis_win(2));
    if strcmp(lock_type,'cue')
        baseline_idx = find(tms >= baseline_win(1) & tms <= baseline_win(2));
    end
    n_timepoints = length(time_idx);

    power_data = zeros(n_trials, n_chans, n_freqs, n_timepoints);

    % ===== Step 1: Filter + Hilbert =====
    for f = 1:n_freqs
        f_low  = freqs(f) / sqrt(2);
        f_high = freqs(f) * sqrt(2);
        filt_order = round(3 * srate / f_low);
        filt_order = filt_order + mod(filt_order,2);

        fprintf('[%s] Filtering %.2f Hz...\n', lock_type, freqs(f));
        EEG_filt = pop_eegfiltnew(EEG, f_low, f_high, filt_order, 0, [], 0);

        for trial = 1:n_trials
            for chan = 1:n_chans
                signal = EEG_filt.data(chan,:,trial);
                L = length(signal);

                if L < target_points
                    pad_total = target_points - L;
                    pad_left = floor(pad_total / 2);
                    pad_right = ceil(pad_total / 2);
                    signal_padded = [zeros(1, pad_left), signal, zeros(1, pad_right)];
                else
                    signal_padded = signal;
                    pad_left = 0;
                end

                h = hilbert(signal_padded);
                amp = abs(h).^2;

                % remove padding
                amp_cropped = amp(pad_left+1 : pad_left+L);
                power_data(trial, chan, f, :) = amp_cropped(time_idx);
            end
        end
    end

    % ===== Step 2: Z-score =====

    if strcmp(lock_type,'cue')
        z_power = zeros(size(power_data));
        mu_baseline = zeros(n_chans, n_freqs);
        sigma_baseline = zeros(n_chans, n_freqs);

        for chan = 1:n_chans
            for f = 1:n_freqs
                base_vals = squeeze(power_data(:, chan, f, baseline_idx));
                base_all = base_vals(:);
                null_distr = zeros(n_bs,1);
                for b = 1:n_bs
                    sample = randsample(base_all, n_trials, true);
                    null_distr(b) = mean(sample);
                end
                mu = mean(null_distr);
                sigma = std(null_distr);
                mu_baseline(chan,f) = mu;
                sigma_baseline(chan,f) = sigma;

                for trial = 1:n_trials
                    z_power(trial, chan, f, :) = (power_data(trial, chan, f, :) - mu) / sigma;
                end
            end
        end

        % 保存 baseline 参数以便 target 使用
        save(fullfile(data_dir, sprintf('%s_cue_baseline.mat', subj_id)), ...
            'mu_baseline', 'sigma_baseline');

    else
        % target: load cue baseline
        B = load(fullfile(data_dir, sprintf('%s_cue_baseline.mat', subj_id)));
        mu_baseline = B.mu_baseline;
        sigma_baseline = B.sigma_baseline;

        z_power = zeros(size(power_data));
        for chan = 1:n_chans
            for f = 1:n_freqs
                for trial = 1:n_trials
                    z_power(trial, chan, f, :) = ...
                        (power_data(trial, chan, f, :) - mu_baseline(chan,f)) / sigma_baseline(chan,f);
                end
            end
        end
    end

    % ===== Step 3: Downsample =====
    dt = mean(diff(tms));  % ms/sample
    ds_factor = round(ds_ms / dt);

    z_power_ds = z_power(:, :, :, 1:ds_factor:end);
    tms_ds = tms(time_idx);
    tms_ds = tms_ds(1:ds_factor:end);

    chan_labels = {EEG.chanlocs.labels};
    % ===== 保存结果 =====
    save(fullfile(data_dir, sprintf('%s_%s_TF_zpower.mat', subj_id, lock_type)), ...
        'z_power_ds', 'freqs', 'tms_ds', 'mu_baseline', 'sigma_baseline', ...
        'chan_labels', '-v7.3');

    fprintf('✔ %s-locked TF analysis saved.\n', lock_type);
end

fprintf('\n 分析完成！\n');