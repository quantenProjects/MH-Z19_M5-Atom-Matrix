import mhz19
import time

sensor = mhz19.MHZ19(2, tx=33, rx=23)

for i in range(60, 1, -1):
    print("wait for warm up", i)
    time.sleep(1)

while True:
    if sensor.get_data() == 1:
        print("got results:")
        print(sensor.ppm)
        print(sensor.temp)
        print(sensor.co2status)
    else:
        print("read not successful")
    print("")
    time.sleep(1)

