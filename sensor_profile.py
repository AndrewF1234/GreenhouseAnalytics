import smbus
import board
import math
import adafruit_ahtx0
import busio
import adafruit_tsl2561
import time
import datetime
import csv
import boto3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pytz
import os
import socket
from datetime import date, timedelta
from influxdb import InfluxDBClient
from dateutil.relativedelta import relativedelta

try:
    data_list = []
    filename = '7-26-2023.csv'
    i2c = busio.I2C(board.SCL, board.SDA)
    light_sensor = adafruit_tsl2561.TSL2561(i2c, 0x29)
    humidity = adafruit_ahtx0.AHTx0(board. I2C())
    bus = smbus.SMBus(1)
    tmpAddress=0x50 # 12c connection
    beta =  2180# represents maximum digital value should be 4096
    mountain_tz = pytz.timezone('US/Mountain')
    humidity.calibrate()
except Exception as e:
    print(e)
    pass
    
try:
    client=InfluxDBClient(host="172.27.8.101",port="8086")
    client.switch_database('home')
except Exception as e:
    print(e)
    with open(filepath + "logfile", "a") as f:
        writer = csv.writer(f)
        writer.writerow(str(e))
        f.close()
    pass
    
header = ['date', 'Temperature', 'Temperature 2', 'Humidity', 'Light Intensity(Lux)']
filepath = '/home/raspberry/IotEnvironmentProject/readingValues/'
datatype_dic_human = {
    "Temperature": "TemperatureOne (C)",
    "Temperature 2": "TemperatureTwo (C)",
    "Humidity" : "Humidity (%)",
    "Light Intensity(Lux)": "Lux"
}
datatype_dic_computer = {
    "date": str,
    "Temperature": np.float64,
    "Temperature 2": np.float64,
    "Humidity": np.float64,
    "Light Intensity(Lux)": np.float64
}
if (not os.path.exists(filepath + filename)):
    with open(filepath + filename, "w+") as f:
        writer = csv.writer(f)
        writer.writerow(header)

def read_temp():
    data =bus.read_i2c_block_data(tmpAddress, 0, 2) # gets block data
    raw_data = ((data[0] & 0x0f) << 8 | data[1]) & 0xfff # takes block data from device (analog) converts raw data
    voltage = (raw_data / beta)* 3.3 # find voltage and ratio it using beta to max voltage
    thermistor_resistance = (100000* (3.3-voltage))/voltage # resistance found using voltage divider equation
    # temperature found based on steinhart-hard equation.
    temperature = (1/(1/298.15+ ((1/beta) * math.log(thermistor_resistance/100000)))) - 273.15
    return temperature

def read_AHT20():
    return humidity.temperature;

def read_humidity():
    if (humidity.relative_humidity> 0 and humidity.relative_humidity < 100):
        return humidity.relative_humidity
    else:
        return 0.0

def read_light():
    light_sensor = adafruit_tsl2561.TSL2561(i2c, 0x29)
    return light_sensor.lux;

def read_time():
    return datetime.datetime.today()

def binary_search(list, key):
    low = 0;
    high = len(list)
    while (high >= low):
        mid = math.ceil((low + high)/2)
        if (key < list[mid]):
            high = mid - 1
        elif (((mid - 1 != -1)and(list[mid -1] < key and key < list[mid])) or ((mid + 1 < len(list))and(list[mid + 1] > key and key > list[mid]))):
            return mid
        else:
            low = mid + 1
    return 0

def create_svg_graph(filesvg_name, minutes_graph, *datatypes):
    df = pd.read_csv(filepath + filename, dtype=datatype_dic_computer)
    
    
    #samples = min(len(df.index)-1,num_samples_to_graph)
    plt.figure()
    df['date'] = pd.to_datetime(df['date'], format="mixed")
    recorded_time = datetime.datetime.today() - timedelta(minutes=minutes_graph)
    human_list = []
    index = binary_search(df['date'], recorded_time)
    for datatype in datatypes:
        plt.plot(df['date'][index:], df[datatype][index:])
        human_list.append(datatype_dic_human[datatype])
    plt.legend(human_list, loc = "lower right")
    plt.savefig(filepath + filesvg_name)
    plt.close()


last_reading = 0
while True:
    if (last_reading + 5 < time.time()):
        last_reading = time.time()
        try:
            temp = read_temp()
        except Exception as e:
            temp = None
        try:
            aht20 = read_AHT20()
        except Exception as e:
            aht20 = None
        try:
            humid = read_humidity()
        except Exception as e:
            humid = None
        try:
            light = read_light()
            if (light == None):
                light = 0.0;
        except Exception as e:
            light = None;
            with open(filepath + "logfile", "a") as f:
                writer = csv.writer(f)
                writer.writerow(str(e))
                f.close()
            pass

        print(f"Time: {read_time()}")
        print(f"Temp_1.1: {temp}")
        print(f"Temp_AHT20: {aht20}")
        print(f"Humidity: {humid}")
        print(f"Light: {light}")

        with open(filepath + filename, 'a') as f:
            writer = csv.writer(f)
            data = [read_time(), temp, aht20, humid, light]
            writer.writerow(data)
            f.close()    
        data_specific = [
                {
                "measurement": "check",
                "time":datetime.datetime.now(tz=pytz.UTC).astimezone(pytz.timezone('US/Mountain')),
                "fields": {
                    "temperature": temp,
                    "temp 2": aht20,
                    "humid": humid,
                    "light": light
                    }
                }
            ]
        data_list.append(data_specific)
        print(data_specific)
        try:
            sock = socket.create_connection(("172.27.8.101", "8086"), timeout=1)
            print(f"Connected to 172.27.8.101")
            sock.close()  # Close the socket when done
            print("HERE")
            for x in data_list:
                 print(x)
                 client.write_points(x)
            print("END")
            results=client.query('SELECT * FROM data_specific')
            login_points=list(results.get_points())
            print(login_points)
            data_list.clear()
        except socket.error as e:
            error = [read_time(), str(e)]
            with open(filepath + "logfile", "a") as f:
                writer = csv.writer(f)
                writer.writerow(error)
                f.close()
            pass
                
        
            
        
        
        #create_svg_graph("5minute.svg", int(5), "Temperature", "Temperature 2", "Humidity", "Light Intensity(Lux)")
        #day_process = Process(target=create_svg_graph, args=("day.svg", int(1440), "Temperature", "Temperature 2", "Humidity", "Light Intensity(Lux)"))
        #week_process = Process(target=create_svg_graph, args=("week.svg", int(1440 * 7), "Temperature", "Temperature 2", "Humidity", "Light Intensity(Lux)"))
        #month_process = Process(target=create_svg_graph, args=("month.svg", int(1440 * 7 * 4), "Temperature", "Temperature 2", "Humidity", "Light Intensity(Lux)"))
        #day_process.start()
        #week_process.start()
        #month_process.start()
        #day_process.join()
        #week_process.join()
        #month_process.join()
            #create_svg_graph("week.svg", int((1440*7 * 60)/ 5), "Temperature", "Temperature 2", "Humidity", "Light Intensity(Lux)")
            #create_svg_graph("month.svg", int((1440*7*4 * 60)/ 5), "Temperature", "Temperature 2", "Humidity", "Light Intensity(Lux)")
            #plt.show()
