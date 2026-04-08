function fig = plot_coherence_fig4A_style(C_tf, time_vec_sec, freq_vec_hz, title_str, clim, smooth_cfg, interp_factor)
% plot_coherence_fig4A_style
% 增强版：可选 display-level smoothing + 可选插值（仅用于显示）
%
% 输入：
%   C_tf: [nFreq x nTimeWin]
%   smooth_cfg: struct('do',true,'t_span',5,'f_span',3)  % 高斯平滑核长度(点数)
%   interp_factor: e.g., 4  % 时间/频率网格插值倍数（仅显示）

if nargin < 5 || isempty(clim); clim = []; end
if nargin < 6 || isempty(smooth_cfg)
    smooth_cfg = struct('do',false,'t_span',5,'f_span',3);
end
if nargin < 7 || isempty(interp_factor)
    interp_factor = 1;
end

C_plot = C_tf;

% --- 1) 平滑（仅显示）---
if isfield(smooth_cfg,'do') && smooth_cfg.do
    t_span = smooth_cfg.t_span; % 时间方向核长度（点）
    f_span = smooth_cfg.f_span; % 频率方向核长度（点）
    C_plot = smoothdata(C_plot, 2, 'gaussian', t_span); % time dim=2
    C_plot = smoothdata(C_plot, 1, 'gaussian', f_span); % freq dim=1
end

% --- 2) 插值让图更"细腻"（仅显示）---
if interp_factor > 1
    t_new = linspace(time_vec_sec(1), time_vec_sec(end), numel(time_vec_sec)*interp_factor);
    f_new = linspace(freq_vec_hz(1),  freq_vec_hz(end),  numel(freq_vec_hz)*interp_factor);
    [TT, FF]   = meshgrid(time_vec_sec, freq_vec_hz);
    [TT2, FF2] = meshgrid(t_new, f_new);
    C_plot = interp2(TT, FF, C_plot, TT2, FF2, 'linear');
    time_plot = t_new;
    freq_plot = f_new(:);
else
    time_plot = time_vec_sec;
    freq_plot = freq_vec_hz(:);
end

fig = figure('Color','w','Position',[100 100 520 420]);

[TTp, FFp] = meshgrid(time_plot, freq_plot);
surf(TTp, FFp, C_plot, 'EdgeColor','none');
view(2); axis tight;
xlabel('Time (s)');
ylabel('Frequency (Hz)');
title(title_str, 'Interpreter','none');

set(gca, 'YScale','log');
yticks([2 4 8 16 32 45]);
ylim([min(freq_plot) max(freq_plot)]);

cb = colorbar;
cb.Label.String = 'Coherence';

if ~isempty(clim)
    caxis(clim);
end

set(gca, 'LineWidth', 1, 'FontSize', 11);
end
