import mhz19
import time
import math

import atom

class Display:

    COLOR_PPM = [ (500, (0,0,1)), (800, (0,1,0)), (1000, (1,1,0)), (1400, (1,0.5,0)), (100000, (1,0,0))]

    def __init__(self, neopixel, brightness=1.0) -> None:
        self.np = neopixel
        self.state = "boot"
        self.brightness = brightness
        self._reset_ticks()
        self.ppm = -1

    def _reset_ticks(self) -> None:
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

    def set_state(self, state):
        self.state = state
        self._reset_ticks()
        display.update()

    def update(self):
        if self.state == "boot":
            for i in range(len(self.np)):
                color = self._bn((1, 1, 1) if i % 2 == 0 else (0,0,0))
                self.np[i] = color
        elif self.state == "warmup":
            self._set_black()
            warmup_time = 60 * 1000
            current_progress = len(self.np) * self._ticks() / warmup_time
            current_index = math.floor(current_progress)
            for i in range(current_index):
                self.np[i] = self._bn((1,1,1))
            self.np[current_index] = self._bn((1,1,1), current_progress % 1)
        elif self.state == "display":
            if self.ppm < 0:
                for i in range(len(self.np)):
                    color = self._bn((1,0,0) if i % 2 == 0 else (0,1,0))
                    self.np[i] = color
            else:
                self._set_black()
                color = (0,0,0)
                for threshold, color_of_threshold in self.COLOR_PPM:
                    color = color_of_threshold
                    if threshold > self.ppm:
                        break
                for i in range(15):
                    self.np[i] = self._bn(color)

                hundrest_ppm = math.floor(self.ppm / 100)
                color = (1,1,1)
                for i in range(5):
                    self.np[24 - i] = self._bn(color if hundrest_ppm & 2**i > 0 else (0,0,0))
        elif self.state.startswith("setting_"):
            self._set_black()
            self.np[0] = self._bn(self._get_settings_color())
        elif self.state.startswith("applied_"):
            for i in range(len(self.np)):
                self.np[i] = self._bn(self._get_settings_color())
        self.np.write()

matrix = atom.Matrix()

sensor = mhz19.MHZ19(2, tx=33, rx=23)
display = Display(matrix._np, 20)
display.update()
time.sleep(2)

display.set_state("warmup")
print("warmup")
start = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), start) < 6 * 1000:
    display.update()
    time.sleep(0.1)
while sensor.ppm == 500 or sensor.ppm == 515 or sensor.ppm == -1:
    sensor.get_data()
    print(sensor.ppm)
    for i in range(10):
        display.update()
        time.sleep(0.1)
print("warmup completed")


display.set_state("display")

failed_readings = 0
last_reading = time.ticks_ms()

while True:
    if time.ticks_diff(time.ticks_ms(), last_reading) > 1000:
        if sensor.get_data() == 1:
            print(f"time {time.ticks_ms()},  {sensor.ppm} ppm, {sensor.temp} temp, {sensor.co2status} status")
            display.ppm = sensor.ppm
            failed_readings = 0
        else:
            failed_readings += 1
            if failed_readings > 5:
                display.ppm = -1
            print("read not successful")
        last_reading = time.ticks_ms()
    # TODO implement button and calibration stuff
    if not matrix.get_button_status():
        in_menu_since = time.ticks_ms()
        state = -1
        while time.ticks_diff(time.ticks_ms(), in_menu_since) < 15000:
            if not matrix.get_button_status():
                pressed_since = time.ticks_ms()
                while not matrix.get_button_status() and time.ticks_diff(time.ticks_ms(), pressed_since) < 2000:
                    time.sleep(0.1)
                if time.ticks_diff(time.ticks_ms(), pressed_since) >= 2000:
                    if state == -1:
                        state = 0
                    elif state == 0:
                        # TODO cali
                        display.set_state("applied_cali")
                        time.sleep(2)
                        break
                    elif state == 1:
                        # TODO on
                        display.set_state("applied_on")
                        time.sleep(2)
                        break
                    elif state == 2:
                        # TODO off
                        display.set_state("applied_off")
                        time.sleep(2)
                        break
                else:
                    if state == -1:
                        break
                    else:
                        state = (state + 1) % 3
                if state >= 0:
                    display.set_state(("setting_cali", "setting_on", "setting_off")[state])
                    display.update()
                time.sleep(1)
                in_menu_since = time.ticks_ms()
            time.sleep(0.1)
        display.set_state("display")

    display.update()
    time.sleep(0.01)

