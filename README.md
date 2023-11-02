# MH-Z19 CO2 Sensor from Winsen


## Install

Developed for `M5STACK_ATOM-20231005-v1.21.0.bin` from https://micropython.org/download/M5STACK_ATOM/

```
mpremote u0 fs cp *.py :
mpremote u0 fs cp -r web :
mpremote u0 fs cp -r utemplate :
```

## Used Libs

https://github.com/pfalcon/utemplate/

https://github.com/miguelgrinberg/microdot

https://github.com/tuupola/micropython-mpu6886

## old readme:

__MH-Z19B + MH-Z19C driver for MicroPython__



This library implements a simple class to get data from the MH-Z19 Sensors

It will tell you 
* PPM 
* Room temperature (not very accurate) - not documented in Module Datasheet
* CO2 Status (whatever that is)  -   Neither documented in Module Datasheet



Author: Florian "overflo" Bittner - 12/2020 

 [Projects](https://overflo.info) 
 
 [Twitter](https://twitter.com/overflo) 
 
 [Github](https://github.com/overflo23)



*Version 0.1*

__License MIT__


Some hints taken from:
https://github.com/nara256/mhz19_uart/blob/master/src/MHZ19_uart.cpp




USE LIKE:

```
import mhz19

#init sensor on UART #1
sensor = mhz19.mhz19(1)

#update data from sensor
sensor.get_data()

print('ppm:',    sensor.ppm)
print('temp:',   sensor.temp)
print('status:', sensor.co2status)
```
