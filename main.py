import time
import json
import ubinascii
import machine
import network
import uasyncio as asyncio
import atom

import gc


import mhz19

from display import DirectionSensor, Display, COLOR_PPM_HEX



class Application:

    def __init__(self, matrix, display, sensor, webserver:bool=True):
        self.matrix = matrix
        self.display = display
        self.sensor = sensor
        self.last_reading = time.ticks_ms()
        self.failed_readings = 0
        self.warmuped = False
        self.current_status = {}
        self.webserver = webserver

    async def run(self):
        if self.webserver:
            from microdot_asyncio import Microdot
            from microdot_utemplate import render_template, init_templates
            init_templates("web")

            ap = network.WLAN(network.AP_IF) # create access-point interface
            ap.config(essid='CO2 Sensor ' + ubinascii.hexlify(machine.unique_id()).decode(), password="covidisnotover", authmode=network.AUTH_WPA_WPA2_PSK) # set the SSID of the access point
            ap.config(max_clients=10) # set how many clients can connect to the network
            ap.active(True)         # activate the interface

            app = Microdot()
            @app.route('/')
            async def index(request):
                return render_template("index.html", self.current_status), {'Content-Type': 'text/html'}
            @app.route('/json')
            async def json_route(request):
                return self.current_status
            @app.route('/meminfo')
            async def meminfo(request):
                free = gc.mem_free()
                alloc = gc.mem_alloc()
                return f"{100*alloc/(free+alloc):.1f} % mem used\nused: {alloc}\nfree: {free}"

        self.display.update()
        time.sleep(1)

        if self.webserver:
            await asyncio.gather(self.handle_gc(), self.handle_button_and_display(), self.handle_sensor(), app.start_server(port=80))
        else:
            await asyncio.gather(self.handle_gc(), self.handle_button_and_display(), self.handle_sensor())


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

    async def handle_gc(self):
        while True:
            gc.collect()
            await asyncio.sleep(0.01)


async def main():
    matrix = atom.Matrix()
    sensor = mhz19.MHZ19(2, tx=33, rx=23)
    direction_sensor = DirectionSensor(21, 25)
    display = Display(matrix._np, sensor, direction_sensor, brightness=20)
    application = Application(matrix, display, sensor, webserver=True)

    await application.run()


asyncio.run(main())
