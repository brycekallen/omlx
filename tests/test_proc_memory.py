# SPDX-License-Identifier: Apache-2.0
"""Tests for omlx.utils.proc_memory.get_phys_footprint."""

import os
import sys

import pytest

from omlx.utils.proc_memory import get_phys_footprint


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin-only API")
class TestGetPhysFootprintDarwin:
    def test_returns_positive_for_current_process(self):
        v = get_phys_footprint()
        assert v > 0
        # Python interpreter alone should be at least a few MB.
        assert v > 4 * 1024**2

    def test_explicit_pid_matches_default(self):
        v_default = get_phys_footprint()
        v_explicit = get_phys_footprint(pid=os.getpid())
        # Phys can change between two calls (running interpreter), but
        # should be within a small drift band.
        assert abs(v_default - v_explicit) < 32 * 1024**2

    def test_invalid_pid_returns_zero(self):
        # PID 0 is the kernel — proc_pid_rusage refuses it.
        assert get_phys_footprint(pid=0) == 0

    def test_includes_python_heap(self):
        import mmap as _mmap

        baseline = get_phys_footprint()
        size = 64 * 1024 * 1024
        # Use mmap to get fresh OS pages that are guaranteed not to be
        # already present in the process phys_footprint (bypasses Python's
        # allocator page reuse which causes bytearray to silently recycle
        # already-counted pages, giving baseline == after in CI).
        mm = _mmap.mmap(-1, size)
        try:
            # Write unique data to each page so pages are dirty and resident,
            # and cannot be deduplicated or trivially compressed.
            for i in range(0, size, 4096):
                mm[i : i + 4] = i.to_bytes(4, "little")
            after = get_phys_footprint()
        finally:
            mm.close()
        # phys should have grown by at least most of the allocation.
        assert after - baseline > 32 * 1024 * 1024


class TestGetPhysFootprintFallback:
    def test_returns_zero_on_non_darwin(self, monkeypatch):
        # Simulate libproc unavailable.
        monkeypatch.setattr("omlx.utils.proc_memory._proc_pid_rusage", None)
        assert get_phys_footprint() == 0
        assert get_phys_footprint(pid=12345) == 0
