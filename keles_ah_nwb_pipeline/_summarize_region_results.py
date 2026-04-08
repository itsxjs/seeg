import pandas as pd
import numpy as np

p = '/Volumes/rmhyw/keles_ah_nwb_pipeline/results/spike_region_batch_000623/spike_region_batch_summary.csv'
df = pd.read_csv(p)
ok = df[df.status == 'ok'].copy()

print('sessions', len(ok))
print('median_units_A', float(ok.n_units_a.median()))
print('median_units_H', float(ok.n_units_h.median()))
print('median_rho_AA', float(ok.rho_aa_median.median()))
print('median_rho_HH', float(ok.rho_hh_median.median(skipna=True)))
print('median_rho_AH', float(ok.rho_ah_median.median(skipna=True)))
print('median_rho_HA', float(ok.rho_ha_median.median(skipna=True)))
print('mean_sig_AA', float(ok.sig_aa_ratio.mean(skipna=True)))
print('mean_sig_HH', float(ok.sig_hh_ratio.mean(skipna=True)))
print('mean_sig_AH', float(ok.sig_ah_ratio.mean(skipna=True)))
print('mean_sig_HA', float(ok.sig_ha_ratio.mean(skipna=True)))

lag = ok['lag_ms_median'].dropna()
print('lag_n', len(lag))
if len(lag):
    print('lag_median', float(lag.median()))
    print('lag_q25', float(lag.quantile(0.25)))
    print('lag_q75', float(lag.quantile(0.75)))
    print('A_leads_frac', float((lag > 0).mean()))
    print('H_leads_frac', float((lag < 0).mean()))

ok['asym'] = (ok.rho_ah_median - ok.rho_ha_median).abs()
print('TOP_ASYM')
print(ok[['subject', 'nwb_file', 'rho_ah_median', 'rho_ha_median', 'lag_ms_median', 'asym']].sort_values('asym', ascending=False).head(5).to_string(index=False))
