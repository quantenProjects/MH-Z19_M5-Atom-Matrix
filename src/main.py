import os
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
from ringbuffer import RingBuffer



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
        self.ring_buffer = RingBuffer(60 * 8) # every minute for 8 hours
        self.last_ring_buffer_append = time.ticks_ms()
        self.ap = None

    async def run(self):
        if self.webserver:
            from microdot_asyncio import Microdot, send_file
            from microdot_utemplate import render_template, init_templates
            init_templates("web")

            self.ap = network.WLAN(network.AP_IF) # create access-point interface
            self.ap.config(essid='CO2 Sensor ' + ubinascii.hexlify(machine.unique_id()).decode(), password="covidisnotover", authmode=network.AUTH_WPA_WPA2_PSK) # set the SSID of the access point
            self.ap.config(max_clients=10) # set how many clients can connect to the network
            if self.wifi_on_boot():
                self.ap.active(True)

            app = Microdot()
            @app.route('/')
            async def index(request):
                return render_template("index.html", self.current_status, False), {'Content-Type': 'text/html'}
            @app.route('/hide_links')
            async def hide_links(request):
                return render_template("index.html", self.current_status, True), {'Content-Type': 'text/html'}
            @app.route('/plot')
            async def plot_route(request):
                return send_file("web/plot.html")
            @app.route('/chart.umd.js')
            async def chartjs(request):
                return send_file("web/chart.umd.js", max_age=86400)
            @app.route('/settings')
            async def settings_route(request):
                return send_file("web/settings.html")
            @app.route('/calibration_on')
            async def calibration_on(request):
                self.sensor.enable_self_calibration()
                return "Self calibration turned on"
            @app.route('/calibration_off')
            async def calibration_off(request):
                self.sensor.disable_self_calibration()
                return "Self calibration turned off"
            @app.route('/calibration_now')
            async def calibration_now(request):
                self.sensor.zero_point_calibration()
                return "Calibrated to zero point (400 ppm)"
            @app.route('/wifi_on_boot_enable')
            async def wifi_on_boot_enable(request):
                self.wifi_on_boot(True)
                return "Enabled wifi on boot"
            @app.route('/wifi_on_boot_disable')
            async def wifi_on_boot_disable(request):
                self.wifi_on_boot(False)
                return "Disabled wifi on boot"
            @app.route('/json')
            async def json_route(request):
                return self.current_status
            @app.route('/history')
            async def history(request):
                return self.ring_buffer.get_list()
            @app.route('/meminfo')
            async def meminfo(request):
                free = gc.mem_free()
                alloc = gc.mem_alloc()
                return f"{100*alloc/(free+alloc):.1f} % mem used\nused: {alloc}\nfree: {free}"

        self.display.update()
        time.sleep(1)
        await self.warmup()

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

    def wifi_on_boot(self, set_setting=None):
        if set_setting is None:
            try:
                os.stat("wifi_on_boot")
                return True
            except:
                return False
        else:
            try:
                if set_setting:
                    with open("wifi_on_boot", "w") as wififile:
                        wififile.write("enabled")
                else:
                    os.remove("wifi_on_boot")
            except:
                pass

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
            if time.ticks_diff(time.ticks_ms(), self.last_ring_buffer_append) > 60000:
                self.ring_buffer.append(self.sensor.ppm)
                self.last_ring_buffer_append = time.ticks_ms()
            await asyncio.sleep(0.01)

    async def handle_button_and_display(self):
        while True:
            if not self.matrix.get_button_status():
                in_menu_since = time.ticks_ms()
                state = -1
                while time.ticks_diff(time.ticks_ms(), in_menu_since) < 15000: # quit menu after 15 sec
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
                        elif state == -1 and time.ticks_diff(time.ticks_ms(), pressed_since) >= 100:
                            wifi_state = not self.ap.active()
                            self.ap.active(wifi_state)
                            self.display.set_state("wifi_on" if wifi_state else "wifi_off")
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
