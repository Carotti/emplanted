from machine import Pin,I2C
import time

def rw(inAddress, outAddress):
    i2cport = I2C(scl=Pin(5), sda=Pin(4), freq=100000)
    i2cport.writeto(0x40, bytearray([inAddress]))
    time.sleep(0.1)
    data=i2cport.readfrom(outAddress, 2)
    return data

def getTemp():
    temp = int.from_bytes(rw(0xf3, 0x40), 'big')
    temp_celsius = (175.72*temp/65536) - 46.85
    return temp_celsius

def getHum():
    hum = int.from_bytes(rw(0xf5, 0x40), 'big')
    hum_perc = (125*hum/65536) - 6
    return hum_perc
