"""Saturation signals (P6, CTL-410, ADR-007).

Queue age leads, because depth alone cannot distinguish a queue that is draining from one that is not. Multiple
signals, never depth alone. Counters are plain and separate: merging two outcomes into one counter would hide exactly
what this episode is about.
"""
import threading


class Signals:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = {}
        self._gauges = {}

    def increment(self, name, by=1):
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + by

    def gauge(self, name, value):
        with self._lock:
            self._gauges[name] = value

    def counter(self, name):
        return self._counters.get(name, 0)

    def snapshot(self):
        with self._lock:
            return {"counters": dict(self._counters), "gauges": dict(self._gauges)}
