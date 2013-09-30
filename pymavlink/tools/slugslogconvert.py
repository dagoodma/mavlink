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
import os
#import re
import pprint
from subprocess import call

# Python 2.x and 3.x compatability
try:
    from tkinter import *
    import tkinter.filedialog
    import tkinter.messagebox
except ImportError as ex:
    # Must be using Python 2.x, import and rename
    from Tkinter import *
    import tkFileDialog
    import tkMessageBox

    tkinter.filedialog = tkFileDialog
    del tkFileDialog
    tkinter.messagebox = tkMessageBox
    del tkMessageBox

#sys.path.append(os.path.join('pymavlink','generator'))
#from mavgen import *

DEBUG = True
title = "SLUGS Log Converter"
conversion_script = "mavlogdump_samplehold.py"
message_types = "ATTITUDE,LOCAL_POSITION_NED,GPS_RAW_INT,GPS_DATE_TIME,SLUGS_NAVIGATION,RAW_IMU,SCALED_PRESSURE,CPU_LOAD,HEARTBEAT,SYS_STATUS,RC_CHANNELS_RAW,SERVO_OUTPUT_RAW,SCALED_IMU,RAW_PRESSURE,MID_LVL_CMDS,SENSOR_DIAG,VOLT_SENSOR,STATUS_GPS,NOVATEL_DIAG,PTZ_STATUS"
conversion_args = "--format=csv --no-timestamps --dialect=slugs --types={0} --csv_sep=\",tab\"".format(message_types)
error_limit = 5


class Application(Frame):
    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.pack_propagate(0)
        self.grid( sticky=N+S+E+W)
        self.createWidgets()
        self.pp = pprint.PrettyPrinter(indent=4)

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

        # Run log conversion script
        args = conversion_args + " " + self.binary_log_value.get() + " > " + self.out_value.get()
        cmd = "python " + conversion_script + " " + args
        result = 0

        if DEBUG:
            print("Converting log file")
            self.pp.pprint(cmd)
        try:
            result = call(cmd,shell=True)
            if result == 0:
                tkinter.messagebox.showinfo('Successfully Converted Log File', 'Log file was converted succesfully.')
            else:
                raise Exception(conversion_script + " returned with error code " + str(result) + ". See terminal for details.")

        except Exception as ex:
            #exStr = formatErrorMessage(str(ex));
            exStr  = str(ex)
            if DEBUG:
                print('An occurred while converting log file: \n\t{0!s}'.format(ex))
            tkinter.messagebox.showerror('Error Converting Log File','{0!s}'.format(exStr))
            return

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

# ---------------------------------
# Start

if __name__ == '__main__':
  app = Application()
  app.master.title(title)
  app.mainloop()
