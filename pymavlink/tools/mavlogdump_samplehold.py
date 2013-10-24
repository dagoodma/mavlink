#!/usr/bin/env python

'''
example program that dumps a Mavlink log file. The log file is
assumed to be in the format that qgroundcontrol uses, which consists
of a series of MAVLink packets, each with a 64 bit timestamp
header. The timestamp is in microseconds since 1970 (unix epoch)
'''

import sys, time, os, struct, json
from collections import OrderedDict

# allow import from the parent directory, where mavlink.py is
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from optparse import OptionParser
parser = OptionParser("mavlogdump.py [options] <LOGFILE>")

parser.add_option("--debug",dest="debug",action='store_true',help="Debug messages")
parser.add_option("--no-timestamps",dest="notimestamps", action='store_true', help="Log doesn't have timestamps")
parser.add_option("--planner",dest="planner", action='store_true', help="use planner file format")
parser.add_option("--robust",dest="robust", action='store_true', help="Enable robust parsing (skip over bad data)")
parser.add_option("-f", "--follow",dest="follow", action='store_true', help="keep waiting for more data at end of file")
parser.add_option("--condition",dest="condition", default=None, help="select packets by condition")
parser.add_option("-q", "--quiet", dest="quiet", action='store_true', help="don't display packets")
parser.add_option("-o", "--output", default=None, help="output matching packets to give file")
parser.add_option("--format", dest="format", default=None, help="Change the output format between 'standard', 'json', and 'csv'. For the CSV output, you must supply types that you want.")
parser.add_option("--csv_sep", dest="csv_sep", default=",", help="Select the delimiter between columns for the ouput CSV file. Use 'tab' to specify tabs. Only applies when --format=csv")
parser.add_option("--types",  default=None, help="types of messages (comma separated)")
parser.add_option("--dialect",  default="ardupilotmega", help="MAVLink dialect")
parser.add_option("--no-description",dest="description_section", action='store_false', default=True, help="disables data desciption section")
(opts, args) = parser.parse_args()

import inspect
import pprint
import mavutil
from mavutil import get_dialect_module
#import mavlink

if len(args) < 1:
    print("Usage: mavlogdump.py [options] <LOGFILE>")
    sys.exit(1)

filename = args[0]
mlog = mavutil.mavlink_connection(filename, planner_format=opts.planner,
                                  notimestamps=opts.notimestamps,
                                  robust_parsing=opts.robust,dialect=opts.dialect)

output = None
if opts.output:
    output = mavutil.mavlogfile(opts.output, write=True)

desired_types = opts.types
if desired_types is not None:
    desired_types = desired_types.split(',')

if opts.debug:
    print("Building " + opts.format + " file with types: " + str(desired_types))

opts.csv_sep = opts.csv_sep.replace("tab","\t")

# Write out a header row as we're outputting in CSV format.
fields = []
fields_header = ""
offsets = {}
if opts.format == 'csv':
    try:
        currentOffset = 1 # Store how many fields in we are for each message.
        for type in desired_types:
            try:
                typeClass = "MAVLink_{0}_message".format(type.lower())
                fields += [type + '.' + x for x in inspect.getargspec(getattr(get_dialect_module(), typeClass).__init__).args[1:]]
                offsets[type] = currentOffset
                currentOffset += len(fields)
            except IndexError, e:
                quit()
    except TypeError, e:
        print("You must specify a list of message types if outputting CSV format via the --types argument.")
        exit()

# Build field header and structs for message fields to sample and hold 
window = OrderedDict()
for field in fields:
    if fields_header:
        fields_header += opts.csv_sep + " "

    fields_header += field.replace('.', '_')
    window[field] = 0

fields_header = fields_header.rstrip(opts.csv_sep)

# Show data description section
if opts.description_section:
    print("Description data:")
    i = 1
    for field in fields:
        field = field.replace('.', '_')
        print(field.upper() + " {" + str(i) + "}")
        i += 1

    print("End description data" + os.linesep ) 

# Show column names in csv format)
print(fields_header.upper())

# Initialize timestamp field for alignment
current_timestamp = 0
use_timestamp = False

if opts.debug:
    print("Initialized sample window fields: " + str(window))

while True:
    m = mlog.recv_match(condition=opts.condition, blocking=opts.follow, type=desired_types)
    if m is None:
        break

    if desired_types is not None and m.get_type() not in desired_types and m.get_type() != 'BAD_DATA':
        continue
    last_timestamp = 0
    
    if m.get_type() == 'BAD_DATA' and m.reason == "Bad prefix":
        continue

    # Save fields into window
    data = m.to_dict()
    type = m.get_type()
    
    # Iterate over all fields of data and set the window
    for field,value in data.items():
        key = type + "." + field
        if (key in window):
            window[key] = value

    # If JSON was ordered, serve it up. Split it nicely into metadata and data.
    if opts.format == 'json':
        data = m.to_dict()
        del data['mavpackettype']
        outMsg = {"meta": {"msgId": m.get_msgId(), "type": m.get_type(), "timestamp": m._timestamp}, "data": json.dumps(data)}
        print(outMsg)
    elif opts.format == 'csv':
        if not use_timestamp or current_timestamp != window["ATTITUDE.time_boot_ms"]:
            current_timestamp = window["ATTITUDE.time_boot_ms"]
        
            # Build the line
            out = []
            values = window.values()
            for v in values:
                out.append(str(v))
            
            out = opts.csv_sep.join(out)
            out = out.rstrip(opts.csv_sep)
            if opts.debug:
                print(out + " ----- " + type)
            else:
                print(out)
        
