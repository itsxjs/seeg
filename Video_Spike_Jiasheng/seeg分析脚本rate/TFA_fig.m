function batch_plot_channels_like_dislike()
%% ====== 配置：被试与通道 ======
subj_channels = struct();
subj_channels.sub001 = {'POL B1','C2-Ref','C3-Ref'};
subj_channels.sub004 = {'POL B1','POL B2','POL B3','POL B4','C2-Ref','C3-Ref','C4-Ref'};
subj_channels.sub007 = {'POL B4','POL B2','C4-Ref','C3-Ref','F2-Ref','F3-Ref'};
subj_channels.sub008 = {'POL B1','POL B2','C1-Ref','C2-Ref','C3-Ref'};
subj_channels.sub009 = {'POL B2','POL B3'};

data_dir = '/Users/defanive/Desktop/Diploma/seeg分析脚本rate'; % 你的 mat 文件目录
out_dir  = fullfile(data_dir, 'SingleChannel_LikeDislike_QC');
if ~exist(out_dir, 'dir'), mkdir(out_dir); end

%% ====== 加载 group LME 结果（用于叠簇与簇ROI）======
L = load(fullfile(data_dir, 'LME_CBPT_2D_like_dislike_FreqTime.mat')); % 改成你的文件名
res = L.res;
sig = res.h_pref;  % [freq x time]

% 两个显著簇（来自你打印的结果）
roi(1).name = 'Cluster5_LF';
roi(1).f = [1.00 7.82];
roi(1).t = [600 1100];
roi(1).dir = 'DISLIKE > LIKE';

roi(2).name = 'Cluster6_Broad';
roi(2).f = [1.00 48.71];
roi(2).t = [1150 1950];
roi(2).dir = 'LIKE > DISLIKE';

% 可选：更可解释的高频ROI（同时间窗）
roi(3).name = 'HFA_30_80';
roi(3).f = [30 80];
roi(3).t = [1150 1950];
roi(3).dir = 'exploratory';

%% ====== 绘图参数 ======
smooth_ms = 200;
ls = {'-','--'}; % dislike 实线，like 虚线
cond_name = {'dislike','like'};

%% ====== 批量循环 ======
subs = fieldnames(subj_channels);
for i = 1:numel(subs)
    sid = subs{i};                       % e.g. 'sub001'
    ch_list = subj_channels.(sid);

    matfile = fullfile(data_dir, sprintf('%s_valence_TF_zpower.mat', sid));
    if ~isfile(matfile)
        warning('File not found: %s (skip)', matfile);
        continue;
    end

    S = load(matfile, '-mat');

    % 必需变量检查
    req = {'z_power_ds','cond_mean_z','freqs','tms_ds','chan_labels','is_dislike','is_like'};
    for k = 1:numel(req)
        if ~isfield(S, req{k})
            warning('%s missing %s (skip file)', matfile, req{k});
            continue;
        end
    end

    freqs = S.freqs(:);
    tms_ds = S.tms_ds(:);
    chan_labels = S.chan_labels(:);

    % 对齐检查（sig 来自 group LME）
    if size(sig,1) ~= numel(freqs) || size(sig,2) ~= numel(tms_ds)
        warning('Axis mismatch for %s: sig(%dx%d) vs freqs(%d) tms(%d). Skip plotting clusters.', ...
            sid, size(sig,1), size(sig,2), numel(freqs), numel(tms_ds));
        sig_use = [];
    else
        sig_use = sig;
    end

    % 平滑窗点数
    dt_ms  = mean(diff(tms_ds));
    win_pts = max(1, round(smooth_ms / dt_ms));
    if mod(win_pts,2) == 0, win_pts = win_pts + 1; end

    fprintf('\n[%s] dislike=%d, like=%d\n', sid, sum(S.is_dislike), sum(S.is_like));

    n_dis = sum(S.is_dislike);
    n_like = sum(S.is_like);
    
    % ===== 被试合法性判定 =====
    min_trials_per_cond = 3;   % 你可以改成 5/8，更严格
    if n_dis < min_trials_per_cond || n_like < min_trials_per_cond
        warning('[%s] INVALID subject: dislike=%d, like=%d (<%d). Skip subject.', ...
            sid, n_dis, n_like, min_trials_per_cond);
        continue;
    end

    for j = 1:numel(ch_list)
        ch_label = ch_list{j};
        ch = find(strcmp(chan_labels, ch_label), 1);
        if isempty(ch)
            warning('[%s] channel not found: %s (skip)', sid, ch_label);
            continue;
        end

        % ------- 生成图：每个通道一个 figure，包含 2 行 × 3 列 -------
        % Row1: dislike TFR | like TFR | diff (like-dislike)
        % Row2: Cluster5 TC | Cluster6 TC | HFA TC(可选/也画)
        fig = figure('Visible','off','Position',[60 60 1500 800]);
        sgtitle(sprintf('%s | %s', sid, ch_label), 'Interpreter','none');

        % ===== Row 1 - TFRs =====
        for c = 1:2
            subplot(2,3,c);
            Z = squeeze(S.cond_mean_z(c, ch, :, :));
            Z = imgaussfilt(Z, 1);
            imagesc(tms_ds, freqs, Z); axis xy;
            set(gca,'YScale','log'); ylim([min(freqs) max(freqs)]);
            xlabel('Time (ms)'); ylabel('Freq (Hz)');
            title(sprintf('%s TFR', cond_name{c}));
            colorbar; caxis([-2.5 2.5]);

            if ~isempty(sig_use)
                hold on;
                contour(tms_ds, freqs, double(sig_use), [0.5 0.5], 'LineColor','k','LineWidth',1.2);
            end
        end

        % diff
        subplot(2,3,3);
        Zdis = squeeze(S.cond_mean_z(1, ch, :, :));
        Zlik = squeeze(S.cond_mean_z(2, ch, :, :));
        dZ   = imgaussfilt(Zlik - Zdis, 1);
        imagesc(tms_ds, freqs, dZ); axis xy; set(gca,'YScale','log');
        xlabel('Time (ms)'); ylabel('Freq (Hz)');
        title('Like - Dislike');
        colorbar; caxis([-1.5 1.5]);

        if ~isempty(sig_use)
            hold on;
            contour(tms_ds, freqs, double(sig_use), [0.5 0.5], 'LineColor','k','LineWidth',1.8);
        end

        % ===== Row 2 - Cluster-driven time courses =====
        cond_mask = {S.is_dislike, S.is_like};
        for r = 1:3
            subplot(2,3,3+r); hold on; grid on;

            ix_f = freqs >= roi(r).f(1) & freqs <= roi(r).f(2);
            ttl = sprintf('%s | %.2f–%.2f Hz | %d–%d ms | %s', ...
                roi(r).name, roi(r).f(1), roi(r).f(2), roi(r).t(1), roi(r).t(2), roi(r).dir);
            title(ttl, 'Interpreter','none');

            hLines = gobjects(1,2); li = 0;
            for c = 1:2
                mask = cond_mask{c};
                if ~any(mask), continue; end

                Ztc = squeeze(mean(S.z_power_ds(mask, ch, ix_f, :), 3, 'omitnan')); % [trial x time]
                Ztc_s = smoothdata(Ztc, 2, 'movmean', win_pts);

                m  = mean(Ztc_s, 1, 'omitnan');
                n  = size(Ztc_s,1);
                sd = std(Ztc_s, 0, 1, 'omitnan');
                se = sd ./ max(1, sqrt(n));
                tcr = tinv(0.975, max(n-1,1));
                ci  = tcr * se;

                x  = tms_ds(:)';
                y1 = m - ci; y2 = m + ci;

                hFill = fill([x fliplr(x)], [y1 fliplr(y2)], 'k', ...
                    'FaceAlpha', 0.12, 'EdgeColor','none');
                set(hFill, 'HandleVisibility','off');

                li = li + 1;
                hLines(li) = plot(x, m, 'LineWidth', 1.6, 'LineStyle', ls{c}, ...
                    'DisplayName', cond_name{c});
            end

            % highlight time window
            yl = ylim;
            patch([roi(r).t(1) roi(r).t(2) roi(r).t(2) roi(r).t(1)], ...
                  [yl(1) yl(1) yl(2) yl(2)], 'k', ...
                  'FaceAlpha', 0.06, 'EdgeColor','none', 'HandleVisibility','off');

            yline(0,'k:'); xline(0,'k:');
            xlabel('Time (ms)'); ylabel('z');

            hLines = hLines(hLines~=0);
            if ~isempty(hLines), legend(hLines,'Location','best'); end
        end

        % ------- 保存 -------
        safe_ch = regexprep(ch_label, '[^\w\-]', '_');
        out_png = fullfile(out_dir, sprintf('%s_%s_likeDislike.png', sid, safe_ch));
        exportgraphics(fig, out_png, 'Resolution', 200);
        close(fig);

        fprintf('Saved: %s\n', out_png);
    end
end

fprintf('\nDone. Output folder: %s\n', out_dir);
end
