from __future__ import annotations

import gc
import hashlib
import math
import statistics
import time
from dataclasses import asdict, dataclass

import numpy as np

from app.brain_v2.preprocessing.raw_decode import DecodedRawFrame
from app.brain_v2.vision_encoders.hf_candidate import HuggingFaceVisionEncoder


@dataclass(frozen=True)
class EncoderBenchmark:
    encoder_id: str
    status: str
    device: str
    dimension: int | None
    load_seconds: float | None
    inference_seconds_median: float | None
    inference_seconds_min: float | None
    inference_seconds_max: float | None
    gpu_peak_allocated_mb: float | None
    gpu_peak_reserved_mb: float | None
    process_rss_before_mb: float | None
    process_rss_after_mb: float | None
    vector_l2_norm: float | None
    vector_sha256: str | None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def vector_sha256(vector: tuple[float, ...]) -> str:
    array = np.asarray(vector, dtype=np.float32)
    return hashlib.sha256(array.tobytes()).hexdigest()


def _rss_mb() -> float | None:
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / (1024.0 * 1024.0)
    except Exception:
        return None


def _sync_cuda(device: str) -> None:
    if device != "cuda":
        return

    import torch

    torch.cuda.synchronize()


def _reset_gpu_peak(device: str) -> None:
    if device != "cuda":
        return

    import torch

    torch.cuda.reset_peak_memory_stats()


def _gpu_peaks(device: str) -> tuple[float | None, float | None]:
    if device != "cuda":
        return None, None

    import torch

    allocated = torch.cuda.max_memory_allocated() / (1024.0 * 1024.0)
    reserved = torch.cuda.max_memory_reserved() / (1024.0 * 1024.0)
    return float(allocated), float(reserved)


def classify_model_load_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".casefold()

    if (
        "gatedrepoerror" in text
        or "gated repo" in text
        or "access to model" in text
        or "restricted" in text
        or "403 client error" in text
    ):
        return "gated_or_unauthorized"

    if (
        "connection" in text
        or "offline" in text
        or "timeout" in text
        or "network" in text
    ):
        return "network_error"

    return "load_error"


def benchmark_hf_encoder(
    *,
    encoder_id: str,
    frame: DecodedRawFrame,
    device: str,
    runs: int,
) -> tuple[EncoderBenchmark, tuple[float, ...] | None]:
    if runs < 1:
        raise ValueError("runs חייב להיות לפחות 1.")

    rss_before = _rss_mb()
    encoder = HuggingFaceVisionEncoder(
        encoder_id=encoder_id,
        device=device,
    )

    try:
        start_load = time.perf_counter()
        encoder.load()
        _sync_cuda(device)
        load_seconds = time.perf_counter() - start_load
    except Exception as exc:
        return (
            EncoderBenchmark(
                encoder_id=encoder_id,
                status="blocked",
                device=device,
                dimension=None,
                load_seconds=None,
                inference_seconds_median=None,
                inference_seconds_min=None,
                inference_seconds_max=None,
                gpu_peak_allocated_mb=None,
                gpu_peak_reserved_mb=None,
                process_rss_before_mb=rss_before,
                process_rss_after_mb=_rss_mb(),
                vector_l2_norm=None,
                vector_sha256=None,
                error_type=classify_model_load_error(exc),
                error_message=str(exc)[:1000],
            ),
            None,
        )

    try:
        # Warm-up is intentionally not included in measured inference time.
        _reset_gpu_peak(device)
        warmup = encoder.encode(frame)
        _sync_cuda(device)

        durations: list[float] = []
        result = warmup

        for _ in range(runs):
            _sync_cuda(device)
            start = time.perf_counter()
            result = encoder.encode(frame)
            _sync_cuda(device)
            durations.append(time.perf_counter() - start)

        allocated, reserved = _gpu_peaks(device)
        vector = result.vector
        norm = math.sqrt(sum(value * value for value in vector))

        report = EncoderBenchmark(
            encoder_id=encoder_id,
            status="pass",
            device=device,
            dimension=result.dimension,
            load_seconds=float(load_seconds),
            inference_seconds_median=float(statistics.median(durations)),
            inference_seconds_min=float(min(durations)),
            inference_seconds_max=float(max(durations)),
            gpu_peak_allocated_mb=allocated,
            gpu_peak_reserved_mb=reserved,
            process_rss_before_mb=rss_before,
            process_rss_after_mb=_rss_mb(),
            vector_l2_norm=float(norm),
            vector_sha256=vector_sha256(vector),
        )
        return report, vector
    except Exception as exc:
        return (
            EncoderBenchmark(
                encoder_id=encoder_id,
                status="failed",
                device=device,
                dimension=None,
                load_seconds=float(load_seconds),
                inference_seconds_median=None,
                inference_seconds_min=None,
                inference_seconds_max=None,
                gpu_peak_allocated_mb=None,
                gpu_peak_reserved_mb=None,
                process_rss_before_mb=rss_before,
                process_rss_after_mb=_rss_mb(),
                vector_l2_norm=None,
                vector_sha256=None,
                error_type=type(exc).__name__,
                error_message=str(exc)[:1000],
            ),
            None,
        )
    finally:
        encoder.unload()
        del encoder
        gc.collect()
