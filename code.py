# Circuitpython code to run a PMSA003I Air Quality
# monitor and display results to an ILI9341 display.
# Screen Timeout is controlled by a VL53L1X ToF distance sensor.

import time
import board
import busio
from digitalio import DigitalInOut, Direction, Pull
from adafruit_pm25.i2c import PM25_I2C
import terminalio
from adafruit_display_text import label
import displayio
import adafruit_ili9341
import adafruit_imageload
import asyncio
import pwmio
from analogio import AnalogOut
import random

import adafruit_vl53l1x
import supervisor
import microcontroller
import ssl
import socketpool
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from secrets import secrets

i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)

vl53 = adafruit_vl53l1x.VL53L1X(i2c)
vl53.distance_mode = 2
vl53.timing_budget = 200
vl53.start_ranging()

spi_bus = board.SPI()
tft_cs = board.D5
tft_reset = board.D6
tft_led = board.D10
tft_dc = board.D9

displayio.release_displays()
display_bus = displayio.FourWire(
    spi_bus, command=tft_dc, chip_select=tft_cs, reset=tft_reset
)

# initialize display. Note that auto_refresh is set to False!
display = adafruit_ili9341.ILI9341(
    display_bus, width=240, height=320, rotation=270, auto_refresh=False
)

splash = displayio.Group()
display.show(splash)

font = terminalio.FONT
text_color = 0xFFFFFF

disp_text_1 = "PM2.5:"
disp_label_1 = label.Label(font, text=disp_text_1, color=text_color, scale=2)
disp_label_1.x = 84
disp_label_1.y = 20

disp_text_2 = ""
disp_label_2 = label.Label(font, text=disp_text_2, color=text_color, scale=4)
disp_label_2.x = 80
disp_label_2.y = 50


disp_text_3 = "ug/\nm^3"
disp_label_3 = label.Label(
    font, text=disp_text_3, color=text_color, scale=1, line_spacing=0.9
)
disp_label_3.x = 153
disp_label_3.y = 50

disp_text_4 = ""
disp_label_4 = label.Label(
    font, text=disp_text_4, color=text_color, scale=1, line_spacing=0.9
)
disp_label_4.x = 45
disp_label_4.y = 230

disp_text_5 = ""
disp_label_5 = label.Label(
    font, text=disp_text_5, color=text_color, scale=1, line_spacing=0.9
)
disp_label_5.x = 90
disp_label_5.y = 245

# COULD NOT FIGURE OUT HOW TO GET BACKLIGHT ON/OFF WORKING WITHOUT MESSING UP DISPLAY!
# backlight_led = pwmio.PWMOut(board.A5, frequency = 5000, duty_cycle = 0)
# backlight_led.duty_cycle = 65535

backlight_led = DigitalInOut(board.A5)
backlight_led.switch_to_output()
backlight_led.value = True


face_sprites_bitmap, face_sprites_palette = adafruit_imageload.load(
    "/face_sprites.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette
)

face_sprites = displayio.TileGrid(
    face_sprites_bitmap,
    pixel_shader=face_sprites_palette,
    width=1,
    height=1,
    tile_width=16,
    tile_height=16,
)
face_sprites_group = displayio.Group(scale=15)
face_sprites_group.append(face_sprites)
face_sprites_group.x = 0
face_sprites_group.y = 25

splash.append(face_sprites_group)
splash.append(disp_label_1)
splash.append(disp_label_2)
splash.append(disp_label_3)
splash.append(disp_label_4)
splash.append(disp_label_5)
pm25_reset_pin = None

# Create library object, use 'slow' 100KHz frequency!
# Connect to a PM2.5 sensor over I2C
pm25 = PM25_I2C(i2c, pm25_reset_pin)


try:
    wifi.radio.connect(secrets["ssid"], secrets["password"])
except:
    print("hard resetting in 15 seconds...")
    time.sleep(15)
    microcontroller.reset()

def connected(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    #print("Connected to Adafruit IO! Listening for topic changes on %s" % onoff_feed)
    # Subscribe to all changes on the onoff_feed.
    #client.subscribe(onoff_feed)
    print("placeholder1")


def disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    print("Disconnected from Adafruit IO!")


def message(client, topic, message):
    # This method is called when a topic the client is subscribed to
    # has a new message.
    #print("New message on topic {0}: {1}".format(topic, message))
    print("placeholder2")


# Create a socket pool
pool = socketpool.SocketPool(wifi.radio)

# Set up a MiniMQTT Client
mqtt_client = MQTT.MQTT(
    broker=secrets["broker"],
    port=secrets["port"],
    username=secrets["aio_username"],
    password=secrets["aio_key"],
    socket_pool=pool,
    ssl_context=ssl.create_default_context(),
)

# Setup the callback methods above
mqtt_client.on_connect = connected
mqtt_client.on_disconnect = disconnected
mqtt_client.on_message = message

# Connect the client to the MQTT broker.
print("Connecting to Adafruit IO...")
mqtt_client.connect()

pm25_feed = secrets["aio_username"] + secrets["feed"]

class Sensorvals:
    def __init__(self):
        # air quality
        self.p03 = None  # 0.3 micron particles
        self.p05 = None  # 0.5 micron particles
        self.p10 = None  # 1.0 micron particles
        self.p25 = None  # 2.5 micron particles
        self.p50 = None  # 5.0 micron particles
        self.p100 = None  # 10 micron particles
        self.pm10 = None  # PM 1.0 value
        self.pm25 = None  # PM 2.5 value
        self.pm100 = None  # PM 10 value

        self.vl53_cm_prev = 0
        self.vl53_cm = 0
        self.timeout = False


sensorvals = Sensorvals()

# Coroutine to read distance from VL53L1X sensor.
async def vl53_read(sensorvals):
    while True:
        try:
            if vl53.data_ready:
                #print("Distance: {} cm".format(vl53.distance))
                sensorvals.vl53_cm = vl53.distance
                vl53.clear_interrupt()
        except:
            print("ranging fail.")
        await asyncio.sleep(0.2)

#Coroutine to handle Screen Timeout.
async def screen_timeout(sensorvals):
    start_time = time.monotonic()
    timeout_time = 30
    while True:
        try:
            distance = sensorvals.vl53_cm
            prev_distance = sensorvals.vl53_cm_prev
            if distance != None and prev_distance != None:
                if distance - prev_distance < -3:
                    print("Activate!")
                    start_time = time.monotonic()
                    sensorvals.timeout = False
                sensorvals.vl53_cm_prev = distance
            if time.monotonic() - start_time > timeout_time:
                print("TIMEOUT!")
                start_time = time.monotonic()
                sensorvals.timeout = True
        except:
            print("screen timeout fail.")
        await asyncio.sleep(0.2)

#Coroutine to read Air Quality data and display on screen.
async def pm25_read(sensorvals):
    while True:
        try:
            aqdata = pm25.read()
            sensorvals.p03 = aqdata["particles 03um"]
            sensorvals.p05 = aqdata["particles 05um"]
            sensorvals.p10 = aqdata["particles 10um"]
            sensorvals.p25 = aqdata["particles 25um"]
            sensorvals.p50 = aqdata["particles 50um"]
            sensorvals.p100 = aqdata["particles 100um"]
            sensorvals.pm10 = aqdata["pm10 standard"]
            sensorvals.pm25 = aqdata["pm25 standard"]
            sensorvals.pm100 = aqdata["pm100 standard"]

            disp_label_2.text = "{:03d}".format(sensorvals.pm25)
            disp_label_4.text = "Particle Counts per 0.1L:"
            disp_label_5.text = (
                "0.3um: "
                + str(sensorvals.p03)
                + "\n0.5um: "
                + str(sensorvals.p05)
                + "\n1.0um: "
                + str(sensorvals.p10)
                + "\n2.5um: "
                + str(sensorvals.p25)
                + "\n5.0um: "
                + str(sensorvals.p50)
                + "\n10 um: "
                + str(sensorvals.p100)
            )
            display.refresh()
        except RuntimeError:
            print("Unable to read from sensor, retrying...")
        await asyncio.sleep(1.0)

#Coroutine to display animated face, and set PM2.5 ranges for "mood".
async def face_display(sensorvals):
    while True:
        sleeptime = random.random() * 3.0
        try:
            if sensorvals.timeout == False:
                splash.hidden = False
                if sensorvals.pm25 >= 0 and sensorvals.pm25 < 3:
                    choice = random.randint(0, 3)
                    face_sprites[0] = choice
                    if choice == 3:
                        sleeptime = 0
                elif sensorvals.pm25 >= 3 and sensorvals.pm25 < 7:
                    choice = random.randint(4, 7)
                    face_sprites[0] = choice
                    if choice == 7:
                        sleeptime = 0
                elif sensorvals.pm25 >= 7 and sensorvals.pm25 < 13:
                    choice = random.randint(8, 11)
                    face_sprites[0] = choice
                    if choice == 1:
                        sleeptime = 0
                elif sensorvals.pm25 >= 13 and sensorvals.pm25 < 51:
                    choice = random.randint(12, 15)
                    face_sprites[0] = choice
                    if choice == 15:
                        sleeptime = 0
                elif sensorvals.pm25 >= 51:
                    choice = random.randint(16, 19)
                    face_sprites[0] = choice
                    if choice == 19:
                        sleeptime = 0
                display.refresh()
            elif sensorvals.timeout == True:
                splash.hidden = True
                display.refresh()
        except:
            print("face fail")
        await asyncio.sleep(sleeptime)

async def mqtt_send(sensorvals):
    while True:
        try:
            if sensorvals.pm25 is not None:
                mqtt_client.publish(pm25_feed, sensorvals.pm25)
                print("pm25 data published!" + " Value: " + str(sensorvals.pm25))
        except:
            print ("mqtt fail.")
        await asyncio.sleep(30)

async def main():
    vl53_read_task = asyncio.create_task(vl53_read(sensorvals))
    pm25_read_task = asyncio.create_task(pm25_read(sensorvals))
    face_display_task = asyncio.create_task(face_display(sensorvals))
    screen_timeout_task = asyncio.create_task(screen_timeout(sensorvals))
    mqtt_send_task = asyncio.create_task(mqtt_send(sensorvals))

    await asyncio.gather(vl53_read_task)


asyncio.run(main())
