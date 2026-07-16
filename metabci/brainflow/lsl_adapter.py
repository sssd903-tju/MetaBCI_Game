# -*- coding: utf-8 -*-
"""
MetaBCI brainflow LSL 数据流采集适配器

基于 brainflow.ProcessWorker 模式，提供 LSL 流发现、连接与数据采集功能。
底层通过 pylsl 实现，与本项目 brainviz/pages/live_lab.py 共享同一套 LSL 逻辑。

使用示例:
    from metabci.brainflow.lsl_adapter import scan_lsl_streams, connect_lsl_stream

    streams = scan_lsl_streams()
    inlet, info = connect_lsl_stream(streams[0]['name'])
"""

from metabci.brainflow.workers import ProcessWorker


def scan_lsl_streams(timeout: float = 2.0) -> list[dict]:
    """扫描局域网内的 LSL EEG 流

    Args:
        timeout: 扫描超时 (秒)

    Returns:
        [{"name": "StreamName", "host": "hostname", "srate": 250.0, "n_channels": 8}, ...]
    """
    try:
        from pylsl import resolve_byprop
        streams = resolve_byprop('type', 'EEG', timeout=timeout)
        result = []
        for s in streams:
            info = s.desc().child("info")
            result.append({
                "name": s.name(),
                "host": s.hostname(),
                "srate": float(s.nominal_srate() or 250.0),
                "n_channels": s.channel_count(),
            })
        return result
    except ImportError:
        raise ImportError("pylsl 未安装。请运行: pip install pylsl")


def connect_lsl_stream(stream_name: str, timeout: float = 3.0):
    """连接到指定名称的 LSL EEG 流

    Args:
        stream_name: LSL 流名称
        timeout: 连接超时 (秒)

    Returns:
        (StreamInlet, stream_info_dict)
    """
    try:
        from pylsl import resolve_byprop, StreamInlet
        streams = resolve_byprop('name', stream_name, timeout=timeout)
        if not streams:
            raise RuntimeError(f"未找到 LSL 流: {stream_name}")
        info = streams[0]
        inlet = StreamInlet(info)
        return inlet, {
            "name": info.name(),
            "srate": float(info.nominal_srate() or 250.0),
            "n_channels": info.channel_count(),
        }
    except ImportError:
        raise ImportError("pylsl 未安装。请运行: pip install pylsl")


__all__ = ["ProcessWorker", "scan_lsl_streams", "connect_lsl_stream"]
