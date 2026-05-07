%% make_total_selected_nodes.m
% 把 ../电极定位/sub00?.tsv 汇总成 total.node，并筛出 amygdala/hippocampus/fusiform 到 selected.node
clear; clc;

in_dir = "../电极定位";

total_node = fullfile(in_dir, "total.node");
selected_node = fullfile(in_dir, "selected.node");

regionCol = "Desikan_Killiany";   % 与你函数保持一致
nodeSize = 1;                     % 统一点大小（写在第5列）

keywords = ["amygdala","hippocampus","fusiform"];  % 小写匹配
subjects = ["Sub001", "Sub004", "Sub005", "Sub007", "Sub008", "Sub009"];

files_all = dir(fullfile(in_dir, "*.tsv"));

files = files_all( ...
    ismember( ...
        erase({files_all.name}, ".tsv"), ...
        subjects ...
    ) ...
);
% 全局脑区 -> colorID 映射（保证跨被试一致）
region2id = containers.Map('KeyType','char','ValueType','int32');
next_id = int32(1);

% 打开输出文件
fid_all = fopen(total_node, "w");
assert(fid_all>0, "无法写入：%s", total_node);

fid_sel = fopen(selected_node, "w");
assert(fid_sel>0, "无法写入：%s", selected_node);

n_all = 0;
n_sel = 0;

for f = 1:numel(files)
    tsvPath = fullfile(files(f).folder, files(f).name);
    [~, subID, ~] = fileparts(files(f).name);  % sub001 之类

    T = readtable(tsvPath, "FileType","text", "Delimiter","\t");

    needCols = ["Channel","MNI", regionCol];
    for c = needCols
        if ~ismember(c, string(T.Properties.VariableNames))
            error("文件 %s 缺少列：%s", tsvPath, c);
        end
    end

    Channel = string(T.Channel); Channel(ismissing(Channel)) = "NA";
    Region  = string(T.(regionCol)); Region(ismissing(Region)) = "Unknown";

    XYZ = parse_bracket_xyz(string(T.MNI));
    X = XYZ(:,1); Y = XYZ(:,2); Z = XYZ(:,3);

    % 逐行写出
    for i = 1:height(T)
        reg = Region(i);
        reg_key = char(reg);  % Map 用 char key

        if ~isKey(region2id, reg_key)
            region2id(reg_key) = next_id;
            next_id = next_id + 1;
        end
        colorID = region2id(reg_key);

        label = sanitize_label(subID + "_" + Channel(i) + "_" + reg);

        % —— total.node：6列（x y z colorID nodeSize label）——
        fprintf(fid_all, "%.3f\t%.3f\t%.3f\t%.3f\t%d\t%s\n", ...
            X(i), Y(i), Z(i), double(colorID), nodeSize, char(label));
        n_all = n_all + 1;

        % —— selected.node：包含关键词的行 ——（用 Region 判断最稳）
        reg_low = lower(reg);
        if any(contains(reg_low, keywords))
            fprintf(fid_sel, "%.3f\t%.3f\t%.3f\t%.3f\t%d\t%s\n", ...
                X(i), Y(i), Z(i), double(colorID), nodeSize, char(label));
            n_sel = n_sel + 1;
        end
    end
end

fclose(fid_all);
fclose(fid_sel);

fprintf("Wrote total:    %s   (%d nodes)\n", total_node, n_all);
fprintf("Wrote selected: %s   (%d nodes)\n", selected_node, n_sel);

%% ===== helper: parse "[x,y,z]" =====
function XYZ = parse_bracket_xyz(S)
S = strtrim(string(S));
S = erase(S, ["[","]"]);
S = replace(S, " ", "");
parts = split(S, ",");
XYZ = nan(numel(S),3);

if size(parts,2) == 3
    XYZ = str2double(parts);
else
    for ii = 1:numel(S)
        nums = regexp(S(ii), '[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', 'match');
        if numel(nums) >= 3
            XYZ(ii,:) = str2double(nums(1:3));
        else
            error("MNI 解析失败：%s", S(ii));
        end
    end
end
end

%% ===== helper: BrainNet-safe label =====
function s = sanitize_label(s)
s = string(s);
s(ismissing(s) | strlength(s)==0) = "NA";
s = regexprep(s, '\s+', '_');          % 空白 -> _
s = regexprep(s, '[^\w\-.]', '_');     % 其他奇怪符号 -> _
s = regexprep(s, '_{2,}', '_');        % 多个 _ 压缩
s = regexprep(s, '^_+|_+$', '');       % 去首尾 _
end
