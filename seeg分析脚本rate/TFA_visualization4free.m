%% ===== 加载与通道选择 =====
load('sub001_bin2_TF_zpower.mat');   % 改成你的文件名
ch_label = 'POL D2';                  % 选择通道
ch = find(strcmp(chan_labels, ch_label));
if isempty(ch), error('未找到通道 %s', ch_label); end

%% ===== (1) 两条件 TFR =====
conds = {'cutoff','finish'};  % 顺序与 cond_mean_z 第1/2维一致
figure('Name','TFR per condition (bin2)');
for c = 1:2
    subplot(1,2,c);
    Z = squeeze(cond_mean_z(c, ch, :, :));     % [freq x time]
    Z = imgaussfilt(Z, 1);
    imagesc(tms_ds, freqs, Z); axis xy;
    set(gca,'YScale','log'); ylim([min(freqs) max(freqs)]);
    xlabel('Time (ms)'); ylabel('Freq (Hz)');
    title(conds{c});
    colorbar; caxis([-2.5 2.5]);               % 统一色标
end
sgtitle(sprintf('Channel: %s (z to baseline)', chan_labels{ch}));

%% ===== (2) 条件差图：finish - cutoff =====
Zfin = squeeze(cond_mean_z(2, ch, :, :));
Zcut = squeeze(cond_mean_z(1, ch, :, :));
dZ   = Zfin - Zcut;
dZs = imgaussfilt(dZ, 1);

figure('Name','Finish - Cutoff');
imagesc(tms_ds, freqs, dZs); axis xy; set(gca,'YScale','log');
xlabel('Time (ms)'); ylabel('Freq (Hz)');
title('Finish - Cutoff (z difference)');
colorbar; caxis([-1.5 1.5]);

%% ===== (3) 频段时间课程（平滑+95%CI，图例只显示曲线） =====
% 参数
smooth_ms  = 200;           % 平滑窗口（毫秒）
alpha_band = [8 12];
beta_band  = [13 30];
gamma_band = [40 80];
band_edges = [alpha_band; beta_band; gamma_band];
bands      = {'alpha','beta','gamma'};

% 条件掩码
cond_mask = {is_cut, is_fin};
cond_name = {'cutoff','finish'};

% 频段掩码
ix_alpha = freqs >= alpha_band(1) & freqs <= alpha_band(2);
ix_beta  = freqs >= beta_band(1)  & freqs <= beta_band(2);
ix_gamma = freqs >= gamma_band(1) & freqs <= gamma_band(2);
band_ixs = {ix_alpha, ix_beta, ix_gamma};

% 平滑窗口点数
dt_ms  = mean(diff(tms_ds));
win_pts = max(1, round(smooth_ms / dt_ms));
if mod(win_pts,2) == 0, win_pts = win_pts + 1; end  % 用奇数窗

figure('Name','Band-limited time courses (smoothed, 95% CI) - bin2');
for b = 1:3
    subplot(3,1,b); hold on; grid on;

    % 标题直接用 band_edges 简写
    title(sprintf('%s band (%.0f–%.0f Hz),  smooth=%d ms', ...
        bands{b}, band_edges(b,1), band_edges(b,2), smooth_ms));

    hLines = gobjects(1,2); li = 0;   % 收集曲线句柄用于图例
    for c = 1:2
        mask = cond_mask{c};
        if ~any(mask), continue; end

        % trial × time：先在 freq 上均值 -> 每个 trial 的时间课程
        Ztc = squeeze(mean(z_power_ds(mask, ch, band_ixs{b}, :), 3, 'omitnan')); % [trial x time]

        % 逐 trial 平滑（移动平均）
        Ztc_s = smoothdata(Ztc, 2, 'movmean', win_pts);

        % 均值与 95% CI（t分布）
        m   = mean(Ztc_s, 1, 'omitnan');
        n   = sum(~any(isnan(Ztc_s),2));
        sd  = std(Ztc_s, 0, 1, 'omitnan');
        se  = sd ./ max(1, sqrt(n));
        tcr = tinv(0.975, max(n-1,1));
        ci  = tcr * se;

        x  = tms_ds(:)'; y1 = m - ci; y2 = m + ci;

        % 阴影：不进入图例
        hFill = fill([x fliplr(x)], [y1 fliplr(y2)], 'k', ...
                     'FaceAlpha', 0.15, 'EdgeColor', 'none');
        set(hFill, 'HandleVisibility','off');

        % 线型区分两条件
        ls = {'-','--'};  % cutoff实线，finish虚线
        li = li + 1;
        hLines(li) = plot(x, m, 'LineWidth', 1.8, 'LineStyle', ls{c}, ...
                          'DisplayName', cond_name{c});
    end

    yline(0,'k:'); xline(0,'k:');
    xlabel('Time (ms)'); ylabel('z');

    % 图例只显示曲线
    hLines = hLines(hLines~=0);
    if ~isempty(hLines)
        legend(hLines, 'Location','best');
    end
end

sgtitle(sprintf('Channel: %s', ch_label));
