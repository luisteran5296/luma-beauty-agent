"""Bounded TTL cache with per-key single-flight loading."""
from collections import OrderedDict
from concurrent.futures import Future
import threading
import time


class TTLCache:
    def __init__(self, capacity=128, ttl=600, clock=time.monotonic):
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self.values, self.pending, self.lock = OrderedDict(), {}, threading.Lock()

    def get(self, key, loader):
        with self.lock:
            item = self.values.get(key)
            if item and item[0] > self.clock():
                self.values.move_to_end(key)
                return item[1], True
            self.values.pop(key, None)
            owner = key not in self.pending
            future = self.pending.setdefault(key, Future())
        if not owner:
            return future.result(), True
        try:
            value = loader()
            with self.lock:
                self.values[key] = (self.clock()+self.ttl, value)
                while len(self.values) > self.capacity:
                    self.values.popitem(last=False)
            future.set_result(value)
            return value, False
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)
