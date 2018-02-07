from umqtt.simple import MQTTClient
import network
from machine import Pin,I2C
import machine
import time
import json

boardConfig = {
    "network": {
        "ssid": "emplanted-wifi",
        "password": "emplanted#$_"
    },
    "mqtt": {
        "name": "emplanted-iot",
        "broker": "192.168.43.92",
        "topic": "esys/emplanted/",
        "subscriptions": [
            "lights",
            "request"
        ]
    },
    "th-sensor": {
        "scl": 5,
        "sda": 4,
        "freq": 100000,
        "slave-addr": 0x40,
        "htr-ctrl-value" : 0xF,
        "htr-write-cmd" : 0x51,
        "user-reg1" : 0xE6,
        "commands": {
            "measure-hum": 0xF5,
            "measure-temp": 0xF3
        }
    },
    "lights": {
        "pin": 14,
        "default-state": 0
    }
}

class THSensor:
    def __init__(self, config):
        self.scl = config["scl"]
        self.sda = config["sda"]
        self.freq = config["freq"]
        self.slaveAddr = config["slave-addr"]
        self.commands = config["commands"]
        self.wrt-htr = config["htr-ctrl-cmd"]
        self.htr-value = config["htr-ctrl-value"]
        self.htr-strt = config["user-reg1"]
        self.setHtrCtrl()

    def setHtrCtrl(self):
        i2cport = I2C(scl=Pin(self.scl), sda=Pin(self.sda), freq=self.freq)
        write(self.wrt-htr, i2cport) # Command for writing to heater
        time.sleep(0.1) # Hack, but important (Maybe????)!
        write(self.htr-value, i2cport) # Value to be written to heater


    def write(self, inAddress, i2cport):
        i2cport.writeto(self.slaveAddr, bytearray([inAddress]))
        pass

    def rw(self, inAddress, outAddress):
        i2cport = I2C(scl=Pin(self.scl), sda=Pin(self.sda), freq=self.freq)
        write(inAddress, i2cport)
        time.sleep(0.1) # Hack, but important!
        data=i2cport.readfrom(outAddress, 2) # Read 2 bytes
        return data

    def getTemp(self):
        temp = int.from_bytes(self.rw(self.commands["measure-temp"], self.slaveAddr), 'big')
        temp_celsius = (175.72*temp/65536) - 46.85
        return temp_celsius

    def getHum(self):
        i2cport = I2C(scl=Pin(self.scl), sda=Pin(self.sda), freq=self.freq)
        write(self.htr-strt, i2cport) # Command for writing to user register 1
        write(0x4, i2cport) # Turn on heater, bit 2 of user register 1
        time.sleep(10) # Sleep for 10 seconds to drive off condensation
        write(self.htr-strt, i2cport) # Command for writing to user register 1
        write(0x0, i2cport) # Turn off heater, bit 2 of user register 1
        hum = int.from_bytes(self.rw(self.commands["measure-hum"], self.slaveAddr), 'big')
        hum_perc = (125*hum/65536) - 6
        return hum_perc

class Lights:
    def __init__(self, config):
        self.pin = Pin(config["pin"], Pin.OUT)
        self.pin.value(config["default-state"])

    def enable(self):
        self.pin.value(0)

    def disable(self):
        self.pin.value(1)

class EmplantedBoard:
    def mqttReceivedLights(self, msg):
        if (msg == "ON"):
            self.lights.enable()
        elif (msg == "OFF"):
            self.lights.disable()

    def mqttReceivedRequest(self, msg):
        requests = json.loads(msg)
        readings = {}
        for i in requests:
            reading = None
            if i == "temp":
                reading = self.thSensor.getTemp()
            elif i == "hum":
                reading = self.thSensor.getHum()
            readings[i] = reading
        self.mqttPublish("readings", json.dumps(readings))

    def mqttReceived(self, topic, msg):
        topicStr = topic.decode("utf-8")
        msgStr = msg.decode("utf-8")

        if topicStr == (self.mqttTopic + "lights"):
            self.mqttReceivedLights(msgStr)

        if topicStr == (self.mqttTopic + "request"):
            self.mqttReceivedRequest(msgStr)

    def __init__(self, config):
        ap_if = network.WLAN(network.AP_IF)
        ap_if.active(False)

        sta_if = network.WLAN(network.STA_IF)

        sta_if.active(True)
        sta_if.connect(config["network"]["ssid"], config["network"]["password"])

        while not sta_if.isconnected():
            machine.idle()

        self.mqttClient = MQTTClient(config["mqtt"]["name"], config["mqtt"]["broker"])
        self.mqttTopic = config["mqtt"]["topic"]
        self.mqttClient.set_callback(self.mqttReceived)
        self.mqttClient.connect()
        for i in config["mqtt"]["subscriptions"]:
            self.mqttClient.subscribe(self.mqttTopic + i)

        self.thSensor = THSensor(config["th-sensor"])

        self.lights = Lights(config["lights"])

    def mqttPublish(self, topic, payload):
        self.mqttClient.publish(self.mqttTopic + topic, bytes(payload, 'utf-8'))

    def mqttCheck(self):
        self.mqttClient.check_msg()

    def mqttWait(self):
        self.mqttClient.wait_msg()

board = EmplantedBoard(boardConfig)

while True:
    board.mqttCheck()
    time.sleep(1)

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
