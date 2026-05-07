%% ====== 0) 你需要改的两行 ======
brainnet_dir = "/Applications/BrainNetViewer_20191031";           % 改成你的 BrainNetViewer 文件夹
node_file    = "../电极定位/total.node";          % 改成你的 .node
out_dir      = "../图图";              % 输出文件夹（不存在会创建）

%% ====== 0.5) 根据 label 重编码模块编号（第4列）======
% 规则：label含 amygdala -> 2；含 hippocampus -> 3；含 fusiform -> 4；否则 1
% 输出新 node：*_relabel.node

[node_dir, node_base, node_ext] = fileparts(node_file);
node_file2 = fullfile(node_dir, node_base + "_relabel" + node_ext);

fid = fopen(node_file, 'r');
assert(fid>0, "打不开 node 文件：%s", node_file);

% 读 6 列：x y z (col4 int) (col5 float) label
C = textscan(fid, '%f%f%f%d%f%s', 'Delimiter', '\t');
fclose(fid);

X = C{1}; Y = C{2}; Z = C{3};
col4 = C{4};          % 这里将被重写
col5 = C{5};          % size（保持不变）
lab  = lower(string(C{6}));   % 统一转小写，便于 contains

newID = ones(numel(lab),1);        % 默认 1
newID(contains(lab, "amygdala"))     = 2;
newID(contains(lab, "hippocampus"))  = 3;
newID(contains(lab, "fusiform"))     = 4;

% 写出新 node（第4列写 newID，第5列保持原 col5）
fid = fopen(node_file2, 'w');
assert(fid>0, "无法写入：%s", node_file2);

for i = 1:numel(X)
    fprintf(fid, "%.3f\t%.3f\t%.3f\t%d\t%.3f\t%s\n", ...
        X(i), Y(i), Z(i), newID(i), col5(i), char(C{6}(i)));
end
fclose(fid);

fprintf("Re-labeled node saved: %s\n", node_file2);

% 用新 node 来画
node_file = node_file2;

%% ====== 1) 初始化 ======
addpath(genpath(brainnet_dir));
if ~exist(out_dir, "dir"), mkdir(out_dir); end

% 选择一个 MNI/ICBM152 的脑表面（按你本地 BrainNet 自带文件为准）
mesh_candidates = [
    fullfile(brainnet_dir, "Data", "SurfTemplate", "BrainMesh_ICBM152_smoothed.nv")
    fullfile(brainnet_dir, "Data", "SurfTemplate", "BrainMesh_ICBM152.nv")
    fullfile(brainnet_dir, "Data", "SurfTemplate", "BrainMesh_MNI152.nv")
    fullfile(brainnet_dir, "BrainMesh_ICBM152_smoothed.nv")
    fullfile(brainnet_dir, "BrainMesh_ICBM152.nv")
];
mesh_file = "";
for k = 1:numel(mesh_candidates)
    if isfile(mesh_candidates(k))
        mesh_file = mesh_candidates(k);
        break;
    end
end
assert(strlength(mesh_file)>0, "没找到 ICBM/MNI 的 .nv 表面文件，请检查 BrainNet 路径或模板位置。");

%% ====== 2) 调用 BrainNet 绘图（无 edge，用 []）=====
% 这里用 BrainNet_MapCfg（大多数版本都有）
hFig = figure("Color","w", "Name","BrainNet Node Render");


BrainNet_MapCfg(char(mesh_file), char(node_file), '');

% 稍微等渲染稳定（避免导出黑图）
drawnow;

%% ====== 3) 一些常用美化（能用就用，用不了就跳过）=====
ax = gca;
axis(ax, "off");
material(ax, "dull");
lighting(ax, "gouraud");
camlight("headlight");

%% ====== 4) 导出多视角 PNG ======
views = struct( ...
    "RightLateral", [  90,  0], ...  % 右侧外侧
    "LeftLateral",  [ -90,  0], ...  % 左侧外侧
    "Dorsal",       [   0, 90], ...  % 顶视
    "Posterior",    [ 180,  0] ...   % 后视
);

names = fieldnames(views);
for i = 1:numel(names)
    v = views.(names{i});
    view(v(1), v(2));
    drawnow;

    out_png = fullfile(out_dir, "node_" + names{i} + ".png");
    exportgraphics(gcf, out_png, "Resolution", 300);
    fprintf("Saved: %s\n", out_png);
end

%% ====== 5) 可选：导出一个 .fig 便于你手动在 GUI 里继续调 ======
savefig(gcf, fullfile(out_dir, "brainnet_node_render.fig"));
disp("Done.");
