
class RingBuffer:
    def __init__(self, max_size:int) -> None:
        self._max_size = max_size
        self._buffer = list()

    @property
    def max_size(self) -> int:
        return self._max_size

    def append(self, elem):
        self._buffer.append(elem)
        if len(self._buffer) > self._max_size:
            self._buffer.pop(0)

    def clear(self):
        self._buffer = list()

    def __len__(self) -> int:
        return len(self._buffer)

    def get_list(self) -> list:
        return self._buffer
