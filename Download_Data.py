# Download Data

from __future__ import print_function
from ctypes import c_void_p, cast
from mbientlab.metawear import MetaWear, libmetawear, parse_value, cbindings, create_voidp, create_voidp_int, FnVoid_VoidP_UByte_Long_UByteP_UByte, \
    FnVoid_VoidP_DataP, byref, LogDownloadHandler, FnVoid_VoidP_UInt_UInt
from mbientlab.metawear.cbindings import *
from time import sleep
from threading import Event

import sys
import platform
import six
import csv

e = Event()
GPIO_output = []
switch_output = []
accel_output = []

def switch_handler(ctx, data):
    time = data.contents.epoch
    value = parse_value(data, n_elem = 2) #no units
    switch_output.append("%i, %i" %(time, value))

def GPIO_handler(ctx, data):
    time = data.contents.epoch
    values = parse_value(data, n_elem = 2) #mV
    GPIO_output.append("%i, %i" %(time, values))  

def accel_handler(ctx, data):
    time = data.contents.epoch
    value = parse_value(data, n_elem = 2) #m/s^2
    accel_output.append("%i, %s" %(time, value))

GPIO_callback = cbindings.FnVoid_VoidP_DataP(GPIO_handler)
switch_callback = cbindings.FnVoid_VoidP_DataP(switch_handler)
accel_callback = cbindings.FnVoid_VoidP_DataP(accel_handler)

#Connecting the MetaWear Device, how can we connect to a specific device?
address = 'CF:77:B8:03:8A:B4' #"C5:41:50:B9:17:6F"
print("Connecting to %s..." % (address))
d = MetaWear(address)
d.connect()

Long = LedPattern(pulse_duration_ms=1000, high_time_ms=500, high_intensity=16, low_intensity=16, repeat_count=Const.LED_REPEAT_INDEFINITELY)
libmetawear.mbl_mw_led_write_pattern(d.board, byref(Long), LedColor.GREEN)
libmetawear.mbl_mw_led_play(d.board)
sleep(1.0)
libmetawear.mbl_mw_led_stop_and_clear(d.board)

print("Setting up Device")
libmetawear.mbl_mw_settings_set_connection_parameters(d.board, 7.5, 7.5, 0, 6000)

try:
    # Downloading the Data
    print("Downloading data")
    sleep(1.0)

    de = Event()
    def progress_update_handler(context, entries_left, total_entries):
        if (entries_left == 0):
            de.set()

    fn_wrapper = FnVoid_VoidP_UInt_UInt(progress_update_handler)
    download_handler = LogDownloadHandler(context = None, \
        received_progress_update = fn_wrapper, \
        received_unknown_entry = cast(None, FnVoid_VoidP_UByte_Long_UByteP_UByte), \
        received_unhandled_entry = cast(None, FnVoid_VoidP_DataP))
    
    libmetawear.mbl_mw_logging_download(d.board, 0, byref(download_handler))

    # Creating Xcel File
    file_name = raw_input("Enter File name.csv: ")
    header = ['Epoch', 'GPIO', 'Epoch', 'Switch', 'Epoch', 'Accel(x)', 'Accel(y)', 'Accel(z)']
    with open(file_name, 'wb') as f:
        wr= csv.writer(f, dialect = 'excel')
        wr.writerow(header)
        i = 0
        while i < len(GPIO_output):
            while len(switch_output) < len(GPIO_output):
                switch_output.append('0, 0')
            while len(accel_output) < len(GPIO_output):
                accel_output.append('0, 0, 0, 0')
            GPIO = GPIO_output[i].split(', ')
            Switch = switch_output[i].split(', ')
            Accel = accel_output[i].translate(None, "{}xyz:,").split()
            Combined_data = [GPIO[0], GPIO[1], Switch[0], Switch[1], Accel[0], Accel[1], Accel[2], Accel[3]]
            wr.writerow(Combined_data)
            i +=1
    f.close()
    print("Finished Downloading")

except RuntimeError as err:
    print(err)

finally:
    print("Resetting device")
    d.on_disconnect = lambda status: e.set()
    libmetawear.mbl_mw_debug_reset(d.board)
    e.wait()