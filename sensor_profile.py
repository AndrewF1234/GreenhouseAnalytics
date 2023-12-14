# Board Specific Imports
import smbus, board, busio, adafruit_tsl2561, adafruit_ahtx0

# Logic Specific Imports
import math, time, datetime, csv, pytz, os, socket
from datetime import date, timedelta
from influxdb import InfluxDBClient

# Init and Declare changing variables

DATA_LOGGED = '7-26-2023.csv'
DEPENDENT_PI_IP = "172.27.8.101"
DATA_LOGGED_FILEPATH = '/home/raspberry/IotEnvironmentProject/readingValues/'
ERROR_LOG_FILE = "logfile"
DATABASE_NAME = "home"

cached_data_list = []
tmpAddress = 0x50 # 12c connection
beta =  2180 # represents maximum digital value should be 4096 for thermistor equation
header = ['date', 'Temperature', 'Temperature 2', 'Humidity', 'Light Intensity(Lux)']

# Function for logging errors
def log_error(error, type):
    with open(DATA_LOGGED_FILEPATH + ERROR_LOG_FILE, type) as f:
        writer = csv.writer(f)
        writer.writerow(str(e))
        f.close()
def log_error(error):
    with open(DATA_LOGGED_FILEPATH + ERROR_LOG_FILE, "a") as f:
        writer = csv.writer(f)
        writer.writerow(str(error))
        f.close()

# Checking if the log file exists. If not makes it then adds a header
if (not os.path.exists(DATA_LOGGED_FILEPATH + DATA_LOGGED)):
    with open(DATA_LOGGED_FILEPATH + DATA_LOGGED, "w+") as f:
        writer = csv.writer(f)
        writer.writerow(header)

try:
    # i2c 
    bus = smbus.SMBus(1)
    i2c = busio.I2C(board.SCL, board.SDA)
    # init and declare sensor variables
    mountain_tz = pytz.timezone('US/Mountain')
    light_sensor = adafruit_tsl2561.TSL2561(i2c, 0x29)
    humidity_sensor = adafruit_ahtx0.AHTx0(board. I2C())
    humidity_sensor.calibrate()
except Exception as e:
    log_error(e)
    pass
    
# Init the  influx client and database
try:
    client=InfluxDBClient(host=DEPENDENT_PI_IP,port="8086")
    client.switch_database(DATABASE_NAME)
except Exception as e:
    log_error(e)
    pass
    
def read_temp():
    data =bus.read_i2c_block_data(tmpAddress, 0, 2) # gets block data
    raw_data = ((data[0] & 0x0f) << 8 | data[1]) & 0xfff # takes block data from device (analog) converts raw data
    voltage = (raw_data / beta)* 3.3 # find voltage and ratio it using beta to max voltage
    thermistor_resistance = (100000* (3.3-voltage))/voltage # resistance found using voltage divider equation
    # temperature found based on steinhart-hard equation.
    temperature = (1/(1/298.15+ ((1/beta) * math.log(thermistor_resistance/100000)))) - 273.15
    return temperature

def read_AHT20():
    return humidity_sensor.temperature;

def read_humidity():
    if (humidity_sensor.relative_humidity> 0 and humidity_sensor.relative_humidity < 100):
        return humidity_sensor.relative_humidity
    else:
        return 0.0

def read_light():
    light_sensor = adafruit_tsl2561.TSL2561(i2c, 0x29)
    return light_sensor.lux;

def read_time():
    return datetime.datetime.today()

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
                light = 0.0
        except Exception as e:
            light = None
            log_file(e)
            pass

        with open(DATA_LOGGED_FILEPATH + DATA_LOGGED, 'a') as f:
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
        
        # Append data
        cached_data_list.append(data_specific)
        
        # Tries connection. If connection fails goes to except function to cache data, 
        # connection succeeds then it will send all of cached_data_list to database
        try:
            sock = socket.create_connection((DEPENDENT_PI_IP, "8086"), timeout=1) # try connection
            print(f"Connected to {DEPENDENT_PI_IP}")
            sock.close()  # Close connection

            for x in cached_data_list: # Writes data to client in cached list
                 client.write_points(x)
            
            results=client.query('SELECT * FROM data_specific')
            login_points=list(results.get_points())
            cached_data_list.clear() # Clears when done
        except socket.error as e:
            error = [read_time(), str(e)] # Stores error
            log_file(error)
            pass
