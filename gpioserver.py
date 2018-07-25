
import os.path
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import Adafruit_BBIO.GPIO as GPIO
import threading
import time
# import datetime   # will need for filter auto run 1 hour/day every day
from tornado.ioloop import PeriodicCallback  # used to send data to client once a second

# notes:
# 1. error checking needed for 1 wire program will fail if 3 temp sensors are not connected  on GPIO P9-12
# 2. system uses 4 relay ebay type output board and 3 DS18d20 digital temperature sensors
# 3. all javascript is in index.html
# 4.
#
#
#
#
#

tempw = " "  # water Temperature
tempg = " "  # water Temperature
tempo = " "  # water Temperature
mode = 0   # mode 0 stop filter
           # mode 1 filter water 1 hour time out
           # mode 2 run hot tub 2 hour time out
           # mode 3 heat greenhouse
           # mode 4 shut down greenhouse or hot tub => go to mode 0
           # mode 5
set_water = 105.0 # hot tub water setting
cd_time = 0
time_till = 0  # estimated time for water to reach temp
time.sleep(10) # delay needed for 1 wire to init
from glob import glob
time.sleep(1.5)
devicedir = glob("/sys/bus/w1/devices/28-*")
device = devicedir[0]+"/w1_slave"
w1 = device  # system level interface for digital temperature sensor DS18d20
device2 = devicedir[1]+"/w1_slave"
w2 = device2  # system level interface for digital temperature sensor DS18d20
device3 = devicedir[2]+"/w1_slave"
w3 = device3  # system level interface for digital temperature sensor DS18d20
time.sleep(.8)
GPIO.setup("P8_13", GPIO.OUT)  # 1 Connected to heater p8_13
GPIO.output("P8_13", GPIO.HIGH)
GPIO.setup("P8_8", GPIO.OUT)  # relay 4 connected to light p8_8
GPIO.output("P8_8", GPIO.HIGH)
GPIO.setup("P8_9", GPIO.OUT)  # relay 3 p8_9
GPIO.output("P8_9", GPIO.HIGH)
GPIO.setup("P8_10", GPIO.OUT)  # relay 2 Connected to pump 2_4
GPIO.output("P8_10", GPIO.HIGH)

#Tornado Folder Paths
# on beaglebone
   #/home/pyfiles/  (gpioserver.py)    this is "root folder"
   # /home/pyfiles/static/        css lives here
   # /home/pyfiles/templates/    html lives here
settings = dict(
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    static_path=os.path.join(os.path.dirname(__file__), "static"))
#Tonado server port
PORT = 8888   # set this to your desired port


class MainHandler(tornado.web.RequestHandler):
    def get(self):   # this loads web page when user connects
        print "[HTTP](MainHandler) User Connected."
        self.render("index.html")


class WSHandler(tornado.websocket.WebSocketHandler):
    connections = set()
    global mode

    def open(self):  # on connection will start 1 second callback
        print '[WS] Connection was opened.'
        self.callback = PeriodicCallback(self.send_data, 1000)
        self.callback.start()
        self.write_message(str(mode) + "m", binary=False)  # send current mode from server to client

    def on_message(self, message):   # receive message from client to server
        global mode
        global set_water
        #print '[WS] Incoming message:', message
        if message == "filter_on":
            mode = 1
        if message == "filter_off":
            mode = 0
        if message == "light_off":
            GPIO.output("P8_8", GPIO.HIGH)
        if message == "light_on":
            GPIO.output("P8_8", GPIO.LOW)
        if message == "hottub_on":
            mode = 2
        if message == "hottub_off":
            mode = 4
        if message == "green_on":
            mode = 3
        if message == "green_off":
            mode = 5
        if (message[:2]) == "WT":  # this includes first 2 chars WT is water temperature setting
            set_water = message[2:]  # this strips first 2 chars
            #print set_water

    def send_data(self):  # send data to client  every 1 second
        global mode
        global cd_time
        global set_water
        self.write_message(tempo+"o", binary=False)
        self.write_message(tempg+"g", binary=False)
        self.write_message(tempw+"w", binary=False)
        self.write_message(str(mode)+"m", binary=False)
        self.write_message(str(set_water)+"s", binary=False)
        if mode == 1:
            self.write_message(str(cd_time) + "c", binary=False)
        if mode == 2:
            self.write_message(str(time_till) + "t", binary=False)
        if GPIO.input("P8_8") == 0:
            self.write_message("l", binary=False)

    def on_close(self):

        print '[WS] Connection was closed.'
        self.callback.stop()


def heating():  # Hot tub heating
    global mode
    global set_water
    while True:

        time.sleep(2)
        if mode == 2:

            time.sleep(1.5)
            GPIO.output("P8_10", GPIO.LOW)  # turn on pump
            setting = set_water

            if float(setting)-float(tempw) > 0.0:
                GPIO.output("P8_13", GPIO.LOW)  # turn on heater
            else:
                GPIO.output("P8_13", GPIO.HIGH)  # turn off heater
                time.sleep(2)
                #  put text to angie here
        elif mode == 4:
            GPIO.output("P8_13", GPIO.HIGH)  # turn off heater
            time.sleep(15.0)
            GPIO.output("P8_10", GPIO.LOW)  # turn off pump
            mode = 0


def heatingg():   # Greenhouse Heating
    global mode
    global tempg
    while True:
        time.sleep(1)
        if mode == 3 and float(tempg) < 44.0:
            while float(tempw) < 108.0:
                GPIO.output("P8_10", GPIO.LOW)  # turn on pump
                GPIO.output("P8_13", GPIO.LOW)  # turn on heater
                if mode == 5:
                    GPIO.output("P8_13", GPIO.HIGH)  # turn off heater
                    time.sleep(15.0)
                    GPIO.output("P8_10", GPIO.HIGH)  # turn off pump
                    break

            else:
                GPIO.output("P8_13", GPIO.HIGH)  # turn off heater
                time.sleep(30.0)
                GPIO.output("P8_10", GPIO.HIGH)  # turn off pump
                time.sleep(2)

        elif mode == 5:
            mode = 0
            time.sleep(1)


def filterw():
    global mode
    global cd_time
    while True:
        time.sleep(1)
        if mode == 1:  # Running Filter?
            time.sleep(.25)
            start_time = time.time()
            GPIO.output("P8_10", GPIO.LOW)  # turn pump on
            while (time.time()-start_time) < 3600.0 and mode == 1:
                seconds = time.time()-start_time
                m, s = divmod(seconds, 60)
                h, m = divmod(m, 60)
                cd_time = "%d:%02d:%02d" % (h, m, s)
                time.sleep(.5)
            else:
                GPIO.output("P8_10", GPIO.HIGH)  # turn pump off
                mode = 0
                #print "TIMED OUT"
        elif mode == 0:
            GPIO.output("P8_10", GPIO.HIGH)  # turn pump off
        else:
            time.sleep(1)
            pass


def update_temp():  # this is the temperature thread DS18S20 output new value every 1000 ms
    global tempw
    global tempg
    global tempo
    while True:
        raw = open(w1, "r").read()
        crc_check = raw.split("crc=")[1]  # test for good temperature data
        if crc_check.find("YES") >= 0:
            tempv = float(raw.split("t=")[-1])/1000
            tempw = str('{0:.1f}'.format(tempv * 9.0 / 5.0 + 32.0))
            raw = open(w2, "r").read()
        crc_check = raw.split("crc=")[1]  # test for good temperature data
        if crc_check.find("YES") >= 0:
            tempv = float(raw.split("t=")[-1])/1000
            tempg = str('{0:.1f}'.format(tempv * 9.0 / 5.0 + 32.0))
            #print (tempw)
        raw = open(w3, "r").read()
        crc_check = raw.split("crc=")[1]  # test for good temperature data
        if crc_check.find("YES") >= 0:
            tempv = float(raw.split("t=")[-1])/1000
            tempo = str('{0:.1f}'.format(tempv * 9.0 / 5.0 + 32.0))

    else:
        pass

#def timing():  # this is the one day at a time thread for filter
 #   global mode


def timing():
    global time_till
    global mode
    global set_water
    time.sleep(5)
    while True:
        tempwfl = tempw
        time.sleep(10)
        delta_temp = float(tempw) - float(tempwfl)
        if mode == 2 and delta_temp >= 0.0:

            time_seconds = ((float(set_water) - float(tempw)) / delta_temp) * 60
            m, s = divmod(time_seconds, 60)
            h, m = divmod(m, 60)
            time_till = "%d:%02d:%02d" % (h, m, s)
            print time_till
        else:
            time_till = "%d:%02d:%02d" % (0, 0, 0)


# setup threads and run
t1 = threading.Thread(name='ReadTemps', target=update_temp)
t1.setDaemon(True)
t1.start()

t2 = threading.Thread(name='FilterWater', target=filterw)
t2.setDaemon(True)
t2.start()

t3 = threading.Thread(name='HeatGreenhouse', target=heatingg)
t3.setDaemon(True)
t3.start()

t4 = threading.Thread(name='HeatHottub', target=heating)
t4.setDaemon(True)
t4.start()

t5 = threading.Thread(name='TimeToTemp', target=timing)
t5.setDaemon(True)
t5.start()

application = tornado.web.Application([
    (r'/', MainHandler),
    (r'/ws', WSHandler),
], **settings)


if __name__ == "__main__":
    try:
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(PORT)
        main_loop = tornado.ioloop.IOLoop.instance()
        print "Tornado Server started"
        main_loop.start()

    except:
        print "Exception triggered - Tornado Server stopped."
        GPIO.cleanup()

#End of Program