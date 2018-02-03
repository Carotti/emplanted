from umqtt.simple import MQTTClient
import network
from machine import Pin,I2C
import time
import json

config = [
    {"wifi": {
            "ssid": "emplabted-wifi",
            "password": "emplanted#$_"
        }
    },
    {"sensor": {
            "i2c": {
                "scl-pin": 5,
                "sda-pin": 4
            }
        }
    }
]

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

ap_if = network.WLAN(network.AP_IF)
ap_if.active(False)

sta_if = network.WLAN(network.STA_IF)

if not sta_if.isconnected():
    sta_if.active(True)
    sta_if.connect("emplanted-wifi", "emplanted#$_")

client = MQTTClient('emplanted-iot', '192.168.43.92')
client.connect()
# payload = json.dumps([
#     {"name":"temp-reading", "data":getTemp()},
#     {"name":"hum-reading", "data":getHum()}
# ])
# client.publish('esys/emplanted/temp', bytes(payload,'utf-8'))

while True:
    tmp = getTemp()
    if tmp > 23:
        payload = json.dumps([{"name":"warning", "text":"Temperature is above 23!"}])
        client.publish('esys/emplanted/warnings', bytes(payload, 'utf-8'))
    time.sleep(5)
