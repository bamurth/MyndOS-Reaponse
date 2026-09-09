"""Boundary-safe trailing bins over labelled condition segments."""
from __future__ import annotations

import pandas as pd


def make_bins(segments: list[tuple[float, float, str]], width: float = 10.0, step: float | None = None,
              margin_start: float = 0.0) -> pd.DataFrame:
    """Trailing bins of ``width`` seconds inside each (start, end, label) segment.

    Bins never span a boundary: the first bin ends at start + margin_start + width
    and the last bin ends at or before ``end``. Partial bins are dropped.
    Columns: t_start, t_end, condition, elapsed (bin end minus segment start),
    seg_index.
    """
    step = width if step is None else step
    rows = []
    for k, (s, e, lab) in enumerate(segments):
        t_end = s + margin_start + width
        while t_end <= e + 1e-9:
            rows.append({"t_start": t_end - width, "t_end": t_end, "condition": lab,
                         "elapsed": t_end - s, "seg_index": k})
            t_end += step
    return pd.DataFrame(rows, columns=["t_start", "t_end", "condition", "elapsed", "seg_index"])
