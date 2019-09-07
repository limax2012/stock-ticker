# sevseg_menu.py 2019/07/28 Max Li

# The display driver code was found at:
# https://www.raspberrypi.org/forums/viewtopic.php?t=117564

import time
import pigpio
import json
import urllib.request
import smbus
import math
import string

APIKEY = "U4YRXMMO8JSBDFTY" # AlphaVantage

pi = pigpio.pi()

# Display setup --------------------------------------------------------

REFRESH=1000 # microseconds

CHARSET={
' ': 0b00000000,
'0': 0b11111100,
'1': 0b01100000,
'2': 0b11011010,
'3': 0b11110010,
'4': 0b01100110,
'5': 0b10110110,
'6': 0b10111110,
'7': 0b11100000,
'8': 0b11111110,
'9': 0b11110110,
'A': 0b11101110,
'B': 0b00111110,
'C': 0b10011100,
'D': 0b01111010,
'E': 0b10011110,
'F': 0b10001110,
'G': 0b10111100,
'H': 0b01101110,
'I': 0b01100000,
'J': 0b01111000,
'K': 0b10101110,
'L': 0b00011100,
'M': 0b10101000,
'N': 0b11101100,
'O': 0b00111010,
'P': 0b11001110,
'Q': 0b11100110,
'R': 0b00001010,
'S': 0b10110110,
'T': 0b00011110,
'U': 0b01111100,
'V': 0b00111000,
'W': 0b01010100,
'X': 0b00101000,
'Y': 0b01110110,
'Z': 0b11011010
}

# This defines which gpios are connected to which segments
#           a   b   c   d   e   f   g  dp
SEG2GPIO=[  6, 10, 26, 20, 12,  5, 19, 21]

# This defines the gpio used to switch on a LCD
#           1   2   3   4   5
LCD2GPIO=[ 13, 11,  9, 18]

wid = None

showing = [0]*len(LCD2GPIO)

CHARS=len(CHARSET)

def translate_to_segments(lcd, char, isDecimal):
	char = char.capitalize()
	if char in CHARSET:
		showing[lcd] = CHARSET[char]
		if isDecimal:
			showing[lcd] = showing[lcd] + 0b1
	else:
		showing[lcd] = 0

def update_display():
    global wid
    wf = []
    for lcd in range(len(LCD2GPIO)):

        segments = showing[lcd] # segments on for current LCD

        on = 0 # gpios to switch on
        off = 0 # gpios to switch off

        # set this LCD on, others off (Switched them because common cathode)
        for L in range(len(LCD2GPIO)):
            if L == lcd:
                off |= 1<<LCD2GPIO[L] # switch LCD off
            else:
                on |= 1<<LCD2GPIO[L] # switch LCD on

        # set used segments on, unused segments off
        for b in range(8):
            if segments & 1<<(7-b):
                on |= 1<<SEG2GPIO[b] # switch segment on
            else:
                off |= 1<<SEG2GPIO[b] # switch segment off

        wf.append(pigpio.pulse(on, off, REFRESH))

        #print(on, off, REFRESH) # debugging only

    pi.wave_add_generic(wf) # add pulses to waveform
    new_wid = pi.wave_create() # commit waveform
    pi.wave_send_repeat(new_wid) # transmit waveform repeatedly

    if wid is not None:
        pi.wave_delete(wid) # delete no longer used waveform

    #print("wid", wid, "new_wid", new_wid)

    wid = new_wid

# Display a number or word
def displayOnScreen(thing):

    # Round prices to fourth digit
    if isinstance(thing, float):

        if len(str(thing)) > 5:
            decimalPos = str(thing).find('.')
            thing = round(thing, 4 - decimalPos)

        thing = str(thing)

        # Add trailing zeroes
        while len(thing) < 5:
            thing = thing + '0'

    else:

        thing = str(thing)
        numDecimals = thing.count('.')

        if len(thing) - numDecimals < 4:
            thing = " " * (4 - len(thing) + numDecimals) + thing

    thing = list(thing)

    for i in range(0, 4):

        # Account for decimal point
        isDecimal = False
        if i < len(thing)-1 and thing[i+1] == '.':
            isDecimal = True
            thing.pop(i+1)

        translate_to_segments(i, thing[i], isDecimal)

    update_display()

# Get the price of stock using AlphaVantage API and displays it
def display_stock_price(stock):

    global stockNum

    try:

        # AlphaVantage API call and parse
        url = "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=" + stock + "&interval=1min&apikey=" + APIKEY

        print("Opening url", end=", ", flush=True)

        data = urllib.request.urlopen(url, timeout=5)

        print("Reading from url", end=", ", flush=True)

        data = json.loads(data.read().decode('utf-8'))

        if list(data.keys())[0] == "Note":
            print("Exceeded 5 API calls per minute")
            return

        print("Parsing data", end=", ", flush=True)

        if list(data.keys())[0] == "Error Message":
            print("Invalid stock")
            deleteCurrentStock()
            display("NULL")
            time.sleep(0.5)
            screenNum = 1
            display("LIST")
            return

        else:
            recent_refresh = data["Meta Data"]["3. Last Refreshed"]
            price = float(data["Time Series (1min)"][recent_refresh]["4. close"])
            print(stock, price)
            display(price)

    except:
        print("FAIL")
        display("FAIL")
        display_stock_price(stock)

# Set all used gpios as outputs.

for segment in SEG2GPIO:
    pi.set_mode(segment, pigpio.OUTPUT)

for lcd in LCD2GPIO:
    pi.set_mode(lcd, pigpio.OUTPUT)

# Fuel Guage I2C setup -------------------------------------------------

channel = 1
fuel_guage_address = 0x36
soc_register = 0x04

bus = smbus.SMBus(channel)

# Button setup ---------------------------------------------------------

# GPIO pins for the buttons
BACK = 4
UP = 17
DOWN = 14
SELECT = 15

pi.set_mode(BACK, pigpio.INPUT)
pi.set_mode(UP, pigpio.INPUT)
pi.set_mode(DOWN, pigpio.INPUT)
pi.set_mode(SELECT, pigpio.INPUT)

pi.set_pull_up_down(BACK, pigpio.PUD_DOWN)
pi.set_pull_up_down(UP, pigpio.PUD_DOWN)
pi.set_pull_up_down(DOWN, pigpio.PUD_DOWN)
pi.set_pull_up_down(SELECT, pigpio.PUD_DOWN)

lastInterruptTime = 0

mainMenu = ["LIST", "EDIT", "BATT"]
editMenu = ["ADD", "DEL"]
screenNum = 1

stocks = []
stockNum = 0
displayPrice = False
lastRequestTime = 0

# "Add" screen variables
alphabet = string.ascii_uppercase + ' '
currentDigit = 0
stockInput = ['A','A','A','A']

REFRESH_INTERVAL = 15
TIME_STEP = 0.25

def buttonPress(gpio, level, tick):

    global lastInterruptTime
    global screenNum
    global stockNum
    global displayPrice
    global lastRequestTime
    global alphabet
    global currentDigit
    global stockInput

    if time.time() - lastInterruptTime > 0.25: # Debounce button

        lastInterruptTime = time.time()

        if screenNum == 11 or screenNum == 221: # stock select screen

            if gpio == BACK:
                if displayPrice:
                    displayPrice = False
                else:
                    screenNum = math.floor(screenNum/10)
            elif gpio == UP:
                if stockNum > 0:
                    stockNum = stockNum - 1
            elif gpio == DOWN:
                if stockNum < len(stocks) - 1:
                    stockNum = stockNum + 1
            elif gpio == SELECT:
                if screenNum == 11:
                    displayPrice = True
                    lastRequestTime = timer % REFRESH_INTERVAL
                else:
                    deleteCurrentStock()
                    screenNum = 2
                    blinkDots(2)

        elif screenNum == 211:

            if gpio == BACK:
                if currentDigit == 0:
                    screenNum = 21
                else:
                    currentDigit = currentDigit - 1
            if gpio == UP:
                letterIndex = alphabet.find(stockInput[currentDigit])
                stockInput[currentDigit] = alphabet[(letterIndex - 1) % 27]
            if gpio == DOWN:
                letterIndex = alphabet.find(stockInput[currentDigit])
                stockInput[currentDigit] = alphabet[(letterIndex + 1) % 27]
            if gpio == SELECT:
                if currentDigit < 3:
                    currentDigit = currentDigit + 1
                else:
                    stockInput = [letter for letter in stockInput if letter != ' ']
                    print("successfully added " + ''.join(stockInput))
                    newStock = ''.join(stockInput)
                    stocks.append(newStock)
                    stockFile = open("stocks.txt", 'a')
                    stockFile.write(newStock + '\n')
                    stockFile.close()
                    stockInput = ['A','A','A','A']
                    currentDigit = 0
                    screenNum = 2
                    blinkDots(2)

        else:

            onesDigit = screenNum % 10

            if gpio == BACK:
                if screenNum > 10:
                    screenNum = math.floor(screenNum / 10)
            elif gpio == UP:
                if onesDigit > 1:
                    screenNum = screenNum - 1
            elif gpio == DOWN:
                if (screenNum < 10 and onesDigit < 3) or (screenNum > 20 and onesDigit < 2):
                    screenNum = screenNum + 1
            elif gpio == SELECT:
                if screenNum < 30:
                    screenNum = screenNum * 10 + 1
            else:
                print("Invalid button press")
                return

        print(screenNum)
        screenUpdate()


backButton = pi.callback(BACK, pigpio.RISING_EDGE, buttonPress)
upButton = pi.callback(UP, pigpio.RISING_EDGE, buttonPress)
downButton = pi.callback(DOWN, pigpio.RISING_EDGE, buttonPress)
selectButton = pi.callback(SELECT, pigpio.RISING_EDGE, buttonPress)

def screenUpdate():

    global screenNum
    global currentDigit
    global stockInput

    if screenNum < 10: # single-digits - main menu
        display(mainMenu[screenNum - 1])
    elif screenNum == 11 or screenNum == 221: # 11 or 221 - stock select
        if len(stocks) != 0:
            display(stocks[stockNum])
        else:
            display("NONE")
            time.sleep(0.75)
            screenNum = math.floor(screenNum / 10)
            screenUpdate()
    elif screenNum < 30: # 20s - Add/Del
        display(editMenu[screenNum % 10 - 1])
    elif screenNum == 31: # 31 - battery %
        display(bus.read_byte_data(fuel_guage_address, soc_register))
    elif screenNum == 211:
        display(''.join(stockInput[: (currentDigit + 1)]) + '.' + ''.join(stockInput[(currentDigit + 1) :]))

def deleteCurrentStock():
    global stocks
    global stockNum
    stocks.pop(stockNum)
    stockFile = open("stocks.txt", 'w')
    for stock in stocks:
        stockFile.write("%s\n" % stock)
    stockNum = 0

def blinkDots(iterations):
    for i in range(0, iterations):
        display(" .   ")
        time.sleep(0.05)
        display("  .  ")
        time.sleep(0.05)
        display("   . ")
        time.sleep(0.05)
        display("    .")
        time.sleep(0.05)

# Main program ---------------------------------------------------------

stockFile = open("stocks.txt", 'r')
stocks = stockFile.read().splitlines()
stockFile.close()

print(stocks)

blinkDots(4)

screenUpdate()

timer = 0

try:
    while(True):
        if displayPrice and timer % REFRESH_INTERVAL == lastRequestTime:
            display_stock_price(stocks[stockNum])
        timer += TIME_STEP
        time.sleep(TIME_STEP)

except KeyboardInterrupt:
    display("    ")

# Clean up -------------------------------------------------------------

pi.wave_delete(wid)

pi.stop()
