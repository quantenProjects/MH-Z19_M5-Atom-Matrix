import machine
import math
import time

from mpu6886 import MPU6886

COLOR_PPM = [ (500, (0,0,1)), (800, (0,1,0)), (1000, (1,1,0)), (1400, (1,0.5,0)), (100000, (1,0,0))]
COLOR_PPM_HEX = [ (500, "00C0F0", "excellent"), (800, "10D653", "good"), (1000, "FFFD13", "okay"), (1400, "FF6B0F", "bad"), (100000, "FF3C13", "terrible")]

class DirectionSensor:

    def __init__(self, scl, sda):
        self.i2c = machine.SoftI2C(scl=machine.Pin(scl), sda=machine.Pin(sda))
        self.sensor = MPU6886(self.i2c)
        self.direction = 0

    def whoami(self):
        return self.sensor.whoami

    def tick(self):
        x, y, z = self.sensor.acceleration
        if abs(z) > abs(x) and abs(z) > abs(y):
            self.direction = 0
        elif abs(x) > abs(y):
            self.direction = 1 if x > 0 else 3
        else:
            self.direction = 0 if y > 0 else 2

class Display:


    def __init__(self, neopixel, sensor, direction_sensor, brightness=1.0) -> None:
        self.np = neopixel
        self.state = "boot"
        self.brightness = brightness
        self.reset_ticks()
        self.sensor = sensor
        self.direction_sensor = direction_sensor

    def reset_ticks(self) -> None:
        self.tick_base = time.ticks_ms()
    
    def _ticks(self) -> float:
        return time.ticks_diff(time.ticks_ms(), self.tick_base)

    def _set_black(self) -> None:
        for i in range(len(self.np)):
            self.np[i] = (0,0,0)

    def _bn(self, color, additional_brightness=1.0):
        return [int(value * self.brightness * max(additional_brightness, 0)) for value in color]

    def _get_settings_color(self) -> tuple[float,float,float]:
        if self.state.endswith("on"):
            return (0, 1, 0)
        elif self.state.endswith("off"):
            return (1, 0, 0)
        elif self.state.endswith("cali"):
            return (0, 0, 1)
        return (0,0,0)

    def _xy_to_index(self, x, y) -> int:
        WIDTH = 5
        return x + y * WIDTH

    def _index_to_xy(self, index) -> tuple[int, int]:
        WIDTH = 5
        return index % WIDTH, index // WIDTH

    def _rotate_xy(self, x, y) -> tuple[int, int]:
        WIDTH = 5
        direction = self.direction_sensor.direction
        if direction == 1:
            x = WIDTH - 1 - x
            x, y = y, x
        elif direction == 2:
            x = WIDTH - 1 - x
            y = WIDTH - 1 - y
        elif direction == 3:
            y = WIDTH - 1 - y
            x, y = y, x
        return x, y

    def _rotate_index(self, index) -> int:
        x, y = self._index_to_xy(index)
        x, y = self._rotate_xy(x, y)
        return self._xy_to_index(x, y)

    def set_state(self, state):
        self.state = state
        self.reset_ticks()
        self.update()

    def update(self):
        self.direction_sensor.tick()
        if self.state == "boot":
            for i in range(len(self.np)):
                color = self._bn((1, 1, 1) if i % 2 == 0 else (0,0,0))
                self.np[self._rotate_index(i)] = color
        elif self.state == "error":
            for i in range(len(self.np)):
                color = self._bn((1, 0, 0) if i % 2 == 0 else (0,0,1))
                self.np[self._rotate_index(i)] = color
        elif self.state == "warmup":
            self._set_black()
            warmup_time = 60 * 1000
            current_progress = (len(self.np) * self._ticks() / warmup_time) % len(self.np)
            current_index = math.floor(current_progress)
            for i in range(current_index):
                self.np[self._rotate_index(i)] = self._bn((1,1,1))
            self.np[self._rotate_index(current_index)] = self._bn((1,1,1), current_progress % 1)
        elif self.state == "display":
            self._set_black()
            if self.sensor.ppm < 0:
                for i in range(15):
                    color = self._bn((1,0,0) if i % 2 == 0 else (0,1,0), additional_brightness=0.2)
                    self.np[self._rotate_index(i)] = color
            else:
                color = (0,0,0)
                for threshold, color_of_threshold in COLOR_PPM:
                    color = color_of_threshold
                    if threshold > self.sensor.ppm:
                        break
                for i in range(15):
                    self.np[self._rotate_index(i)] = self._bn(color)

                if self._ticks() < 1000:
                    self.np[self._rotate_index(19)] = self._bn(color, additional_brightness=(1 - (self._ticks()/1000))*0.5)

                hundrest_ppm = math.floor(self.sensor.ppm / 100)
                color = (1,1,1)
                for i in range(5):
                    self.np[self._rotate_index(24 - i)] = self._bn(color if hundrest_ppm & 2**i > 0 else (0,0,0))
        elif self.state.startswith("setting_"):
            self._set_black()
            self.np[self._rotate_index(0)] = self._bn(self._get_settings_color())
        elif self.state.startswith("applied_"):
            for i in range(len(self.np)):
                self.np[self._rotate_index(i)] = self._bn(self._get_settings_color())
        self.np.write()
