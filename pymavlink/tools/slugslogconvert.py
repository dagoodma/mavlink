#!/usr/bin/env python
"""\
slugslogconvert.py is a GUI front-end for mavlogdump.py that is set to convert
mavlink binary log files to csv format for MATLAB.

Notes:
-----
* 2013-9-20 -- dagoodman
    Started tool.

Copyright 2012 David Goodman (dagoodman@soe.ucsc.edu)
Released under GNU GPL version 3 or later

"""
import os, sys, struct
#import re
import pprint
import threading
import Queue
from collections import OrderedDict
from time import sleep
#from subprocess import call

# Tkinter Python 2.x and 3.x compatability
try:
    from tkinter import *
    import tkinter.filedialog
    import tkinter.messagebox
    import tkinter.progressbar

except ImportError as ex:
    # Must be using Python 2.x, import and rename
    from Tkinter import *
    import tkFileDialog
    import tkMessageBox
    import ttk

    tkinter.filedialog = tkFileDialog
    del tkFileDialog
    tkinter.messagebox = tkMessageBox
    del tkMessageBox


# allow import from the parent directory, where mavutil.py is
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import inspect
import pprint
import mavutil
from mavutil import get_dialect_module


DEBUG = True
CHECK_DELAY = 10 # ms
title = "SLUGS Log Converter"

options = {
    "types":  "GPS_RAW_INT,ATTITUDE,LOCAL_POSITION_NED,GPS_DATE_TIME,SLUGS_NAVIGATION,RAW_IMU,SCALED_PRESSURE,CPU_LOAD,HEARTBEAT,SYS_STATUS,RC_CHANNELS_RAW,SERVO_OUTPUT_RAW,SCALED_IMU,RAW_PRESSURE,MID_LVL_CMDS,SENSOR_DIAG,DIAGNOSTIC,DATA_LOG,VOLT_SENSOR,STATUS_GPS,NOVATEL_DIAG,PTZ_STATUS,MISSION_CURRENT,SENSOR_BIAS",
    "dialect": "slugs",
    "format": "csv",
    "align_timestamps": True,
    "align_timestamp_field": "ATTITUDE.time_boot_ms",
    "csv_sep": ",tab",
    "no_timestamps": True,
    "print_description": True,
    "debug": False,
}

terminal_lock = threading.Lock()

#------------------------------ Gui -------------------------------
class Application(Frame):
    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.pack_propagate(0)
        self.grid( sticky=N+S+E+W)
        self.createWidgets()
        self.pp = pprint.PrettyPrinter(indent=4)

        self.menu= Menu(self.master)
        self.master.config(menu=self.menu)
        self.file_menu = Menu(self.menu)
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Quit", command=self.quit)

        self.edit_menu = Menu(self.menu)
        self.options_menu = Menu(self.edit_menu)
        self.menu.add_cascade(label="Edit", menu=self.edit_menu)
        self.edit_menu.add_cascade(label="Options", menu=self.options_menu)

        self.parsing = False
        self.log_parser = None
        self.log_parser_queue = None
        self.log_parser_error = False
        self.progress_counter = 0
        
        self.progress_bar_container = False

        #self = SlugsOptionsMenu(master
        #self.options_menu.add_checkbutton(label="Autoscroll", onvalue=True, offvalue=False, variable=self.autoscroll_value)

    """\
    Creates the gui and all of its content.
    """
    def createWidgets(self):


        #----------------------------------------
        # Create the binary log file entry

        self.binary_log_value = StringVar()
        self.binary_log_label = Label( self, text="Binary log" )
        self.binary_log_label.grid(row=0, column = 0)
        self.binary_log_entry = Entry( self, width = 26, textvariable=self.binary_log_value )
        self.binary_log_entry.grid(row=0, column = 1)
        self.binary_log_button = Button (self, text="Browse", command=self.browseBinaryLogFile)
        self.binary_log_button.grid(row=0, column = 2)

        #----------------------------------------
        # Create the Out entry

        self.out_value = StringVar()
        self.out_label = Label( self, text="Output CSV" )
        self.out_label.grid(row=1,column = 0)
        self.out_entry = Entry( self, width = 26, textvariable=self.out_value )
        self.out_entry.grid(row=1, column = 1)
        self.out_button = Button (self, text="Browse", command=self.browseOutputFile)
        self.out_button.grid(row=1, column = 2)

        #----------------------------------------
        # Create the generate button

        self.convert_button = Button ( self, text="Convert", command=self.convertLog)
        self.convert_button.grid(row=4,column=1)

    """\
    Open a file selection window to choose the binary mavlink log file.
    """
    def browseBinaryLogFile(self):
        binary_log_file = tkinter.filedialog.askopenfilename(parent=self, title='Choose a binary .mavlink log file')
        if DEBUG:
            print("Binary log: " + binary_log_file)
        if binary_log_file != None:
            self.binary_log_value.set(binary_log_file)

    """\
    Open a file selection window to choose an output csv file.
    """
    def browseOutputFile(self):
        mavlinkFolder = os.path.dirname(os.path.realpath(__file__))
        output_file = tkinter.filedialog.asksaveasfilename(parent=self,title='Please choose an output .csv file name')
        if DEBUG:
            print("Output: " + output_file)
        if output_file != None:
            self.out_value.set(output_file)

    """\
    Converts the binary mavlink log file to a plaintext csv file.
    """
    def convertLog(self):
        # Verify settings
        if not self.binary_log_value.get():
            tkinter.messagebox.showerror('Error Converting Log File','A binary .mavlink log file must be specified.')
            return

        if not self.out_value.get():
            tkinter.messagebox.showerror('Error Converting Log File', 'An output .csv file must be specified.')
            return


        if os.path.exists(self.out_value.get()):
            if not tkinter.messagebox.askokcancel('Overwrite output log file?','The output file \'{0}\' already exists. The file will be overwritten.'.format(self.out_value.get())):
                return

        opts = options
        input_file = self.binary_log_value.get()
        output_file = self.out_value.get()

        if DEBUG:
            print("Converting log file")

        result = 0

        try:
            # Create the progress bar
            self.createProgressBar()           

            # Start worker thread to convert log file
            self.log_parser = LogParserThread(self,opts,input_file,output_file)
            self.log_parser.startParsing()
            self.log_parser_queue = self.log_parser.queue

            # Starting updating progress bar
            self.createProgressBar()
            self.checkParser()

        except Exception as ex:
            self.showError(str(ex))
            self.removeProgressBar()
            raise
            return

    """\
    Creates the progress bar.
    """
    def createProgressBar(self):
        if not self.progress_bar_container:
            self.progress_bar_container = Toplevel(self)
            self.progress_bar_container.title("Parsing MAVLINK Log")
            self.progress_bar_label = Label(
                self.progress_bar_container,
                text="Progress",
                bd=1
            )
            self.progress_bar_label.pack(side=TOP)

            self.progress_bar = ttk.Progressbar(
                self.progress_bar_container,
                orient="horizontal",
                length=270,
                mode="determinate",
                variable=self.progress_counter,
            )
            self.progress_bar.pack(side=TOP)
            self.progress_counter = 75

    """\
    Removes the progress bar.
    """
    def removeProgressBar(self):
        if self.progress_bar_container:
            self.progress_bar.destroy()
            self.progress_bar_label.destroy()
            self.progress_bar_container.destroy()

    """\
    Checks the parser thread to see if it finished.
    """
    def checkParser(self):
        self.processQueue()
        if not self.log_parser.running:
            self.parsing = False
            self.removeProgressBar()
            result = not (self.log_parser_error or self.log_parser.has_error)
            if result:
                tkinter.messagebox.showinfo('Successfully Converted Log File', 'Log file was converted succesfully.')
            else:
                tkinter.messagebox.showinfo('Failed To Parse Log File', 'The log file failed to parse.')
        else:
            self.after(CHECK_DELAY, self.checkParser)

    """\
    Updates the progress bar's progress value.
    """
    def setProgressBar(self, value):
        if self.progress_bar:
            self.progress_counter = value

    """\
    Updates the progress bar if one exists by pulling messages from worker thread
    off of queue.
    """
    def processQueue(self):
        while (self.log_parser_queue.qsize()):
            try:
                message = self.log_parser_queue.get_nowait()

                if not isinstance(message, (int, long, float, complex)):
                    self.showError(message)
                    self.parsing = False
                    self.log_parser_error = True
                else:
                    self.setProgressBar(message)

            except Queue.Empty:
                pass

    """\
    Shows an error message window.
    """
    def showError(self, message):
        tkinter.messagebox.showerror('Error Parsing Log File', 'There was an error parsing the log: ' + message)
        

"""\
Format the mavgen exceptions by removing "ERROR: ".
"""
def formatErrorMessage(message):
    #reObj = re.compile(r'^(ERROR):\s+',re.M);
    #matches = re.findall(reObj, message);
    #message = re.sub(reObj, '\n', message);

    #prefix = ("An error occurred in mavlogdump:" if len(matches) == 1 else "Errors occured in mavgen:\n")

    #return prefix + message
    return message


# End of Application class
# ---------------------------------


"""\
This class defines an options menu for the SLUGS log converter.
"""
# --------------- SLUGS Options ------------------
class SlugsOptionsMenu(OptionMenu):
    def __init__(self, master, status, *options):
        self.var = StringVar(master)
        self.var.set(status)
        OptionMenu.__init__(self, master, self.var, *options)
        self.config(font=('calibri',(10)),bg='white',width=12)
        self['menu'].config(font=('calibri',(10)),bg='white') 

"""\
This threaded client uses mavlogdump to parse the log.
"""
# --------------- Threaded Client ------------------
class LogParserThread:
    def __init__(self, master, opts, input, output):
        self.master = master
        self.opts = opts
        self.queue = Queue.Queue() # Used for outgoing data (integers=percents, strings=errors)
        #self.gui = Application(master, self.queue, self.endApplication)
        self.has_error = False
       
        # Open log and output files
        self.input_filename = input
        self.output_filename = output
        print(self.input_filename + " > " + self.output_filename)

        self.mlog = mavutil.mavlink_connection(self.output_filename,
                                          notimestamps=self.opts['no_timestamps'],
                                          dialect=self.opts['dialect'])
        print(self.mlog)
        self.output_file = open(self.output_filename, 'wb')
    
        # Set progress and output
        self.progress = 0 # from 0 to 100 (percent %)
        self.current_message = 0
        self.total_messages = 1
        self.current_timestamp = 0 # for timestamp alignment
        
        # Options parsing
        if self.opts['types'] is not None:
            self.types = self.opts['types'].split(',')

        if self.opts['debug']:
            print("Building " + self.opts['format'] + " file with types: " + str(self.types))

        self.opts['csv_sep'] = self.opts['csv_sep'].replace("tab","\t")

        # Write out a header row as we're outputting in CSV format.
        self.fields = [] # list of message fields
        self.fields_header = "" # header to print above data

        # Populate fields 
        if self.opts['format'] == 'csv':
            try:
                currentOffset = 1 # Store how many fields in we are for each message.
                for type in self.types:
                    try:
                        typeClass = "MAVLink_{0}_message".format(type.lower())
                        self.fields += [type + '.' + x for x in inspect.getargspec(getattr(get_dialect_module(), typeClass).__init__).args[1:]]
                    except IndexError, e:
                        self.queue.put("An indexing error occurred while checking message types.")
                        raise e
            except TypeError, e:
                self.has_error = True
                self.queue.put("No message types were specified for parsing.")
                raise e
            except:
                self.has_error = True
                self.queue.put("An unknown error occurred while checking message types.")
                raise

        # Build field header and structs for message fields to sample and hold 
        self.window = OrderedDict()
        for field in self.fields:
            if self.fields_header:
                self.fields_header += self.opts['csv_sep'] + " "
            self.fields_header += field.replace('.', '_')
            self.window[field] = 0 # initialize all fields to zero

        if self.opts['debug']:
            print("Initialized sample window fields: " + str(self.window))

        self.fields_header = self.fields_header.rstrip(self.opts['csv_sep']) # remove ending separator

    """\
    Prints headers to the output file and starts the worker thread 
    to begin parsing.
    """
    def startParsing(self):
        # Print data description header section
        if self.opts['print_description']:
            self.output_file.write('Description data:\r\n')
            i = 1
            for field in self.fields:
                field = field.replace('.', '_')
                self.output_file.write(field.upper() + " {" + str(i) + '}\r\n')
                i += 1

            self.output_file.write('End description data\r\n\r\n')

        # Print field names in a header row
        self.output_file.write(self.fields_header.upper() + '\r\n')

        # Start running
        self.running = 1
        self.progress = 0 # from 0 to 100 (percent %)
        self.thread1 = threading.Thread(target=self.workerThread1)
        self.thread1.start()

        #self.periodicCall()

    """\
    Quits the thread if it's not running.
    """
    def periodicCall(self):
        if not self.running:
            import sys
            sys.exit(1)
        self.master.after(UPDATE_DELAY, self.periodicCall)

    """\
    Thread for calling doParse().
    """
    def workerThread1(self):
        while self.running:
            #sleep(READ_DELAY)

            # parse a message and add progress to queue
            self.doParse()
            self.queue.put(self.progress)
 

    """\
    Parse a single message from the log file and write into output file.
    """
    def doParse(self):
        sleep(5)
        m = self.mlog.recv_match(type=self.types, blocking=False, condition=None)
        print("Got: " + str(m) + " from " + str(self.types))
        if m is None:
            self.percent = 100
            self.endApplication()
            return # finished

        # Grab percentage through file
        self.percent = self.mlog.percent()

        if self.types is not None and m.get_type() not in self.types and m.get_type() != 'BAD_DATA':
            return # message not in types
        
        # TODO keep a count of bad data here
        if m.get_type() == 'BAD_DATA' and m.reason == "Bad prefix":
            return

        # Save fields into window
        data = m.to_dict()
        type = m.get_type()
        
        # Iterate over all fields of data and set the window
        for field,value in data.items():
            key = type + "." + field
            if (key in self.window):
                self.window[key] = value

        # Skip message if timestamp didnt change
        if self.opts['align_timestamps'] and self.current_timestamp == self.window[self.opts['align_timestamp_field']]:
            return

        self.current_timestamp = self.window[self.opts['align_timestamp_field']]

        if self.opts['format'] == 'csv':
            # Build the line
            out = []
            values = self.window.values()
            for v in values:
                out.append(str(v))
            
            out = self.opts['csv_sep'].join(out)
            out = out.rstrip(self.opts['csv_sep'])
            if self.opts['debug']:
                self.output_file.write(out + " ----- " + type + '\r\n')
            else:
                self.output_file.write(out + '\r\n')
            
    def endApplication(self):
        """\
        Causes the terminal update thread to quit.

        """
        self.running = 0

"""-------------------------------------------------------------
                              Start
   -------------------------------------------------------------"""


if __name__ == '__main__':
  app = Application()
  app.master.title(title)
  app.mainloop()
