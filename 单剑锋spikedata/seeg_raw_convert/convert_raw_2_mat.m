%%
% If not save .mat file, it's recommended to return the raw_data and 
% spike_data to workspace.
% If convert multiple files, it's recommended not to return the raw_data
% or spike_data to workspace, otherwise it only returns for the last file.

save_flag = 1; % 1 -- .mat file saved, 0 -- .mat file not saved

%% list all path/file.raw files you would like to convert in the cell
filenames = {'/Users/defanive/Desktop/Diploma/spikedata/视频-情绪记忆-spike数据/ZE-EPI-VE-20241202-1330/ZE-EPI-VE-20241202-1330.raw'};
tic
raw_data = read_raw(filenames, save_flag); % return
% read_raw(filenames, save_flag); % no return 
toc

%% list all path/file.spk files you would like to convert in the cell
filenames = {'/Users/defanive/Desktop/Diploma/姜芳丽spike_rate/tiktok3-20250908-1504.spk'};
tic
spike_data = read_spike(filenames, save_flag); % return
% read_spike(filenames, save_flag); % no return
toc
