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
switch_count = 0

def GPIO_handler(ctx, data):
    time = data.contents.epoch
    values = parse_value(data, n_elem = 2) #mV
    GPIO_output.append("%i, %i" %(time, values))

def switch_handler(ctx, data):
    time = data.contents.epoch
    value = parse_value(data, n_elem = 2) #no units
    switch_output.append("%i, %i" %(time, value))

GPIO_callback = cbindings.FnVoid_VoidP_DataP(GPIO_handler)
switch_callback = cbindings.FnVoid_VoidP_DataP(switch_handler)

#Connecting the MetaWear Device
address = "C5:41:50:B9:17:6F" #Device 2: 'CF:77:B8:03:8A:B4'   
print("Connecting to %s..." % (address))
d = MetaWear(address)
d.connect()
print("Connected")

print("Setting up Device")
libmetawear.mbl_mw_settings_set_connection_parameters(d.board, 7.5, 7.5, 0, 6000)

Long = LedPattern(pulse_duration_ms=1000, high_time_ms=500, high_intensity=16, low_intensity=16, repeat_count=Const.LED_REPEAT_INDEFINITELY)
sleep(1.0)

# Collecting GPIO and Switch Data
switch = libmetawear.mbl_mw_switch_get_state_data_signal(d.board)
GPIO = libmetawear.mbl_mw_gpio_get_analog_input_data_signal(d.board, 1, 0)

GPIO_logger = create_voidp(lambda fn: libmetawear.mbl_mw_datasignal_log(GPIO, None, fn), resource = "logger")
libmetawear.mbl_mw_datasignal_subscribe(switch, None, switch_callback)

timer = create_voidp(lambda fn: libmetawear.mbl_mw_timer_create_indefinite(d.board, 1000, 0, None, fn), resource = "timer", event = e) #sampling (ms)
libmetawear.mbl_mw_event_record_commands(timer)
libmetawear.mbl_mw_datasignal_read(GPIO)
libmetawear.mbl_mw_datasignal_read(switch)
create_voidp_int(lambda fn: libmetawear.mbl_mw_event_end_record(timer, None, fn), event = e)

# Logging Sensor Data
try:
    libmetawear.mbl_mw_led_write_pattern(d.board, byref(Long), LedColor.GREEN)
    libmetawear.mbl_mw_led_play(d.board)
    sleep(1.0)
    libmetawear.mbl_mw_led_stop_and_clear(d.board)

    print("Start Logging")
    libmetawear.mbl_mw_gpio_start_pin_monitoring(d.board, 1)
    libmetawear.mbl_mw_logging_start(d.board, 0)
    libmetawear.mbl_mw_timer_start(timer)
    
    flag = True
    # Indefinite Logging
    while flag == True:
        libmetawear.mbl_mw_logger_get_signal(GPIO)       
        libmetawear.mbl_mw_datasignal_read(switch)
        if (len(switch_output) > 0):
            if ((int(switch_output[len(switch_output)-1].split(', ')[1]) - int(switch_output[len(switch_output)- 2].split(', ')[1])) == 0):
                flag = True
            elif ((int(switch_output[len(switch_output)-1].split(', ')[0]) - int(switch_output[len(switch_output)- 2].split(', ')[0])) > 5000):
                flag = False
        sleep(1.0)

    #Stop Pin Monitoring 
    print("Stop Logging")
    libmetawear.mbl_mw_logging_stop(d.board)
    libmetawear.mbl_mw_gpio_stop_pin_monitoring (d.board, 1)
    libmetawear.mbl_mw_timer_remove(timer)

except RuntimeError as err:
    print(err)

finally:
    d.on_disconnect = lambda status: e.set()

    e.wait()
