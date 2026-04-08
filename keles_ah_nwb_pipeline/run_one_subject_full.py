from pathlib import Path

from pynwb import NWBHDF5IO

from ah_pipeline.config import PipelineConfig
from ah_pipeline.connectivity_stats import compute_band_granger
from ah_pipeline.export import save_subject_mat
from ah_pipeline.nwb_io import load_events, load_subject_lfp_from_nwb
from ah_pipeline.preprocessing import epoch_subject, preprocess_signal, run_hybrid_qc
from ah_pipeline.spikes import ifr_hgamma_coupling
from ah_pipeline.time_frequency import compute_tf_bootstrap_z


def load_units_table(nwb_path: Path):
    with NWBHDF5IO(str(nwb_path), mode="r", load_namespaces=True) as io:
        nwb = io.read()
        if nwb.units is None:
            import pandas as pd
            return pd.DataFrame({"spike_times": []})
        units = nwb.units.to_dataframe().reset_index(drop=True)
        if "spike_times" not in units.columns:
            import pandas as pd
            return pd.DataFrame({"spike_times": []})
        return units[["spike_times"]].copy()


def main() -> None:
    # 使用最新的直接下载位置
    nwb_path = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/000623/sub-CS42/sub-CS42_ses-P42CSR2_behavior+ecephys.nwb.dandidownload/file")
    event_csv = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/data/smoke_events_subcs42.csv")
    out_dir = Path("/Volumes/人盘含鱼纹/keles_ah_nwb_pipeline/results")

    cfg = PipelineConfig(
        data_dir=nwb_path.parent.parent,
        output_dir=out_dir,
        event_csv=event_csv,
        tf_bootstrap_n=1000,
    )

    sig = load_subject_lfp_from_nwb(nwb_path)
    sig_pp = preprocess_signal(sig, cfg)

    events = load_events(event_csv)
    ep = epoch_subject(sig_pp, events, cfg)
    ep_clean, qc = run_hybrid_qc(ep, cfg)

    tf_res = compute_tf_bootstrap_z(ep_clean, cfg)
    units_df = load_units_table(nwb_path)
    spike_res = ifr_hgamma_coupling(units_df, ep_clean, cfg)
    sgc_df = compute_band_granger(ep_clean, sig_pp.region, cfg)

    save_subject_mat(out_dir, sig.subject, tf_res, qc, spike_res, sgc_df)

    print("subject", sig.subject)
    print("clean_trials", len(ep_clean.trial_info))
    print("tf_shape", tf_res.z_power_ds.shape)
    print("ifr_shape", spike_res.ifr.shape)
    print("coupling_rows", len(spike_res.coupling))
    print("sgc_rows", len(sgc_df))
    print("saved", out_dir / f"{sig.subject}_scene_python_results.mat")


if __name__ == "__main__":
    main()
