"""波形定义与生成模块

参考 DG-LAB 协议：每个 PulseOperation 包含 4 个 100ms 段，
频率固定为低值 (10) 以获得平滑持续输出，通过逐段变化强度值实现波形。
"""
import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple

# PulseOperation: ((f1,f2,f3,f4), (s1,s2,s3,s4))
# f: 频率 10~1000, s: 强度 0~100
# 每个 PulseOperation = 4 段 × 100ms = 400ms
PulseOperation = Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int]]


def _clamp_freq(v: int) -> int:
    return max(10, min(1000, v))


def _clamp_strength(v: int) -> int:
    return max(0, min(100, v))


# ---------------------------------------------------------------------------
# Core: keyframe interpolation → per-100ms segments → PulseOperation packing
# ---------------------------------------------------------------------------

def interpolate_keyframes(keyframes: List[Tuple[int, int]]) -> List[int]:
    """线性插值关键帧，生成 100ms 粒度的强度值列表。

    keyframes: [(steps, target_strength), ...]
      steps = 过渡到目标强度需要的 100ms 步数 (≥1)
      target_strength = 目标强度 (0-100)
    从强度 0 开始，依次线性插值到各关键帧的目标值。
    """
    if not keyframes:
        return [0]

    strengths = []
    current = 0.0

    for steps, target in keyframes:
        steps = max(1, int(steps))
        target = _clamp_strength(int(target))
        for i in range(steps):
            t = (i + 1) / steps
            value = current + (target - current) * t
            strengths.append(_clamp_strength(int(round(value))))
        current = float(target)

    return strengths if strengths else [0]


def pack_segments(freq: int, strengths: List[int]) -> List[PulseOperation]:
    """将 100ms 粒度的强度列表打包成 PulseOperation 列表。

    每 4 个连续强度值组成一个 PulseOperation (400ms)。
    不足 4 的倍数时用最后一个值填充。
    """
    freq = _clamp_freq(freq)
    if not strengths:
        return []

    padded = list(strengths)
    while len(padded) % 4 != 0:
        padded.append(padded[-1])

    pulses = []
    for i in range(0, len(padded), 4):
        f = (freq, freq, freq, freq)
        s = tuple(_clamp_strength(v) for v in padded[i:i + 4])
        pulses.append((f, s))
    return pulses


# ---------------------------------------------------------------------------
# Legacy helpers (kept for compatibility)
# ---------------------------------------------------------------------------

def make_pulse(freq: int, strength: int) -> PulseOperation:
    f = _clamp_freq(freq)
    s = _clamp_strength(strength)
    return ((f, f, f, f), (s, s, s, s))


def make_pulse_varied(freqs: Tuple[int, int, int, int],
                      strengths: Tuple[int, int, int, int]) -> PulseOperation:
    fs = tuple(_clamp_freq(f) for f in freqs)
    ss = tuple(_clamp_strength(s) for s in strengths)
    return (fs, ss)  # type: ignore


# ---------------------------------------------------------------------------
# Preset definitions (keyframe-based, frequency=10 for smooth output)
# ---------------------------------------------------------------------------

@dataclass
class WaveformPreset:
    name: str
    display_name: str
    frequency: int
    keyframes: List[Tuple[int, int]]  # [(steps, target_strength), ...]
    description: str = ""

    def __post_init__(self):
        segs = interpolate_keyframes(self.keyframes)
        self._pulses = pack_segments(self.frequency, segs)
        self._segments = segs

    @property
    def pulses(self) -> List[PulseOperation]:
        return self._pulses

    @property
    def segments(self) -> List[int]:
        """100ms 粒度的强度值序列（用于预览）"""
        return self._segments


PRESET_WAVEFORMS: List[WaveformPreset] = [
    WaveformPreset(
        "breathing", "呼吸", 10,
        [(20, 80), (20, 1)],
        "缓慢渐强再渐弱，模拟呼吸节奏，温和舒适",
    ),
    WaveformPreset(
        "pulse", "脉冲", 10,
        [(1, 70), (11, 70), (1, 1), (11, 1)],
        "方波交替，有明显的开关节奏，冲击感强",
    ),
    WaveformPreset(
        "continuous", "连续", 10,
        [(1, 50), (39, 50)],
        "恒定强度持续输出，稳定均匀",
    ),
    WaveformPreset(
        "sawtooth", "锯齿", 10,
        [(38, 80), (2, 1)],
        "线性渐强后快速归零，逐渐增强的紧张感",
    ),
    WaveformPreset(
        "sine", "正弦", 10,
        [(10, 70), (20, 1), (10, 70)],
        "三角波近似正弦，平滑的周期性起伏",
    ),
    WaveformPreset(
        "random", "随机", 10,
        [(3, 65), (2, 20), (4, 80), (1, 10), (3, 55),
         (2, 40), (5, 75), (3, 15), (2, 60), (3, 30)],
        "不规则强度变化，不可预测的刺激",
    ),
    WaveformPreset(
        "heartbeat", "心跳", 10,
        [(2, 60), (2, 20), (2, 50), (2, 1), (8, 1)],
        "模拟心跳的双脉冲节奏，两次快速跳动后停顿",
    ),
    WaveformPreset(
        "tidal", "潮汐", 10,
        [(30, 80), (30, 1)],
        "缓慢起伏如潮汐，长周期的渐变",
    ),
]


def get_preset_names() -> List[Tuple[str, str]]:
    return [(p.name, p.display_name) for p in PRESET_WAVEFORMS]


def get_preset_by_name(name: str) -> WaveformPreset | None:
    for p in PRESET_WAVEFORMS:
        if p.name == name:
            return p
    return None


def scale_waveform_strength(pulses: List[PulseOperation],
                            factor: float) -> List[PulseOperation]:
    """按比例缩放波形强度"""
    result = []
    for freqs, strengths in pulses:
        new_s = tuple(_clamp_strength(int(s * factor)) for s in strengths)
        result.append((freqs, new_s))  # type: ignore
    return result
