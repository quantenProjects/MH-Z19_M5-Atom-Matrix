# MH-Z19 CO2 Sensor for a M5 Stack Atom Matrix ESP32

__License MIT__


## Features

* Color display of CO2 level
* Binary encoded ppm value
* WIFI AP with Website
    * Exact ppm value with color indication and rating
    * History plot for the last 8 hours (lost on powercycle)
    * API

## Install

Developed for `M5STACK_ATOM-20231005-v1.21.0.bin` from https://micropython.org/download/M5STACK_ATOM/

```
cd src/
mpremote u0 fs cp -r . :
mpremote u0 soft-reset # or powercycle
```

## Hardware

Connect a MH-Z19 CO2 Sensor to the M5 Stack Atom Matrix:

* 5V to 5V
* GND to GND
* TX to G23
* RX to G33

### BOM

* M5 Stack Atom Matrix with ESP32
* Winsen MH Z19 CO2 Sensor
* Maybe a case, e.g. M5Stack ATOM HUB DIY Proto Board Kit

Any other MicroPython Board with 25 Neopixel should also work. You then may need to adapt the pins in the code.

The Atom Matrix is complete, has a case, a button and everything and the only soldering is the 4 pin connection for the CO2 Sensor.

### Sourcing Option in Germany

All parts available at berrybase.de (not sponsored or anything)

Price as of October 2023: about 45€ without case, 55€ with case

## Used Libs

### Adapted MH-Z19 CO2 Sensor Lib

https://github.com/overflo23/MH-Z19_MicroPython

Author: Florian "overflo" Bittner - 12/2020 

https://github.com/nara256/mhz19_uart/blob/master/src/MHZ19_uart.cpp

### Webserver

https://github.com/pfalcon/utemplate/

https://github.com/miguelgrinberg/microdot

https://www.chartjs.org/

## Acceleration Sensor

https://github.com/tuupola/micropython-mpu6886

