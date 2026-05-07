% 假设 EEG 已经在工作空间中
latencies = [EEG.event.latency];  % 所有事件时间
n_events = length(latencies);

newevent = [];  % 初始化结果，N×2，列1为type，列2为latency
free_index = 0;

% 遍历每个事件
for i = 1:n_events
    current_latency = latencies(i);

    % 如果已有事件在200ms内，跳过
    if ~isempty(newevent)
        if mod(i, 2) == 0 
            continue;
        end
        if size(newevent,2) >= 2 && any(abs(newevent(:,2) - current_latency) <= 200)
            continue;
        end
    end
    end
    
    % % 检查前3000ms内是否已有type==2的事件
    % recent_window_start = current_latency - 3000;
    % if ~isempty(newevent) && size(newevent,2) >= 2 && ...
    %         any(newevent(:,2) >= recent_window_start & newevent(:,2) < current_latency & newevent(:,1) <= 3)
    %     event_type = 5;
    % else
    %     scene_index = scene_index + 1;
    %     if scene_index <= 120
    %         event_type = scenematrix(scene_index, 5);
    %     end
    % end
    free_index = free_index + 1;
    event_type = freematrix(free_index, 3);
    % 记录事件
    if free_index <= 88
        newevent = [newevent; event_type, current_latency];
    else
        newevent = [newevent; 99, current_latency];
    end
end

% 输出结果
disp(newevent);
EEG = pop_importevent( EEG, 'append','no','event', newevent ,'fields',{'type','latency'},'timeunit',NaN,'optimalign','off');
EEG = pop_eegfiltnew(EEG, 'locutoff',1,'plotfreqz',1);
EEG = pop_eegfiltnew(EEG, 'hicutoff',200,'plotfreqz',1);
EEG = pop_eegfiltnew(EEG, 'locutoff',49,'hicutoff',51,'revfilt',1,'plotfreqz',1);
EEG = pop_clean_rawdata(EEG, 'FlatlineCriterion',5,'ChannelCriterion',0.8,'LineNoiseCriterion',4,'Highpass','off','BurstCriterion',20,'WindowCriterion',0.25,'BurstRejection','on','Distance','Euclidian','WindowCriterionTolerances',[-Inf 7] );
EEG = pop_reref( EEG, []);
