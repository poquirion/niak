function [files_in,files_out,opt] = niak_brick_build_stack(files_in,files_out,opt)
% Create network, mean and std stack 4D maps from individual functional maps
%
% SYNTAX:
% [FILE_IN,FILE_OUT,OPT] = NIAK_BRICK_BUILD_STACK(FILE_IN,FILE_OUT,OPT)
% _________________________________________________________________________
%
% INPUTS:
%
% FILES_IN (structure) with the following fields :
%
%   MAP.<SUBJECT>
%       (string) Containing the individual map (e.g. rmap_part,stability_maps, etc)
%       NB: assumes there is only 1 .nii.gz or mnc.gz map per individual.
%
%   MASK
%       (3D volume) a binary mask of the voxels that will be included in the 
%       time*space array.
%
%   PHENO
%       (strings,Default '') a .csv files coding for the pheno
%
%
% FILES_OUT (string) the full path for a load_stack.mat file with the folowing variables :
%   
%   STACK_NET_<N> 4D volumes stacking networks for network N across individual maps  
%   MEAN_NET_<N>  4D volumes stacking networks for the mean networks across individual maps.
%   STD_NET_<N>   4D volumes stacking networks for the std networks across individual maps.
%
% OPT  (structure, optional) with the following fields:
%
%   SCALE (cell of integer,default all networks) A list of networks number 
%   in individual maps
%
%   REGRESS_CONF (Cell of string, Default {}) A liste of variables name to be regressed out.
%   WARNING: subject's ID should be the same as in the csv pheno file.
%   
%
%   FLAG_VERBOSE
%       (boolean, default true) turn on/off the verbose.
%
%   FLAG_TEST
%       (boolean, default false) if the flag is true, the brick does not do 
%       anything but updating the values of FILES_IN, FILES_OUT and OPT.
% _________________________________________________________________________
% OUTPUTS:
%
% The structures FILES_IN, FILES_OUT and OPT are updated with default
% valued. If OPT.FLAG_TEST == 0, the specified outputs are written.


%% Initialization and syntax checks

% Input
if ~isstruct(files_in)
    error('niak:brick','FILES_IN should be a structure.\n Type ''help niak_brick_build_stack'' for more info.');
end

if isempty(files_in.mask)
    error('niak:brick','Mask missing.\n Type ''help niak_brick_build_stack'' for more info.')
end
% Read mask
[hdr_m,mask] = niak_read_vol(files_in.mask);

% Output
if ~exist('files_out','var')||isempty(files_out)
    files_out = pwd;
end
if ~ischar(files_out)
    error('FILES_OUT should be a string');
end

% Options
if nargin < 3
    opt = struct;
end

list_fields   = { 'scale' , 'regress_conf' , 'flag_verbose' , 'flag_test' };
list_defaults = {  {}     ,  {}            ,  true          ,  false      };
opt = psom_struct_defaults(opt,list_fields,list_defaults);

% setup list of networks
if isempty(opt.scale)
   [hdr,vol]=niak_read_vol(files_in.map.(fieldnames(files_in.map){1}));
   list_network =  hdr.info.dimensions(end);
   list_network = [1 : list_network];
   opt.scale = num2cell(list_network);
else
   list_network = cell2mat(opt.scale);
end

% If the test flag is true, stop here !
if opt.flag_test == 1
    return
end

% The brick start here 
% Network 4D volumes with M subjects
for ss = list_network
    tseries = [];
    subj_id = '';
    fprintf('loading net_%d:\n',ss)
    for ii = 1:length(fieldnames(files_in.map))
        sub = fieldnames(files_in.map){ii};
        niak_progress(ii,length(fieldnames(files_in.map)),5);
        [hdr,vol] = niak_read_vol(files_in.map.(sub));
        tseries_tmp = niak_vol2tseries(vol(:,:,:,ss),mask);
        tseries = [tseries ;tseries_tmp];
        subj_id = [subj_id ; sub];
    end
    
    % Save stack and IDs for network N
    eval(sprintf('stack.net_%d.load =  tseries;',ss));
    eval(sprintf('stack.net_%d.ids =  subj_id;',ss));

    % Save Mean & std for the network N
    eval(sprintf('stack.net_%d.mean =  mean(tseries);',ss));
    eval(sprintf('stack.net_%d.mean =  std(tseries);',ss));
end

% Save the final stack file
stack_file = fullfile(files_out, 'stack_file.mat');
save(stack_file,'stack');