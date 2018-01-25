from machine import Pin,I2C

i2cport = I2C(scl=Pin(5), sda=Pin(4), freq=100000)
i2cport.writeto(0x40, bytearray([0xf3]))
data=i2cport.readfrom(0x40, 2)
int.from_bytes(data, 'big')
