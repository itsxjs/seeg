function tsv2node(tsvPath, nodePath)
% tsv2node
% 将 TSV（MNI="[x,y,z]"）转换为 BrainNet 可用 node
%
% 输出：
%   nodePath                 : 6列 node（含 label，label 无空格）
%   [nodePath '_5col.node']  : 5列 node（不含 label，最稳）

%% ===== 配置 =====
regionCol = "Desikan_Killiany";   % 你当前用的脑区列
nodeSize  = 1;                  % 🔥 全部点统一大小

%% ===== 读 TSV =====
T = readtable(tsvPath, "FileType","text", "Delimiter","\t");

% 必要列检查
needCols = ["Channel","MNI", regionCol];
for c = needCols
    if ~ismember(c, string(T.Properties.VariableNames))
        error("缺少列：%s", c);
    end
end

Channel = string(T.Channel);
Channel(ismissing(Channel)) = "NA";

Region = string(T.(regionCol));
Region(ismissing(Region)) = "Unknown";

%% ===== 解析 MNI =====
XYZ = parse_bracket_xyz(string(T.MNI));
X = XYZ(:,1); Y = XYZ(:,2); Z = XYZ(:,3);

%% ===== 颜色编号（按脑区 stable）=====
[regionCats, ~, colorID] = unique(Region, "stable");

%% ===== label（Channel + Region，完全 BrainNet-safe）=====
label = sanitize_label(Channel + "_" + Region);

%% ===== 写 6 列 node =====
fid = fopen(nodePath, "w");
assert(fid > 0, "无法写入: %s", nodePath);

for i = 1:height(T)
    fprintf(fid, "%.3f\t%.3f\t%.3f\t%.3f\t%d\t%s\n", ...
        X(i), Y(i), Z(i), colorID(i), nodeSize, char(label(i)));
end
fclose(fid);

%% ===== 写 5 列 node（不带 label，最稳）=====
[p, f, e] = fileparts(nodePath);
nodePath5 = fullfile(p, f + "_5col" + e);

fid = fopen(nodePath5, "w");
assert(fid > 0, "无法写入: %s", nodePath5);

for i = 1:height(T)
    fprintf(fid, "%.3f\t%.3f\t%.3f\t%.3f\t%d\n", ...
        X(i), Y(i), Z(i), colorID(i), nodeSize);
end
fclose(fid);

%% ===== 打印脑区-颜色对照 =====
disp("=== Region -> colorID（stable）===");
for k = 1:numel(regionCats)
    fprintf("%3d  %s\n", k, sanitize_label(regionCats(k)));
end

fprintf("Wrote node:  %s\n", nodePath);
fprintf("Wrote node5: %s\n", nodePath5);

end

%% ---------- helper: parse "[x,y,z]" ----------
function XYZ = parse_bracket_xyz(S)
S = erase(S, ["[","]"]);
S = replace(S, " ", "");
parts = split(S, ",");
XYZ = nan(numel(S),3);

if size(parts,2) == 3
    XYZ = str2double(parts);
else
    for i = 1:numel(S)
        nums = regexp(S(i), '[-+]?\d*\.?\d+', 'match');
        XYZ(i,:) = str2double(nums(1:3));
    end
end
end

%% ---------- helper: make label BrainNet-safe ----------
function s = sanitize_label(s)
s = string(s);
s(ismissing(s) | strlength(s)==0) = "NA";

% 所有空白 → _
s = regexprep(s, '\s+', '_');

% 非字母数字/下划线/.- → _
s = regexprep(s, '[^\w\-.]', '_');

% 多余下划线压缩
s = regexprep(s, '_{2,}', '_');

% 去首尾 _
s = regexprep(s, '^_+|_+$', '');
end
