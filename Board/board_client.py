from umqtt.simple import MQTTClient
import network
from machine import Pin,I2C
import time
import json

config = {
    "network": {
        "ssid": "emplanted-wifi",
        "password": "emplanted#$_"
    },
    "mqtt": {
        "name": "emplanted-iot",
        "broker": "192.168.43.92"
    },
    "th-sensor": {
        "scl": 5,
        "sda": 4,
        "freq": 100000,
        "slave-addr": 0x40,
        "commands": {
            "measure-hum": 0xF5,
            "measure-temp": 0xF3
        }
    }
}

class THSensor:
    def __init__(self, config):
        self.scl = config["scl"]
        self.sda = config["sda"]
        self.freq = config["freq"]
        self.slaveAddr = config["slave-addr"]
        self.commands = config["commands"]

    def rw(inAddress, outAddress):
        i2cport = I2C(scl=Pin(self.scl), sda=Pin(self.sda), freq=self.freq)
        i2cport.writeto(self.slaveAddr, bytearray([inAddress]))
        time.sleep(0.1) # Hack, but important!
        data=i2cport.readfrom(outAddress, 2) # Read 2 bytes
        return data

    def getTemp():
        temp = int.from_bytes(self.rw(self.commands["measure-temp"], self.slaveAddr), 'big')
        temp_celsius = (175.72*temp/65536) - 46.85
        return temp_celsius

    def getHum():
        hum = int.from_bytes(self.rw(self.commands["measure-hum"], self.slaveAddr), 'big')
        hum_perc = (125*hum/65536) - 6
        return hum_perc

class EmplantedBoard:
    def __init__(self, config):
        ap_if = network.WLAN(network.AP_IF)
        ap_if.active(False)

        sta_if = network.WLAN(network.STA_IF)

        if not sta_if.isconnected():
            sta_if.active(True)
            sta_if.connect(config["network"]["ssid"], config["network"]["password"])

        self.mqttClient = MQTTClient(config["mqtt"]["name"], config["mqtt"]["broker"])
        self.mqttClient.connect()

        self.thSensor = THSensor(config["th-sensor"])

board = EmplantedBoard(config)


# payload = json.dumps([
#     {"name":"temp-reading", "data":getTemp()},
#     {"name":"hum-reading", "data":getHum()}
# ])
# client.publish('esys/emplanted/temp', bytes(payload,'utf-8'))

# while True:
#     tmp = getTemp()
#     if tmp > 23:
#         payload = json.dumps([{"name":"warning", "text":"Temperature is above 23!"}])
#         client.publish('esys/emplanted/warnings', bytes(payload, 'utf-8'))
#     time.sleep(5)
