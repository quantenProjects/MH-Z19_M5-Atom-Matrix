"""
MH-Z19 CO2 Sensor from Winsen
MH-Z19B + MH-Z19C  driver for MicroPython

Author: Florian "overflo" Bittner - 12/2020
Find me here:    https://overflo.info / https://twitter.com/overflo / https://github.com/overflo23


Version 0.1
License MIT


Some hints taken from:
https://github.com/nara256/mhz19_uart/blob/master/src/MHZ19_uart.cpp



This implements a simple class to get data from the MH-Z19 Sesors
It will tell you 
 - PPM 
 - Room temperature (not very accurate) - not documented in Module Datasheet
 - CO2 Status (whatever that is)  -   Neither documented in Module Datasheet

"""
from machine import UART
import time
import sys


class MHZ19:
    def __init__(self,  uart_no, tx, rx):
        self.uart_no = uart_no
        self.tx = tx
        self.rx = rx
        self.start()
        self.ppm = -1
        self.temp = 0
        self.co2status = 0

    def start(self):
        self.uart = UART(self.uart_no, 9600, tx=self.tx, rx=self.rx)
        self.uart.init(9600, bits=8, parity=None, stop=1, timeout=10, tx=self.tx, rx=self.rx)

    def stop(self):
        while self.uart.any():
            self.uart.read(1)
        self.uart.deinit()

    def _send_comand(self, byte2:bytes, byte3:bytes = b"\x00") -> bool:
        command = b"\xff\x01" + byte2 + byte3 + b"\x00\x00\x00\x00"
        return self.uart.write(command + self.crc8(command).to_bytes(1, "big")) == 9

    def disable_self_calibration(self) -> bool:
        return self._send_comand(b"\x79", b"\x00")

    def enable_self_calibration(self) -> bool:
        return self._send_comand(b"\x79", b"\xA0")

    def zero_point_calibration(self) -> bool:
        return self._send_comand(b"\x87")

    def get_data(self) -> int:
        self.uart.write(b"\xff\x01\x86\x00\x00\x00\x00\x00\x79")
        time.sleep(0.1)
        s = self.uart.read(9)
        try:
            z = bytearray(s)
        except:
            return 0
        # Calculate crc
        crc = self.crc8(s)
        if crc != z[8]:
            # we should restart the uart comm here..
            self.stop()
            time.sleep(1)
            self.start()

            print('CRC error calculated %d bytes= %d:%d:%d:%d:%d:%d:%d:%d crc= %dn' % (
                crc, z[0], z[1], z[2], z[3], z[4], z[5], z[6], z[7], z[8]))
            return 0
        else:
            self.ppm = ord(chr(s[2])) * 256 + ord(chr(s[3]))
            self.temp = ord(chr(s[4])) - 40
            self.co2status = ord(chr(s[5]))
            return 1

    def crc8(self, a) -> int:
        crc = 0x00
        count = 1
        b = bytearray(a)
        while count < 8:
            crc += b[count]
            count = count+1
        # Truncate to 8 bit
        crc %= 256
        # Invert number with xor
        crc = ~crc & 0xFF
        crc += 1
        return crc
