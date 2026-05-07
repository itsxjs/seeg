load('Sub004_valence_TF_zpower.mat');  % 改成你的文件名
ch = find(strcmp(chan_labels,'POL D2'));   % 选通道；没有Fz就换你感兴趣的

figure('Name','TFR per condition');
conds = {'neg','neu','pos'};
for c = 1:3
    subplot(3,1,c);
    Z = squeeze(cond_mean_z(c, ch, :, :));     % [freq x time]
    Z = imgaussfilt(Z, 1);                     % ⭐ 新增平滑
    imagesc(tms_ds, freqs, Z); axis xy;
    set(gca,'YScale','log'); ylim([min(freqs) max(freqs)]);
    xlabel('Time (ms)'); ylabel('Freq (Hz)');
    title(conds{c});
    colorbar; caxis([-2.5 2.5]);
end
sgtitle(sprintf('Channel: %s (z to baseline)', chan_labels{ch}));

Zpos = squeeze(cond_mean_z(3, ch, :, :));
Zneg = squeeze(cond_mean_z(1, ch, :, :));
dZ   = Zpos - Zneg;


dZs = imgaussfilt(dZ, 1);   % 第二个参数是平滑强度 sigma，通常取 0.5~2 之间
figure('Name','Pos - Neg');
imagesc(tms_ds, freqs, dZs);
axis xy; set(gca,'YScale','log');
xlabel('Time (ms)'); ylabel('Freq (Hz)');
title('Positive - Negative (z difference, smoothed)');
colorbar; caxis([-1.5 1.5]);



% 频段索引
ix_alpha = freqs>=8 & freqs<=12;
ix_beta  = freqs>=13 & freqs<=30;
ix_gamma = freqs>=40 & freqs<=80;

% 各条件 trial 级再平均（更稳）：也可直接用 cond_mean_z
cond_mask = {is_neg, is_neu, is_pos};
labels    = {'neg','neu','pos'};

figure('Name','Band-limited time courses'); 
bands = {'alpha','beta','gamma'};
ixs   = {ix_alpha, ix_beta, ix_gamma};

for b = 1:3
    subplot(3,1,b); hold on;
    for c = 1:3
        % trial × time：对所选频段、当前通道先在 freq 上均值
        Ztc = squeeze(mean(z_power_ds(cond_mask{c}, ch, ixs{b}, :), 3, 'omitnan')); % [trial x time]
        plot(tms_ds, mean(Ztc,1,'omitnan'), 'LineWidth',1.5);
    end
    yline(0,'k:'); xline(0,'k:');
    title([bands{b} ' band']); xlabel('Time (ms)'); ylabel('z');
    legend(labels, 'Location','best'); grid on;
end


% ==== 参数（按需修改）====
ch_label   = 'POL D2';   % 选择通道
smooth_ms  = 200;    % 平滑窗口（毫秒），建议 150~300 ms
alpha_band = [8 12];
beta_band  = [13 30];
gamma_band = [40 80];
band_edges = [alpha_band; beta_band; gamma_band];

% ==== 准备 ====
ch = find(strcmp(chan_labels, ch_label));
if isempty(ch), error('未找到通道 %s', ch_label); end

% 条件掩码
cond_mask = {is_neg, is_neu, is_pos};
cond_name = {'neg','neu','pos'};

% 频段掩码
ix_alpha = freqs >= alpha_band(1) & freqs <= alpha_band(2);
ix_beta  = freqs >= beta_band(1)  & freqs <= beta_band(2);
ix_gamma = freqs >= gamma_band(1) & freqs <= gamma_band(2);
bands = {'alpha','beta','gamma'};
band_ixs = {ix_alpha, ix_beta, ix_gamma};

% 时间平滑窗口（换算为采样点数）
% 你的 tms_ds 等间隔，间隔约为 ds_ms（例如 50 ms）
dt_ms = mean(diff(tms_ds));                 % 每个点代表的毫秒
win_pts = max(1, round(smooth_ms / dt_ms)); % 平滑点数
if mod(win_pts,2) == 0, win_pts = win_pts+1; end  % 用奇数窗更对称

% ==== 画图 ====
figure('Name','Band-limited time courses (smoothed, 95% CI)');
for b = 1:3
    subplot(3,1,b); hold on; grid on;
    title(sprintf('%s band (%.0f–%.0f HZ),  smooth=%d ms', ...
        bands{b}, band_edges(b,1), band_edges(b,2), smooth_ms));

    hLines = gobjects(1,3);   % 预分配
    for c = 1:3
        mask = cond_mask{c};
        if ~any(mask), continue; end
        % trial × time：先在频率维做均值 -> 每个 trial 的时间课程
        Ztc = squeeze(mean(z_power_ds(mask, ch, band_ixs{b}, :), 3, 'omitnan')); % [n_trial x n_time]

        % 逐 trial 在时间上平滑（移动平均）
        % 注：smoothdata 会对每行独立平滑
        Ztc_s = smoothdata(Ztc, 2, 'movmean', win_pts);

        % 计算均值和 95% CI（t 分布）
        m  = mean(Ztc_s, 1, 'omitnan');                      % [1 x time]
        n  = sum(~any(isnan(Ztc_s),2));                      % 有效 trial 数
        sd = std(Ztc_s, 0, 1, 'omitnan');
        se = sd ./ max(1, sqrt(n));
        tcrit = tinv(0.975, max(n-1,1));                     % 双侧95%
        ci = tcrit * se;

        % 画阴影 + 曲线
        % 选一种线型区分条件（不指定颜色，保持 MATLAB 默认配色）
        switch c
            case 1, ls='-';   % neg
            case 2, ls='--';  % neu
            case 3, ls='-.';  % pos
        end

        % 阴影
        x = tms_ds(:)';
        y1 = m - ci;
        y2 = m + ci;
        hFill = fill([x fliplr(x)], [y1 fliplr(y2)], 'k', ...
            'FaceAlpha', 0.15, 'EdgeColor', 'none'); %#ok<NASGU>
        % 再画均值曲线（置顶）
        hFill.Annotation.LegendInformation.IconDisplayStyle = 'off';  % 方法1
        hLine = plot(x, m, 'LineWidth', 1.8, 'LineStyle', ls); %#ok<NASGU>
    end

    yline(0,'k:'); xline(0,'k:');
    xlabel('Time (ms)'); ylabel('z');
    legend(cond_name, 'Location','best'); % 若想阴影不进图例，可手工指定 legend 只包含线条
end

sgtitle(sprintf('Channel: %s', ch_label));
