%%
clear all; close all;
dbstop if error

%%
% If not save .mat file, it's recommended to return the raw_data and
% spike_data to workspace.
% If convert multiple files, it's recommended not to return the raw_data
% or spike_data to workspace, otherwise it only returns for the last file.

save_flag = 1; % 1 -- .mat file saved, 0 -- .mat file not saved
% output_path = '/develop/data/Other_Group/HARDWARE/打标数量检测/同步位分析-同时打标&原始信号-250807/切换界面同时，切换高低电平/20250807-150331/';
% output_path = '/develop/data/SEEG/浙二/0103/';
% output_path = '/develop/data/SEEG/kongzong/0101/';
% output_path = '/develop/data/SEEG/jidasan/0101/';
% output_path = '/develop/data/SEEG/浙二/0101/';
output_path = '/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330';

if isdir(output_path)
    mkdir(output_path);
end

%% list all raw and spk files from given dirs
dirs = {...
        '/Volumes/rmhyw/单剑锋spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/';...
        };
[filenames_raw, filenames_spk] = deal({});

for dirind = 1:length(dirs)
    raw_files = dir([dirs{dirind} '*.raw']);
    filenames_raw = cat(2, filenames_raw, strcat({raw_files.folder}, '/', {raw_files.name}));
    
    spk_files = dir([dirs{dirind} '*.spk']);
    filenames_spk = cat(2, filenames_spk, strcat({spk_files.folder}, '/', {spk_files.name}));
    
    dir_files = dir([dirs{dirind}]);
    subdirs = dir_files(~cellfun(@(x) contains(x, '.'), {dir_files.name}, 'un', 1));

    for subdirind = 1:length(subdirs)
        raw_files = dir([subdirs(subdirind).folder filesep subdirs(subdirind).name filesep '*.raw']);
        filenames_raw = cat(2, filenames_raw, strcat({raw_files.folder}, '/', {raw_files.name}));

        spk_files = dir([subdirs(subdirind).folder filesep subdirs(subdirind).name filesep '*.spk']);
        filenames_spk = cat(2, filenames_spk, strcat({spk_files.folder}, '/', {spk_files.name}));
    end
end

%% list all path/file.raw files you would like to convert in the cell
% filenames_raw = {...
%                 '/mnt/diskB/NetBakData/11431@魏愷含/Disk D/record/20241202/ZE-EPI-NC-20241202-2027/ZE-EPI-NC-20241202-2027_1.raw';...
%                  };
tic
% raw_data = read_raw(filenames_raw, save_flag);
% raw_data = read_raw(filenames, save_flag, output_path); % return
read_raw(filenames_raw, save_flag, output_path); % no return
toc

%% list all path/file.spk files you would like to convert in the cell
% filenames = {'/mnt/diskB/NetBakData/25959@SHAWN/Disk D/record/20241207/ZE-EPI-REST-20241207-0954/ZE-EPI-REST-20241207-0954.spk'};
tic
% spike_data = read_spike(filenames, save_flag, output_path); % return
read_spike(filenames_spk, save_flag, output_path); % no return
toc

%% 
% filenames = {'/mnt/diskB/NetBakData/yuanmou@YUANMOUBAB7/Disk E/record/0103/ZR-JLF-20250914/20250914-163548/yc20250914-1635.raw';...
%              };
tic
% read_impedance(filenames, save_flag, output_path);
read_impedance(filenames_raw(1), save_flag, output_path);
toc
