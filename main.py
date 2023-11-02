import time
import math
import json
import ubinascii
import machine
import network
import uasyncio as asyncio
import atom

from microdot_asyncio import Microdot
from microdot_utemplate import render_template, init_templates

from mpu6886 import MPU6886
import mhz19

init_templates("web")

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

class SensorAndDisplay:

    def __init__(self, matrix, display, sensor):
        self.matrix = matrix
        self.display = display
        self.sensor = sensor
        self.last_reading = time.ticks_ms()
        self.failed_readings = 0
        self.warmuped = False
        self.current_status = {}


    def update_status(self, status: str, values: Optional[dict] = None):
        if values is None:
            values = {}
        prototype_dict = {"status": status, "time": time.ticks_ms()}
        self.current_status = prototype_dict | values
        print(json.dumps(self.current_status))

    async def warmup(self):
        if self.warmuped:
            return
        self.display.set_state("warmup")
        self.update_status("warmup")
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 6 * 1000:
            self.display.update()
            await asyncio.sleep(0.1)
        while self.sensor.ppm == 500 or self.sensor.ppm == 515 or self.sensor.ppm == -1:
            self.sensor.get_data()
            self.update_status("warmup, waiting 500")
            for i in range(10):
                self.display.update()
                await asyncio.sleep(0.1)
        self.update_status("warmup completed")
        self.display.set_state("display")
        self.warmuped = True

    async def handle_sensor(self):
        while True:
            if time.ticks_diff(time.ticks_ms(), self.last_reading) > 2000:
                if self.sensor.get_data() == 1:
                    self.display.reset_ticks()
                    color = "FFFFFF"
                    rating = ""
                    for threshold, color_of_threshold, rating_of_threshold in COLOR_PPM_HEX:
                        color = color_of_threshold
                        rating = rating_of_threshold
                        if threshold > self.sensor.ppm:
                            break
                    self.update_status("valueok", values={"ppm": self.sensor.ppm, "temp": self.sensor.temp, "co2status": self.sensor.co2status, "color": color, "rating": rating})
                    self.failed_readings = 0
                else:
                    self.failed_readings += 1
                    if self.failed_readings > 5:
                        self.sensor.ppm = -1
                    self.update_status("read not successful")
                self.last_reading = time.ticks_ms()
            await asyncio.sleep(0.01)

    async def handle_button_and_display(self):
        await self.warmup()
        while True:
            if not self.matrix.get_button_status():
                in_menu_since = time.ticks_ms()
                state = -1
                while time.ticks_diff(time.ticks_ms(), in_menu_since) < 15000:
                    if not self.matrix.get_button_status():
                        pressed_since = time.ticks_ms()
                        while not self.matrix.get_button_status() and time.ticks_diff(time.ticks_ms(), pressed_since) < 2000:
                            time.sleep(0.1)
                        if time.ticks_diff(time.ticks_ms(), pressed_since) >= 2000:
                            if state == -1:
                                state = 0
                            elif state == 0:
                                self.display.set_state("applied_cali")
                                if not self.sensor.zero_point_calibration():
                                    self.display.set_state("error")
                                    while True:
                                        pass
                                time.sleep(2)
                                break
                            elif state == 1:
                                self.display.set_state("applied_on")
                                if not self.sensor.enable_self_calibration():
                                    self.display.set_state("error")
                                    while True:
                                        pass
                                time.sleep(2)
                                break
                            elif state == 2:
                                self.display.set_state("applied_off")
                                if not self.sensor.disable_self_calibration():
                                    self.display.set_state("error")
                                    while True:
                                        pass
                                time.sleep(2)
                                break
                        else:
                            if state == -1:
                                break
                            else:
                                state = (state + 1) % 3
                        if state >= 0:
                            self.display.set_state(("setting_cali", "setting_on", "setting_off")[state])
                            self.display.update()
                        time.sleep(1)
                        in_menu_since = time.ticks_ms()
                    time.sleep(0.1)
                self.display.set_state("display")

            self.display.update()
            await asyncio.sleep(0.01)




async def main():
    matrix = atom.Matrix()

    sensor = mhz19.MHZ19(2, tx=33, rx=23)
    direction_sensor = DirectionSensor(21, 25)
    display = Display(matrix._np, sensor, direction_sensor, brightness=20)
    sd_handler = SensorAndDisplay(matrix, display, sensor)

    ap = network.WLAN(network.AP_IF) # create access-point interface
    ap.config(essid='CO2 Sensor ' + ubinascii.hexlify(machine.unique_id()).decode(), password="covidisnotover", authmode=network.AUTH_WPA_WPA2_PSK) # set the SSID of the access point
    ap.config(max_clients=10) # set how many clients can connect to the network
    ap.active(True)         # activate the interface

    app = Microdot()
    @app.get('/')
    async def index(request):
        return render_template("index.html", sd_handler.current_status), {'Content-Type': 'text/html'}
    @app.route('/json')
    async def json_route(request):
        return sd_handler.current_status

    display.update()
    time.sleep(1)

    await asyncio.gather(sd_handler.handle_button_and_display(), sd_handler.handle_sensor(), app.start_server(port=80))

asyncio.run(main())
