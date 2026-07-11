#!/usr/bin/env python3
"""Replay BDF file as LSL stream for testing online classification.

Usage:
    python replay_bdf_lsl.py [bdf_path]
"""

import sys
import time
from pathlib import Path

import numpy as np
import mne
from pylsl import StreamInfo, StreamOutlet

FS = 250.0
STREAM_NAME = "brain-cube-eeg"
STREAM_TYPE = "EEG"


def main():
    bdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path.home() / "Downloads" / "测试数据3.bdf")

    print(f"Loading {bdf_path.name}...")
    raw = mne.io.read_raw_bdf(str(bdf_path), preload=True)
    data = raw.get_data()
    n_ch = data.shape[0]
    n_samples = data.shape[1]
    ch_names = raw.ch_names
    print(f"  {n_ch} channels: {ch_names}")
    print(f"  {n_samples} samples @ {FS}Hz = {n_samples/FS:.1f}s")

    # Create LSL stream
    info = StreamInfo(
        STREAM_NAME, STREAM_TYPE, n_ch, FS, "float32",
        source_id="bdf_replay",
    )
    # Set channel names
    ch_info = info.desc().append_child("channels")
    for name in ch_names:
        ch = ch_info.append_child("channel")
        ch.append_child_value("label", name)

    outlet = StreamOutlet(info)
    print(f"LSL stream '{STREAM_NAME}' created. Waiting for consumers...")

    # Wait for consumer to connect (or timeout)
    timeout = time.time() + 30
    while time.time() < timeout:
        if outlet.wait_for_consumers(0.1):
            break
    print("Consumer connected!" if time.time() < timeout else "No consumer — streaming anyway...")

    # Stream data in chunks of ~20 samples (80ms) for low latency
    chunk_size = 20
    sample_idx = 0
    start_time = time.time()

    try:
        while sample_idx < n_samples:
            end_idx = min(sample_idx + chunk_size, n_samples)
            chunk = data[:, sample_idx:end_idx]  # (n_ch, chunk_size)

            for i in range(chunk.shape[1]):
                sample = [float(chunk[ch, i]) for ch in range(n_ch)]
                # Timestamp based on BDF position
                ts = sample_idx / FS
                outlet.push_sample(sample)

                # Maintain real-time pace
                elapsed = time.time() - start_time
                expected = (sample_idx + 1) / FS
                if elapsed < expected:
                    time.sleep(min(0.02, expected - elapsed))

            sample_idx = end_idx

            if sample_idx % 2500 == 0:
                elapsed = time.time() - start_time
                progress = sample_idx / n_samples * 100
                print(f"  {progress:.0f}% ({sample_idx}/{n_samples}) "
                      f"elapsed={elapsed:.1f}s", end="\r")

    except KeyboardInterrupt:
        print("\nStopped by user")

    print(f"\nDone. Streamed {sample_idx} samples in {time.time()-start_time:.1f}s")


if __name__ == "__main__":
    main()
