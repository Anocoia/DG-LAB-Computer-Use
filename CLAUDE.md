# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
pip install -r requirements.txt
python main.py
```

No build step, test suite, or linter configured.

## Architecture

PyQt6 desktop app controlling DG-LAB devices via WebSocket. Uses `qasync` to bridge asyncio with Qt's event loop.

### Data Flow

```
Monitors (system/input/app) → emit Qt signals
    → Modules (7 types) process events, emit strength_output(name, val_a, val_b) [0.0-1.0]
        → StrengthManager mixes all outputs (MAX/SUM/AVG), applies smoothing + limits + multiplier
            → Sends final int values (0-200) to device via WebSocket
```

### Key Components

- **`main.py`** — Entry point. Creates QApplication, applies pink-themed stylesheet, starts qasync event loop.
- **`app/main_window.py`** — Orchestrator. Wires all signals, manages module lifecycle, hosts 9 tabs in a stacked widget. Contains `_apply_*_config()` slots that translate tab UI dicts into module runtime parameters. Has `get_full_config()`/`apply_full_config()` for JSON save/load. Starts monitors/modules/StrengthManager at init for preview mode; only wave timer and device sending are gated on connection.
- **`app/connection.py`** — WebSocket connection manager. Supports local (embedded server + QR code) and remote modes. Handles reconnection with exponential backoff.
- **`app/strength_manager.py`** — Central mixer. 100ms async loop collects normalized module outputs, mixes per channel, applies global limits/multiplier/smoothing, calls back to send strength to device. `get_active_sources()` returns modules with non-zero output for source display.
- **`app/waveform.py`** — Preset waveform definitions. Pulses are `(frequencies_tuple, strengths_tuple)` fed to the device every 500ms.

### Monitors (`app/monitors/`)

Read-only system watchers that emit Qt signals:
- **SystemMonitor** — CPU, memory, network, disk (async loop, configurable interval)
- **InputMonitor** — Mouse clicks/move/scroll, keyboard (pynput daemon threads)
- **AppMonitor** — Active window title/process tracking

### Modules (`app/modules/`)

All 7 modules inherit `QObject`, run async loops, and emit `strength_output(str, float, float)`. Each has `enabled` flag, `channel` setting, `start()`/`stop()` lifecycle. All default to `enabled=False`.

### Widgets (`app/widgets/`)

Each module has a corresponding tab widget. Tabs emit `config_changed(dict)` when UI controls change. Each tab has `get_config() -> dict` and `set_config(dict)` for serialization. The 4 tabs without a pre-existing enable checkbox (SystemTab, InputTab, AppTab, DiceTab) have `_enable_cb`; the other 3 (TimerTab, IdleTab, RhythmTab) already had one.

**MiniMonitor** (`mini_monitor.py`) — Frameless always-on-top mini window showing real-time A/B strength bars and per-module source breakdown. Toggled from main UI "小窗" button; source visibility controlled by "小窗来源" checkbox. Sources display actual strength integers (module raw value × limit × multiplier).

### Signal Wiring Pattern

Tab `config_changed` → MainWindow `_apply_*_config()` → sets module attributes. Module `strength_output` → `StrengthManager.update_module()`. Waveform requests from modules → MainWindow updates active preset name.

### Preview Mode

Monitors, modules, and StrengthManager start at app init (`_start_preview`), not on device bind. `_send_strength` skips actual WebSocket calls when `is_bound` is false. Only the waveform feed timer starts/stops with connection. This lets users see computed strength output in the UI and MiniMonitor without a device.

### Channel Convention

Channel combo boxes use items `["A 通道", "B 通道", "AB 通道"]` (index 0/1/2). Config dicts store `"A"`, `"B"`, or `"AB"` strings. Modules route output to channels via `if channel in ("A", "AB")` pattern.

## Language

All UI text is in Chinese (simplified). Code comments mix Chinese and English.
