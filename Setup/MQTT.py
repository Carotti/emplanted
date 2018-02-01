from umqtt.simple import MQTTClient
import network

ap_if = network.WLAN(network.AP_IF)
ap_if.active(False)

sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect("EEERover", "exhibition")

client = MQTTClient('emplanted-iot', '192.168.0.10')
client.connect()
client.publish('esys/emplanted/test', bytes("TESTING",'utf-8'))
