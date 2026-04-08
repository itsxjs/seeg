%% Kilosort Binary Export Script (SEEG Concatenation)
% 目标：将分段的 .mat 文件拼接并转换为 Kilosort 所需的 .bin 文件

clear; clc;

% --- 配置参数 ---
% 获取当前 mat 文件所在的目录
dataDir = '/Users/defanive/Desktop/Diploma/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-CE-20241208-1107/'; 
% 定义输出文件名
binName = 'concatenated_raw_data.bin';
% 拼接完整输出路径，确保写在 dataDir 里
outputFilePath = fullfile(dataDir, binName);

dataType = 'int16'; % Kilosort 推荐类型

% --- 获取并筛选文件 ---
allMatFiles = dir(fullfile(dataDir, '*.mat'));
allNames = {allMatFiles.name};

% 核心筛选逻辑：
% 1. 必须以 'tiktok3' 开头
% 2. 不包含 'spike', 'impedance', 'spk' 等字样 [cite: 54, 55]
% 3. 符合原始数据命名规约 
%isRawData = strncmp(allNames, 'tiktok', 6) & ~contains(allNames, {'spike', 'impedance', 'spk'});
isRawData = ~contains(allNames, {'spike', 'impedance', 'spk'});
targetFiles = allNames(isRawData);

% --- 逻辑排序 ---
% 按照说明书：无后缀排第一，_1, _2... 随后 
fileIndices = zeros(size(targetFiles));
for i = 1:length(targetFiles)
    tokens = regexp(targetFiles{i}, '_(\d+)\.mat$', 'tokens');
    if isempty(tokens)
        fileIndices(i) = 0; % 主文件
    else
        fileIndices(i) = str2double(tokens{1}{1});
    end
end

[~, sortOrder] = sort(fileIndices);
sortedFiles = targetFiles(sortOrder);

% --- 输出核对 ---
fprintf('目标目录：%s\n', dataDir);
fprintf('检测到 %d 个原始数据文件，拼接顺序如下：\n', length(sortedFiles));
for i = 1:length(sortedFiles)
    fprintf(' [%d] %s\n', i, sortedFiles{i});
end

if isempty(sortedFiles)
    error('未检测到符合条件的原始数据文件，请检查文件名。');
end

% --- 流式写入 ---
% 使用 'wb' 模式打开，确保结果写到 dataDir 下
fid = fopen(outputFilePath, 'wb');
if fid == -1, error('无法在目标目录创建文件，请检查权限。'); end

try
    for i = 1:length(sortedFiles)
        currentFile = fullfile(dataDir, sortedFiles{i});
        fprintf('正在处理 (%d/%d): %s...\n', i, length(sortedFiles), sortedFiles{i});
        
        % 动态加载 data 字段 [cite: 63, 64]
        % 使用 '-mat' 明确指定格式，避免读取错误
        S = load(currentFile, 'data', '-mat');
        
        % 写入二进制文件
        % MATLAB 的 data 维度是 [通道数 x 时间点] [cite: 63, 64]
        % 按照列优先写入，磁盘布局为: T1(Ch1, Ch2...), T2(Ch1, Ch2...)
        fwrite(fid, S.data, dataType);
        
        clear S; % 内存安全：及时释放当前块，防止 18GB 内存溢出再次发生
    end
    fclose(fid);
    fprintf('\n转换成功！\n最终文件已保存至：%s\n', outputFilePath);
catch ME
    if exist('fid','var'), fclose(fid); end
    rethrow(ME);
end