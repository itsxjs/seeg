from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = [
    "Arial Unicode MS",
    "Heiti TC",
    "Songti SC",
    "PingFang SC",
    "SimHei",
    "Noto Sans CJK SC",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


FIXED_PROMPT = (
    "You are rating a 2-second movie clip for AROUSAL (activation intensity), "
    "NOT valence (pleasant/unpleasant). "
    "From a typical audience perspective, decide whether this 2-second clip is likely "
    "to trigger tension, startle, conflict expectation, or rapid emotional escalation. "
    "Return ONLY strict JSON with keys: "
    "arousal_score (0-100 integer), confidence (0-100 integer), "
    "reason_tags (array of short snake_case tags)."
)


@dataclass
class WindowScore:
    start_sec: float
    end_sec: float
    center_sec: float
    arousal_score: float
    confidence: float
    audio_salience: float
    normalized_audio_salience: float
    final_score: float
    reason_tags: str


@dataclass
class SceneOverlapRow:
    start_sec: float
    end_sec: float
    center_sec: float
    nearest_shot_start_t: float
    nearest_scene_id: float
    abs_delta_sec: float
    within_1s: int
    within_2s: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local AI annotation for high-arousal 2s segments on short.mp4"
    )
    parser.add_argument("--video", type=Path, required=True, help="Video file path")
    parser.add_argument(
        "--scene-cut-csv",
        type=Path,
        required=True,
        help="CSV containing shot_start_t and scene_id",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output folder for CSV/PNG/JSON artifacts",
    )
    parser.add_argument("--window-sec", type=float, default=2.0, help="Sliding window length")
    parser.add_argument("--stride-sec", type=float, default=1.0, help="Sliding stride length")
    parser.add_argument(
        "--model-id",
        type=str,
        default="Qwen/Qwen2.5-VL-3B-Instruct",
        help="Vision-language model id (Hugging Face)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "mps", "cpu"],
        help="Compute device",
    )
    parser.add_argument(
        "--frames-per-window",
        type=int,
        default=4,
        help="Number of key frames sampled per window",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=200,
        help="Max generated tokens for VLM response",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Generation temperature (0 for deterministic)",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=None,
        help="Optional cap for number of windows for smoke testing",
    )
    parser.add_argument(
        "--z-threshold",
        type=float,
        default=1.5,
        help="High-confidence z-score threshold on final_score",
    )
    parser.add_argument(
        "--min-vlm-arousal",
        type=float,
        default=70.0,
        help="Minimum VLM arousal score",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=60.0,
        help="Minimum confidence score",
    )
    parser.add_argument(
        "--n-permutations",
        type=int,
        default=5000,
        help="Permutation count for enrichment p-value",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    return parser.parse_args()


def require_file(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} does not exist: {path}")


def safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return fallback
        return out
    except Exception:
        return fallback


def zscore(values: np.ndarray) -> np.ndarray:
    vals = np.asarray(values, dtype=float)
    if vals.size == 0:
        return vals
    mu = np.nanmean(vals)
    sigma = np.nanstd(vals)
    if not np.isfinite(sigma) or sigma < 1e-8:
        return np.zeros_like(vals)
    return (vals - mu) / sigma


def normalize_0_100(values: np.ndarray) -> np.ndarray:
    vals = np.asarray(values, dtype=float)
    if vals.size == 0:
        return vals
    vmin = np.nanmin(vals)
    vmax = np.nanmax(vals)
    if not np.isfinite(vmax - vmin) or (vmax - vmin) < 1e-8:
        return np.zeros_like(vals)
    return 100.0 * (vals - vmin) / (vmax - vmin)


def build_windows(duration_sec: float, window_sec: float, stride_sec: float) -> list[tuple[float, float]]:
    windows: list[tuple[float, float]] = []
    t = 0.0
    while (t + window_sec) <= (duration_sec + 1e-9):
        windows.append((round(t, 6), round(t + window_sec, 6)))
        t += stride_sec
    return windows


def load_video_metadata(video_path: Path) -> tuple[float, float, int, int]:
    try:
        import cv2
    except Exception as exc:
        raise RuntimeError(
            "OpenCV is required for video decoding. Install opencv-python-headless in the arousal environment."
        ) from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    fps = safe_float(cap.get(cv2.CAP_PROP_FPS), 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()

    if fps <= 0 or frame_count <= 0:
        raise RuntimeError("Could not infer FPS/frame_count from video metadata.")
    duration = frame_count / fps
    return duration, fps, width, height


def sample_window_frames(
    video_path: Path,
    fps: float,
    start_sec: float,
    end_sec: float,
    frames_per_window: int,
) -> list[Any]:
    try:
        import cv2
        from PIL import Image
    except Exception as exc:
        raise RuntimeError(
            "Missing frame decoding dependencies. Install opencv-python-headless and Pillow."
        ) from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    times = np.linspace(start_sec, end_sec, num=frames_per_window, endpoint=False) + (
        (end_sec - start_sec) / (2.0 * frames_per_window)
    )
    frames: list[Any] = []
    for t in times:
        frame_idx = max(int(round(t * fps)), 0)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame_bgr = cap.read()
        if not ok or frame_bgr is None:
            continue
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frames.append(Image.fromarray(frame_rgb))

    cap.release()
    return frames


def load_audio_mono(video_path: Path, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    try:
        import librosa

        y, sr = librosa.load(str(video_path), sr=target_sr, mono=True)
        return y.astype(np.float32), int(sr)
    except Exception:
        pass

    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin is None:
        return np.zeros(1, dtype=np.float32), target_sr

    try:
        import soundfile as sf
    except Exception:
        return np.zeros(1, dtype=np.float32), target_sr

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_wav = Path(tmpdir) / "audio.wav"
        import subprocess

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(target_sr),
            str(tmp_wav),
        ]
        run = subprocess.run(cmd, capture_output=True, text=True)
        if run.returncode != 0 or not tmp_wav.exists():
            return np.zeros(1, dtype=np.float32), target_sr
        y, sr = sf.read(str(tmp_wav), dtype="float32")
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        return y.astype(np.float32), int(sr)


def compute_audio_features(y: np.ndarray, sr: int, start_sec: float, end_sec: float) -> tuple[float, float, float]:
    s0 = max(int(round(start_sec * sr)), 0)
    s1 = max(int(round(end_sec * sr)), s0 + 1)
    seg = y[s0:s1]
    if seg.size < 4:
        return 0.0, 0.0, 0.0

    rms_energy = float(np.sqrt(np.mean(seg ** 2) + 1e-12))

    frame_len = max(int(0.025 * sr), 64)
    hop_len = max(int(0.010 * sr), 32)
    n_frames = 1 + max((len(seg) - frame_len) // hop_len, 0)
    if n_frames <= 1:
        return rms_energy, 0.0, rms_energy

    win = np.hanning(frame_len).astype(np.float32)
    mags = []
    for i in range(n_frames):
        st = i * hop_len
        frame = seg[st : st + frame_len]
        if len(frame) < frame_len:
            pad = np.zeros(frame_len, dtype=np.float32)
            pad[: len(frame)] = frame
            frame = pad
        spec = np.fft.rfft(frame * win)
        mags.append(np.abs(spec))

    mag = np.stack(mags, axis=0)
    flux = np.diff(mag, axis=0)
    spectral_flux = float(np.mean(np.sqrt(np.sum(np.maximum(flux, 0.0) ** 2, axis=1))))
    salience = float(0.6 * rms_energy + 0.4 * spectral_flux)
    return rms_energy, spectral_flux, salience


def resolve_device(device_arg: str) -> str:
    try:
        import torch
    except Exception as exc:
        raise RuntimeError(
            "PyTorch is required for VLM inference. Install torch in the arousal environment."
        ) from exc

    if device_arg == "cpu":
        return "cpu"
    if device_arg == "mps":
        if torch.backends.mps.is_available():
            return "mps"
        raise RuntimeError("MPS requested but unavailable. Re-run with --device cpu.")

    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_vlm(model_id: str, device: str) -> tuple[Any, Any, str]:
    try:
        import torch
        import transformers
    except Exception as exc:
        raise RuntimeError(
            "Failed to import transformers VLM stack. Use a newer environment with "
            "transformers>=4.49 and torch>=2.4."
        ) from exc

    auto_processor_cls = getattr(transformers, "AutoProcessor", None)
    if auto_processor_cls is None:
        raise RuntimeError("transformers is missing AutoProcessor. Please upgrade transformers.")

    dtype = torch.float16 if device == "mps" else torch.float32

    model = None
    model_errors = []

    vision_classes = [
        "AutoModelForImageTextToText",  # newer transformers
        "AutoModelForVision2Seq",       # older transformers
    ]
    for cls_name in vision_classes:
        cls = getattr(transformers, cls_name, None)
        if cls is None:
            model_errors.append(f"{cls_name} unavailable in transformers=={transformers.__version__}")
            continue
        try:
            model = cls.from_pretrained(
                model_id,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
                trust_remote_code=True,
            )
            break
        except Exception as exc:
            model_errors.append(f"{cls_name} failed: {exc}")

    if model is None:
        try:
            auto_causal_cls = getattr(transformers, "AutoModelForCausalLM", None)
            if auto_causal_cls is None:
                raise RuntimeError("AutoModelForCausalLM unavailable")

            model = auto_causal_cls.from_pretrained(
                model_id,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
                trust_remote_code=True,
            )
        except Exception as exc:
            model_errors.append(f"AutoModelForCausalLM fallback failed: {exc}")

    if model is None:
        joined = "\n".join(model_errors)
        raise RuntimeError(
            "Unable to load VLM model. This usually means the installed transformers version "
            "is too old for Qwen2.5-VL or the model id is incompatible.\n"
            f"transformers={transformers.__version__}\n"
            f"model_id={model_id}\n{joined}"
        )

    processor = auto_processor_cls.from_pretrained(model_id, trust_remote_code=True)

    try:
        model.to(device)
    except Exception as exc:
        if device == "mps":
            raise RuntimeError(
                "Model failed on MPS. Try --device cpu (slower but more stable)."
            ) from exc
        raise

    model.eval()
    return model, processor, device


def build_multimodal_prompt(start_sec: float, end_sec: float) -> str:
    return (
        f"Clip time range: {start_sec:.3f}s to {end_sec:.3f}s. "
        f"{FIXED_PROMPT}"
    )


def parse_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model response: {text[:200]}")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Parsed JSON payload is not an object.")
    return payload


def parse_structured_from_text(text: str) -> tuple[float, float, list[str]]:
    """Best-effort parse for responses that are not strict JSON."""
    try:
        payload = parse_json_from_text(text)
        arousal = float(np.clip(safe_float(payload.get("arousal_score", 0.0)), 0.0, 100.0))
        confidence = float(np.clip(safe_float(payload.get("confidence", 0.0)), 0.0, 100.0))
        tags = payload.get("reason_tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            tags = []
        tags = [str(t).strip() for t in tags if str(t).strip()]
        return arousal, confidence, tags
    except Exception:
        pass

    # Fallback regex extraction from plain-text model responses.
    m_ar = re.search(r"arousal(?:_score)?\s*[:=]\s*(\d{1,3})", text, flags=re.IGNORECASE)
    m_cf = re.search(r"confidence\s*[:=]\s*(\d{1,3})", text, flags=re.IGNORECASE)
    arousal = float(np.clip(safe_float(m_ar.group(1) if m_ar else 0.0), 0.0, 100.0))
    confidence = float(np.clip(safe_float(m_cf.group(1) if m_cf else 0.0), 0.0, 100.0))
    tags = re.findall(r"[a-z]+(?:_[a-z]+)+", text.lower())
    tags = list(dict.fromkeys(tags))[:8]
    return arousal, confidence, tags


def run_vlm_inference(
    model: Any,
    processor: Any,
    device: str,
    frames: list[Any],
    prompt: str,
    max_new_tokens: int,
    temperature: float,
) -> tuple[float, float, list[str], str]:
    try:
        import torch
    except Exception as exc:
        raise RuntimeError("PyTorch import failed during inference.") from exc

    if not frames:
        return 0.0, 0.0, ["frame_decode_failed"], "{}"

    prepared = None
    raw_text = ""
    errors: list[str] = []

    try:
        prepared = processor(images=frames, text=prompt, return_tensors="pt")
        prepared = {k: v.to(device) if hasattr(v, "to") else v for k, v in prepared.items()}
        with torch.no_grad():
            output = model.generate(
                **prepared,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )
        raw_text = processor.batch_decode(output, skip_special_tokens=True)[0]
    except Exception as exc:
        errors.append(f"direct_processor_path failed: {exc}")

    # Preferred path for chat-oriented VLMs (e.g., Qwen2.5-VL): include explicit image content.
    if not raw_text and hasattr(processor, "apply_chat_template"):
        try:
            content_items = [{"type": "image"} for _ in frames]
            content_items.append({"type": "text", "text": prompt})
            messages = [{"role": "user", "content": content_items}]
            chat_text = processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            prepared = processor(text=[chat_text], images=frames, return_tensors="pt")
            prepared = {k: v.to(device) if hasattr(v, "to") else v for k, v in prepared.items()}
            with torch.no_grad():
                output = model.generate(
                    **prepared,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=temperature > 0,
                )
            raw_text = processor.batch_decode(output, skip_special_tokens=True)[0]
        except Exception as exc:
            errors.append(f"chat_image_template_path failed: {exc}")

    # Some VLM checkpoints require explicit image placeholder tokens in text.
    if not raw_text:
        try:
            image_token = getattr(processor, "image_token", None) or "<image>"
            token_prefix = image_token
            prompt_with_image_tokens = f"{token_prefix}\n{prompt}"
            # Fallback to first frame for checkpoints that do not support multi-image prompts.
            image_input = frames[0]
            prepared = processor(images=image_input, text=prompt_with_image_tokens, return_tensors="pt")
            prepared = {k: v.to(device) if hasattr(v, "to") else v for k, v in prepared.items()}
            with torch.no_grad():
                output = model.generate(
                    **prepared,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=temperature > 0,
                )
            raw_text = processor.batch_decode(output, skip_special_tokens=True)[0]
        except Exception as exc:
            errors.append(f"image_token_fallback failed: {exc}")

    if not raw_text:
        raise RuntimeError("VLM decoding failed. " + " | ".join(errors))

    arousal, confidence, tags = parse_structured_from_text(raw_text)
    return arousal, confidence, tags, raw_text


def select_high_confidence_segments(df_scores: pd.DataFrame, z_th: float, min_arousal: float, min_conf: float) -> pd.DataFrame:
    if df_scores.empty:
        return df_scores.copy()

    hit_mask = (
        (df_scores["z_final_score"] >= z_th)
        & (df_scores["arousal_score"] >= min_arousal)
        & (df_scores["confidence"] >= min_conf)
    )
    hits = df_scores.loc[hit_mask].copy().sort_values("start_sec").reset_index(drop=True)
    if hits.empty:
        return hits

    clusters: list[list[int]] = []
    current = [0]
    for idx in range(1, len(hits)):
        prev = hits.iloc[idx - 1]
        cur = hits.iloc[idx]
        overlap_or_adjacent = cur["start_sec"] <= (prev["end_sec"] + 1e-9)
        if overlap_or_adjacent:
            current.append(idx)
        else:
            clusters.append(current)
            current = [idx]
    clusters.append(current)

    kept_rows = []
    for cluster_id, indices in enumerate(clusters, start=1):
        block = hits.iloc[indices].copy()
        peak_idx = block["final_score"].idxmax()
        row = hits.loc[peak_idx].copy()
        row["cluster_id"] = cluster_id
        row["cluster_size"] = int(len(block))
        kept_rows.append(row)

    out = pd.DataFrame(kept_rows).sort_values("start_sec").reset_index(drop=True)
    return out


def compute_scene_overlap(
    selected_df: pd.DataFrame,
    scenecut_df: pd.DataFrame,
) -> pd.DataFrame:
    if selected_df.empty:
        return pd.DataFrame(
            columns=[
                "start_sec",
                "end_sec",
                "center_sec",
                "nearest_shot_start_t",
                "nearest_scene_id",
                "abs_delta_sec",
                "within_1s",
                "within_2s",
            ]
        )

    shot_times = scenecut_df["shot_start_t"].to_numpy(dtype=float)
    scene_ids = scenecut_df["scene_id"].to_numpy(dtype=float)

    rows: list[SceneOverlapRow] = []
    for _, r in selected_df.iterrows():
        center = float(r["center_sec"])
        deltas = np.abs(shot_times - center)
        nearest_idx = int(np.argmin(deltas))
        nearest_delta = float(deltas[nearest_idx])
        rows.append(
            SceneOverlapRow(
                start_sec=float(r["start_sec"]),
                end_sec=float(r["end_sec"]),
                center_sec=center,
                nearest_shot_start_t=float(shot_times[nearest_idx]),
                nearest_scene_id=float(scene_ids[nearest_idx]),
                abs_delta_sec=nearest_delta,
                within_1s=int(nearest_delta <= 1.0),
                within_2s=int(nearest_delta <= 2.0),
            )
        )

    return pd.DataFrame([asdict(x) for x in rows])


def permutation_enrichment(
    all_windows_df: pd.DataFrame,
    selected_df: pd.DataFrame,
    shot_times: np.ndarray,
    n_perm: int,
    seed: int,
) -> dict[str, float]:
    n_selected = int(len(selected_df))
    if n_selected == 0 or len(all_windows_df) < n_selected:
        return {
            "n_selected": n_selected,
            "obs_within_1s_rate": 0.0,
            "obs_within_2s_rate": 0.0,
            "rand_mean_within_1s_rate": 0.0,
            "rand_mean_within_2s_rate": 0.0,
            "enrichment_within_1s": 0.0,
            "enrichment_within_2s": 0.0,
            "perm_p_within_1s": 1.0,
            "perm_p_within_2s": 1.0,
        }

    def rate_within(center_values: np.ndarray, sec: float) -> float:
        if center_values.size == 0:
            return 0.0
        nearest = np.min(np.abs(center_values[:, None] - shot_times[None, :]), axis=1)
        return float(np.mean(nearest <= sec))

    obs_centers = selected_df["center_sec"].to_numpy(dtype=float)
    obs_r1 = rate_within(obs_centers, 1.0)
    obs_r2 = rate_within(obs_centers, 2.0)

    rng = np.random.default_rng(seed)
    all_centers = all_windows_df["center_sec"].to_numpy(dtype=float)

    rand_r1 = np.zeros(n_perm, dtype=float)
    rand_r2 = np.zeros(n_perm, dtype=float)
    for i in range(n_perm):
        idx = rng.choice(len(all_centers), size=n_selected, replace=False)
        samp = all_centers[idx]
        rand_r1[i] = rate_within(samp, 1.0)
        rand_r2[i] = rate_within(samp, 2.0)

    mean_r1 = float(np.mean(rand_r1))
    mean_r2 = float(np.mean(rand_r2))

    p1 = float((np.sum(rand_r1 >= obs_r1) + 1) / (n_perm + 1))
    p2 = float((np.sum(rand_r2 >= obs_r2) + 1) / (n_perm + 1))

    return {
        "n_selected": n_selected,
        "obs_within_1s_rate": obs_r1,
        "obs_within_2s_rate": obs_r2,
        "rand_mean_within_1s_rate": mean_r1,
        "rand_mean_within_2s_rate": mean_r2,
        "enrichment_within_1s": float(obs_r1 / max(mean_r1, 1e-9)),
        "enrichment_within_2s": float(obs_r2 / max(mean_r2, 1e-9)),
        "perm_p_within_1s": p1,
        "perm_p_within_2s": p2,
    }


def make_scene_coverage_table(scene_overlap_df: pd.DataFrame) -> pd.DataFrame:
    if scene_overlap_df.empty:
        return pd.DataFrame(
            columns=["scene_id", "n_hits", "within_1s_rate", "within_2s_rate", "median_abs_delta_sec"]
        )

    grouped = scene_overlap_df.groupby("nearest_scene_id", as_index=False).agg(
        n_hits=("nearest_scene_id", "size"),
        within_1s_rate=("within_1s", "mean"),
        within_2s_rate=("within_2s", "mean"),
        median_abs_delta_sec=("abs_delta_sec", "median"),
    )
    grouped = grouped.rename(columns={"nearest_scene_id": "scene_id"})
    return grouped.sort_values(["n_hits", "scene_id"], ascending=[False, True]).reset_index(drop=True)


def save_plot(
    output_png: Path,
    windows_df: pd.DataFrame,
    selected_df: pd.DataFrame,
    scenecut_df: pd.DataFrame,
    duration_sec: float,
) -> None:
    fig, ax = plt.subplots(figsize=(16, 5.8), dpi=160)

    ax.plot(windows_df["center_sec"], windows_df["final_score"], color="#1f77b4", linewidth=1.8, label="综合评分")
    ax.plot(windows_df["center_sec"], windows_df["arousal_score"], color="#ff7f0e", linewidth=1.4, alpha=0.75, label="VLM唤醒评分")

    shot_times = scenecut_df["shot_start_t"].to_numpy(dtype=float)
    for t in shot_times:
        ax.axvline(t, color="#666666", linewidth=0.7, alpha=0.14)

    for _, row in selected_df.iterrows():
        ax.axvspan(row["start_sec"], row["end_sec"], color="#d62728", alpha=0.2)

    ax.set_xlim(0, duration_sec)
    ax.set_xlabel("时间 (s)", fontsize=18)
    ax.set_ylabel("评分", fontsize=18)
    ax.set_title("AI高唤醒窗口与官方镜头切割", fontsize=20, pad=12)
    ax.tick_params(axis="both", labelsize=15)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=15, frameon=True)

    fig.tight_layout()
    fig.savefig(output_png)
    plt.close(fig)


def main() -> None:
    args = parse_args()

    require_file(args.video, "Video")
    require_file(args.scene_cut_csv, "Scene-cut CSV")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    scenecut_df = pd.read_csv(args.scene_cut_csv)
    needed_cols = {"scene_id", "shot_start_t"}
    if not needed_cols.issubset(set(scenecut_df.columns)):
        raise ValueError(
            f"scene-cut CSV must contain columns {sorted(needed_cols)}, got {list(scenecut_df.columns)}"
        )

    duration_sec, fps, width, height = load_video_metadata(args.video)

    windows = build_windows(duration_sec, args.window_sec, args.stride_sec)
    if args.max_windows is not None:
        windows = windows[: args.max_windows]

    if not windows:
        raise RuntimeError("No valid windows after applying window/stride/max-windows settings.")

    y, sr = load_audio_mono(args.video)

    device = resolve_device(args.device)
    model, processor, resolved_device = load_vlm(args.model_id, device)

    rows: list[WindowScore] = []
    parse_failures = 0

    for idx, (start_sec, end_sec) in enumerate(windows, start=1):
        frames = sample_window_frames(
            video_path=args.video,
            fps=fps,
            start_sec=start_sec,
            end_sec=end_sec,
            frames_per_window=args.frames_per_window,
        )
        _, _, audio_sal = compute_audio_features(y=y, sr=sr, start_sec=start_sec, end_sec=end_sec)

        prompt = build_multimodal_prompt(start_sec, end_sec)

        try:
            arousal, conf, tags, _raw = run_vlm_inference(
                model=model,
                processor=processor,
                device=resolved_device,
                frames=frames,
                prompt=prompt,
                max_new_tokens=args.max_new_tokens,
                temperature=args.temperature,
            )
        except Exception:
            parse_failures += 1
            arousal, conf, tags = 0.0, 0.0, ["inference_failed"]

        rows.append(
            WindowScore(
                start_sec=float(start_sec),
                end_sec=float(end_sec),
                center_sec=float((start_sec + end_sec) * 0.5),
                arousal_score=float(arousal),
                confidence=float(conf),
                audio_salience=float(audio_sal),
                normalized_audio_salience=0.0,
                final_score=0.0,
                reason_tags="|".join(tags),
            )
        )

        if idx % 20 == 0 or idx == len(windows):
            print(f"Processed windows: {idx}/{len(windows)}")

    df = pd.DataFrame([asdict(r) for r in rows])
    df["normalized_audio_salience"] = normalize_0_100(df["audio_salience"].to_numpy(dtype=float))
    df["final_score"] = (
        0.7 * df["arousal_score"]
        + 0.2 * df["confidence"]
        + 0.1 * df["normalized_audio_salience"]
    )
    df["z_final_score"] = zscore(df["final_score"].to_numpy(dtype=float))

    selected_df = select_high_confidence_segments(
        df_scores=df,
        z_th=args.z_threshold,
        min_arousal=args.min_vlm_arousal,
        min_conf=args.min_confidence,
    )

    scene_overlap_df = compute_scene_overlap(selected_df=selected_df, scenecut_df=scenecut_df)
    scene_coverage_df = make_scene_coverage_table(scene_overlap_df)

    enrich = permutation_enrichment(
        all_windows_df=df,
        selected_df=selected_df,
        shot_times=scenecut_df["shot_start_t"].to_numpy(dtype=float),
        n_perm=args.n_permutations,
        seed=args.seed,
    )

    arousal_segments_path = output_dir / "arousal_segments.csv"
    window_scores_path = output_dir / "window_scores.csv"
    scene_overlap_path = output_dir / "scene_overlap.csv"
    scene_coverage_path = output_dir / "scene_coverage_by_scene_id.csv"
    plot_path = output_dir / "arousal_vs_scenecut.png"
    run_cfg_path = output_dir / "run_config.json"
    summary_path = output_dir / "summary_metrics.json"

    keep_cols = [
        "start_sec",
        "end_sec",
        "center_sec",
        "arousal_score",
        "confidence",
        "audio_salience",
        "final_score",
        "reason_tags",
    ]
    if not selected_df.empty:
        selected_df[keep_cols].to_csv(arousal_segments_path, index=False)
    else:
        pd.DataFrame(columns=keep_cols).to_csv(arousal_segments_path, index=False)

    df.to_csv(window_scores_path, index=False)
    scene_overlap_df.to_csv(scene_overlap_path, index=False)
    scene_coverage_df.to_csv(scene_coverage_path, index=False)

    save_plot(
        output_png=plot_path,
        windows_df=df,
        selected_df=selected_df,
        scenecut_df=scenecut_df,
        duration_sec=duration_sec,
    )

    run_cfg = {
        "video": str(args.video),
        "scene_cut_csv": str(args.scene_cut_csv),
        "output_dir": str(output_dir),
        "window_sec": args.window_sec,
        "stride_sec": args.stride_sec,
        "frames_per_window": args.frames_per_window,
        "model_id": args.model_id,
        "requested_device": args.device,
        "resolved_device": resolved_device,
        "max_windows": args.max_windows,
        "max_new_tokens": args.max_new_tokens,
        "temperature": args.temperature,
        "z_threshold": args.z_threshold,
        "min_vlm_arousal": args.min_vlm_arousal,
        "min_confidence": args.min_confidence,
        "n_permutations": args.n_permutations,
        "seed": args.seed,
        "video_meta": {
            "duration_sec": duration_sec,
            "fps": fps,
            "width": width,
            "height": height,
            "n_windows": len(windows),
        },
    }
    run_cfg_path.write_text(json.dumps(run_cfg, indent=2), encoding="utf-8")

    within_1s = float(scene_overlap_df["within_1s"].mean()) if not scene_overlap_df.empty else 0.0
    within_2s = float(scene_overlap_df["within_2s"].mean()) if not scene_overlap_df.empty else 0.0
    median_abs_delta = (
        float(scene_overlap_df["abs_delta_sec"].median()) if not scene_overlap_df.empty else float("nan")
    )

    summary = {
        "n_total_windows": int(len(df)),
        "n_selected_segments": int(len(selected_df)),
        "within_1s_hit_rate": within_1s,
        "within_2s_hit_rate": within_2s,
        "median_abs_delta_sec": median_abs_delta,
        "parse_or_inference_failures": int(parse_failures),
        "final_score_mean": safe_float(df["final_score"].mean(), 0.0),
        "final_score_std": safe_float(df["final_score"].std(), 0.0),
        "observed_selected_final_score_median": (
            safe_float(selected_df["final_score"].median(), 0.0) if not selected_df.empty else 0.0
        ),
    }
    summary.update(enrich)

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Completed local arousal annotation pipeline.")
    print(f"Selected segments: {len(selected_df)}")
    print(f"Within 1s: {within_1s:.3f}, Within 2s: {within_2s:.3f}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
