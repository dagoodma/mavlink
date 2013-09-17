#!/usr/bin/env python

'''
example program that dumps a Mavlink log file. The log file is
assumed to be in the format that qgroundcontrol uses, which consists
of a series of MAVLink packets, each with a 64 bit timestamp
header. The timestamp is in microseconds since 1970 (unix epoch)
'''

import sys, time, os, struct, json

# allow import from the parent directory, where mavlink.py is
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from optparse import OptionParser
parser = OptionParser("mavlogdump.py [options] <LOGFILE>")

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

types = opts.types
if types is not None:
    types = types.split(',')

if opts.csv_sep == "tab":
    opts.csv_sep = "\t"

# Write out a header row as we're outputting in CSV format.
fields = ['timestamp']
offsets = {}
if opts.format == 'csv':
    try:
        currentOffset = 1 # Store how many fields in we are for each message.
        for type in types:
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
print(opts.csv_sep.join(fields))


while True:
    m = mlog.recv_match(condition=opts.condition, blocking=opts.follow)
    if m is None:
        break

    if types is not None and m.get_type() not in types and m.get_type() != 'BAD_DATA':
        continue
    last_timestamp = 0
    
    if m.get_type() == 'BAD_DATA' and m.reason == "Bad prefix":
        continue
    
    if output:
        timestamp = getattr(m, '_timestamp', None)
        if not timestamp:
            timestamp = last_timestamp
        last_timestamp = timestamp
        output.write(struct.pack('>Q', timestamp*1.0e6))
        output.write(m.get_msgbuf())
    if opts.quiet:
        continue

    # If JSON was ordered, serve it up. Split it nicely into metadata and data.
    if opts.format == 'json':
        data = m.to_dict()
        del data['mavpackettype']
        outMsg = {"meta": {"msgId": m.get_msgId(), "type": m.get_type(), "timestamp": m._timestamp}, "data": json.dumps(data)}
        print(outMsg)
    elif opts.format == 'csv':
        data = m.to_dict()
        type = m.get_type()
        out = [str(data[y.split('.')[-1]]) if y.split('.')[0] == type and y.split('.')[-1] in data else "" for y in [type + '.' + x for x in fields]]
        out[0] = str(m._timestamp)
        print(opts.csv_sep.join(out))
    else:
        print("%s.%02u: %s" % (
            time.strftime("%Y-%m-%d %H:%M:%S",
                          time.localtime(m._timestamp)),
                          int(m._timestamp*100.0)%100, m))
        
