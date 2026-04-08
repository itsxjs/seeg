from pathlib import Path
from pynwb import NWBHDF5IO

nwb_path = Path('/Volumes/rmhyw/keles_ah_nwb_pipeline/data/000623/sub-CS55/sub-CS55_ses-P55CSR1_behavior+ecephys.nwb')

with NWBHDF5IO(str(nwb_path), 'r', load_namespaces=True) as io:
    nwb = io.read()
    print('units exists', nwb.units is not None)
    if nwb.units is not None:
        udf = nwb.units.to_dataframe().reset_index(drop=True)
        print('units cols', list(udf.columns))
        print('n_units', len(udf))
        for c in ['spike_times', 'electrodes', 'electrode_group', 'channel_name', 'label', 'location']:
            if c in udf.columns and len(udf):
                v = udf.iloc[0][c]
                print('sample', c, type(v), str(v)[:160])

    edf = nwb.electrodes.to_dataframe().reset_index(drop=True)
    print('electrodes cols', list(edf.columns))
    print('electrode n', len(edf))
    for c in ['label', 'location', 'origchannel_name', 'group_name']:
        if c in edf.columns and len(edf):
            print('sample elec', c, str(edf.iloc[0][c])[:160])
