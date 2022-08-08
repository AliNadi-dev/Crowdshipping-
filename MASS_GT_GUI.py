# -*- coding: utf-8 -*-
"""
Created on Fri May 29 10:47:15 2020

@author: STH
"""

# Importeer de modules van het model
import __module_FS__
import __module_SIF__
import __module_SHIP__
import __module_TOUR__
import __module_PARCEL_DMND__
import __module_PARCEL_SCHD__
import __module_SERVICE__
import __module_TRAF__
import __module_OUTP__

# Libraries nodig voor de user interface
import tkinter as tk
from tkinter import filedialog
from tkinter.ttk import Progressbar
import os.path
from sys import argv
import zlib
import base64
import tempfile
from threading import Thread
import multiprocessing as mp
import sys
import traceback
import datetime


# Class and functions: Graphical User Interface
class Root:

    def __init__(self):
        '''
        Initialize a GUI object
        '''
        # Get directory of the script
        self.datapath = os.path.dirname(os.path.realpath(argv[0]))
        self.datapath = self.datapath.replace(os.sep, '/') + '/'

        self.moduleNames = [
            'FS', 'SIF',
            'SHIP', 'TOUR',
            'PARCEL_DMND', 'PARCEL_SCHD',
            'SERVICE',
            'TRAF',
            'OUTP']

        # Set graphics parameters
        self.width = 950
        self.height = 120
        self.bg = 'black'
        self.fg = 'white'
        self.font = 'Verdana'

        # Create a GUI window
        self.root = tk.Tk()
        self.root.title("Tactical Freight Simulator HARMONY")
        self.root.geometry(f'{self.width}x{self.height}+0+0')
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=self.bg)
        self.canvas.place(x=0, y=0)
        self.statusBar = tk.Label(
            self.root,
            text="",
            anchor='w',
            borderwidth=0,
            fg='black')
        self.statusBar.place(
            x=2,
            y=self.height - 22,
            width=self.width,
            height=22)

        # Remove the default tkinter icon from the window
        icon = zlib.decompress(base64.b64decode(
            'eJxjYGAEQgEBBiDJwZDBy' +
            'sAgxsDAoAHEQCEGBQaIOAg4sDIgACMUj4JRMApGwQgF/ykEAFXxQRc='))
        _, self.iconPath = tempfile.mkstemp()
        with open(self.iconPath, 'wb') as iconFile:
            iconFile.write(icon)
        self.root.iconbitmap(bitmap=self.iconPath)

        # Create control file label and entry
        self.labelControlFile = tk.Label(
            self.root,
            text='Control file:',
            width=20,
            height=1,
            anchor='w',
            bg=self.bg,
            fg=self.fg,
            font=(self.font, 8))
        self.labelControlFile.place(x=5, y=9)
        self.controlFile = tk.StringVar(self.root, self.datapath)
        self.entryControlFile = tk.Entry(
            self.root,
            textvariable=self.controlFile,
            width=120,
            font=(self.font, 8))
        self.entryControlFile.place(x=80, y=10)

        # Create button to search for control file
        self.searchButton = tk.Button(
            self.root,
            text="...",
            command=self.file_dialog,
            width=2,
            font=(self.font, 5))
        self.searchButton.place(x=905, y=12)

        # Create button to run the main function
        self.runButton = tk.Button(
            self.root,
            text="Run",
            width=15,
            height=3,
            command=self.run_main,
            font=(self.font, 8))
        self.runButton.place(x=425, y=35)

        self.progressBar = Progressbar(
            self.root,
            length=int(self.width / 2))
        self.progressBar.place(x=int(self.width / 2), y=self.height - 22)

        # If the control file is passed as an argument
        # in a batch job or in the command line prompt
        if len(argv) > 1:
            self.controlFile.set(argv[1])
            self.run_main()

        # Keep GUI active until closed
        self.root.mainloop()

    def update_statusbar(self, text):
        self.statusBar.configure(text=text)

    def reset_statusbar(self, event=None):
        self.statusBar.configure(text="")

    def file_dialog(self):
        '''
        Open up a file dialog
        '''
        self.filename = filedialog.askopenfilename(
            initialdir="/",
            title="Select the .ini control file",
            filetype=(("Control files (.ini)", "*.ini"), ("All files", "*.*")))
        self.controlFile.set(self.filename)

    def run_main(self, event=None):
        Thread(target=self.actually_run_main, daemon=True).start()

    def actually_run_main(self):
        '''
        Run the actual emission calculation
        '''
        # All the allowed keys in the control file
        self.varStrings = [
            "INPUTFOLDER", "OUTPUTFOLDER", "PARAMFOLDER", "DIMFOLDER",
            "SKIMTIME", "SKIMDISTANCE",
            "LINKS", "NODES",
            "EMISSIONFACS_BUITENWEG_LEEG", "EMISSIONFACS_BUITENWEG_VOL",
            "EMISSIONFACS_SNELWEG_LEEG", "EMISSIONFACS_SNELWEG_VOL",
            "EMISSIONFACS_STAD_LEEG", "EMISSIONFACS_STAD_VOL",
            "ZONES", "SEGS", "SUP_COORDINATES_ID",
            "DISTRIBUTIECENTRA", "DC_OPP_NUTS3",
            "NSTR_TO_LS",
            "MAKE_DISTRIBUTION", "USE_DISTRIBUTION",
            "DEPTIME_FREIGHT", "DEPTIME_PARCELS",
            "FIRMSIZE", "SBI_TO_SEGS",
            "COST_VEHTYPE", "COST_SOURCING",
            "COMMODITYMATRIX",
            "PARCELNODES", "CEP_SHARES",
            "MRDH_TO_NUTS3", "NUTS3_TO_MRDH", "MRDH_TO_COROP",
            "VEHICLE_CAPACITY",
            "LOGISTIC_FLOWTYPES",
            "PARAMS_SIF_PROD", "PARAMS_SIF_ATTR",
            "PARAMS_TOD", "PARAMS_SSVT",
            "PARAMS_ET_FIRST", "PARAMS_ET_LATER",
            "PARAMS_ECOMMERCE",
            "SERVICE_DISTANCEDECAY", "SERVICE_PA",
            "PARCELS_PER_HH", "PARCELS_PER_EMPL",
            "PARCELS_MAXLOAD", "PARCELS_DROPTIME",
            "PARCELS_SUCCESS_B2C", "PARCELS_SUCCESS_B2B",
            "PARCELS_GROWTHFREIGHT",
            "CROWDSHIPPING",
            "CRW_PARCELSHARE", "CRW_MODEPARAMS",
            "CRW_PDEMAND_CAR", "CRW_PDEMAND_BIKE",
            "ZEZ_CONSOLIDATION", "ZEZ_SCENARIO",
            "NEAREST_DC",
            "NUTSLEVEL_INPUT",
            "YEARFACTOR",
            "IMPEDANCE_SPEED_FREIGHT", "IMPEDANCE_SPEED_VAN",
            "N_CPU", "N_MULTIROUTE",
            "SHIPMENTS_REF", "FIRMS_REF",
            "SELECTED_LINKS",
            "CORRECTIONS_TONNES",
            "MICROHUBS", "VEHICLETYPES",
            "FAC_LS0", "FAC_LS1", "FAC_LS2", "FAC_LS3",
            "FAC_LS4", "FAC_LS5", "FAC_LS6", "FAC_LS7",
            "SHIFT_FREIGHT_TO_COMB1", "SHIFT_VAN_TO_COMB1",
            "SHIFT_FREIGHT_TO_COMB2",
            "LABEL",
            "MODULES"]
        nVars = len(self.varStrings)

        # At which index car the output, input and parameter folder be found
        whereOutputFolder, whereInputFolder, whereParamFolder, whereDimFolder = (
            None, None, None, None)
        for i in range(nVars):
            if self.varStrings[i] == "OUTPUTFOLDER":
                whereOutputFolder = i
            elif self.varStrings[i] == "INPUTFOLDER":
                whereInputFolder = i
            elif self.varStrings[i] == "PARAMFOLDER":
                whereParamFolder = i
            elif self.varStrings[i] == "DIMFOLDER":
                whereDimFolder = i

        # A list for the values belonging to each key in the control file
        varValues = ["" for i in range(nVars)]

        # Which variables are of numeric nature
        numericVars = [
            "PARCELS_PER_HH", "PARCELS_PER_EMPL",
            "PARCELS_MAXLOAD", "PARCELS_DROPTIME",
            "PARCELS_SUCCESS_B2C", "PARCELS_SUCCESS_B2B",
            "PARCELS_GROWTHFREIGHT",
            "YEARFACTOR",
            "NUTSLEVEL_INPUT",
            "CRW_PARCELSHARE",
            "N_MULTIROUTE",
            "FAC_LS0", "FAC_LS1", "FAC_LS2", "FAC_LS3",
            "FAC_LS4", "FAC_LS5", "FAC_LS6", "FAC_LS7",
            "SHIFT_FREIGHT_TO_COMB1", "SHIFT_VAN_TO_COMB1",
            "SHIFT_FREIGHT_TO_COMB2"]
        
        # Which variables refer to a directory path
        dirVars = [
            "INPUTFOLDER",
            "OUTPUTFOLDER",
            "PARAMFOLDER",
            "DIMFOLDER"]

        # Which variables refer to the modules that need to be run
        moduleVars = [
            "MODULES"]

        # Which variables refer to a file path
        fileVars = [
            "SKIMTIME", "SKIMDISTANCE",
            "LINKS", "NODES",
            "EMISSIONFACS_BUITENWEG_LEEG", "EMISSIONFACS_BUITENWEG_VOL",
            "EMISSIONFACS_SNELWEG_LEEG", "EMISSIONFACS_SNELWEG_VOL",
            "EMISSIONFACS_STAD_LEEG", "EMISSIONFACS_STAD_VOL",
            "ZONES", "SEGS", "SUP_COORDINATES_ID",
            "DISTRIBUTIECENTRA", "DC_OPP_NUTS3",
            "NSTR_TO_LS",
            "MAKE_DISTRIBUTION", "USE_DISTRIBUTION",
            "DEPTIME_FREIGHT", "DEPTIME_PARCELS",
            "FIRMSIZE", "SBI_TO_SEGS",
            "COST_VEHTYPE", "COST_SOURCING",
            "COMMODITYMATRIX",
            "PARCELNODES", "CEP_SHARES",
            "MRDH_TO_NUTS3", "NUTS3_TO_MRDH", "MRDH_TO_COROP",
            "VEHICLE_CAPACITY",
            "LOGISTIC_FLOWTYPES",
            "PARAMS_SIF_PROD", "PARAMS_SIF_ATTR",
            "PARAMS_TOD", "PARAMS_SSVT",
            "PARAMS_ET_FIRST", "PARAMS_ET_LATER",
            "PARAMS_ECOMMERCE",
            "SERVICE_DISTANCEDECAY", "SERVICE_PA",
            "ZEZ_CONSOLIDATION", "ZEZ_SCENARIO",
            "SHIPMENTS_REF", "FIRMS_REF",
            "CORRECTIONS_TONNES",
            "CRW_MODEPARAMS", "CRW_PDEMAND_CAR", "CRW_PDEMAND_BIKE",
            "MICROHUBS", "VEHICLETYPES"]

        # Variables that became obsolete due to changes in the modules
        # keep these in here to prevent errors on older ini files with these
        # arguments still in there
        obsoleteVars = [
            "DEPTIME_FREIGHT",
            "PARCELS_PER_HH"]

        # Variables for which a value in the control file is not obligatory
        optionalVars = [
            "SHIPMENTS_REF", "FIRMS_REF",
            "CORRECTIONS_TONNES",
            "SELECTED_LINKS",
            "N_CPU",
            "N_MULTIROUTE",
            "CROWDSHIPPING",
            "NEAREST_DC",
            "CRW_PARCELSHARE", "CRW_MODEPARAMS",
            "CRW_PDEMAND_CAR", "CRW_PDEMAND_BIKE",
            "MICROHUBS", "VEHICLETYPES",
            "FAC_LS0", "FAC_LS1", "FAC_LS2", "FAC_LS3",
            "FAC_LS4", "FAC_LS5", "FAC_LS6", "FAC_LS7",
            "SHIFT_FREIGHT_TO_COMB1", "SHIFT_VAN_TO_COMB1",
            "SHIFT_FREIGHT_TO_COMB2"]
        optionalVars = optionalVars + obsoleteVars

        # Run the modules or not, is set to False if, for example,
        # an input file could not be found
        run = True

        # Write a log file or not, is set to False if the specified
        # outputfolder does not exist
        writeLog = True

        # In this string we collect the error messages
        errorMessage = ""

        try:

            with open(self.controlFile.get(), 'r') as f:
                lines = f.readlines()

                for line in lines:

                    if len(line.split('=')) > 1:

                        if line[0] != '#':

                            key = line.split('=')[0]
                            value = line.split('=')[1]

                            # Allow spaces and tabs before/after the key
                            # and the value
                            while key[0] == ' ' or key[0] == '\t':
                                key = key[1:]

                            while key[-1] == ' ' or key[-1] == '\t':
                                key = key[0:-1]

                            while value[0] == ' ' or value[0] == '\t':
                                value = value[1:]

                            while value[-1] == ' ' or value[-1] == '\t':
                                value = value[0:-1]

                            print(key + ' = ' + value.replace('\n', ""))

                            # Read the arguments in the control file
                            for i in range(nVars):
                                if key.upper() == self.varStrings[i]:

                                    # For numeric arguments, check if they
                                    # can be converted from string to float
                                    if self.varStrings[i] in numericVars:
                                        value = value.replace("'", "")
                                        value = value.replace('"', "")
                                        value = value.replace('\n', "")

                                        try:
                                            varValues[i] = float(value)
                                        except ValueError:
                                            if not (value == '' and value in optionalVars):
                                                varValues[i] = value
                                                errorMessage = (
                                                    errorMessage +
                                                    'Fill in a numeric value for ' +
                                                    self.varStrings[i] +
                                                    ', could not convert following value to a number: ' +
                                                    value +
                                                    "\n")
                                                run = False

                                    # The argument which states which
                                    # modules should be run
                                    elif self.varStrings[i] in moduleVars:
                                        value = value.replace("'", "")
                                        value = value.replace('"', "")
                                        value = value.replace('\n', "")
                                        value = value.replace(' ', '')
                                        varValues[i] = value
                                        varValues[i] = varValues[i].split(',')

                                        for j in range(len(varValues[i])):
                                            varValues[i][j] = varValues[i][j].upper()

                                            if varValues[i][j] not in self.moduleNames:
                                                errorMessage = (
                                                    errorMessage +
                                                    'Module ' +
                                                    varValues[i][j] +
                                                    ' does not exist.' +
                                                    '\n')
                                                run = False

                                    # For string arguments, also replace
                                    # possible '\' by '/'
                                    else:
                                        value = value.replace(os.sep, '/')
                                        value = value.replace("'", "")
                                        value = value.replace('"', "")
                                        value = value.replace('\n', "")
                                        varValues[i] = value

                                        if self.varStrings[i] in dirVars:
                                            if varValues[i][-1] != '/':
                                                varValues[i] = varValues[i] + '/'

                                        if self.varStrings[i] in dirVars or self.varStrings[i] in fileVars:
                                            if self.varStrings[i] not in dirVars:
                                                tmp = varValues[i].split("<<")

                                                if len(tmp) > 1:
                                                    tmp = tmp[1].split(">>")

                                                    if tmp[0] == 'OUTPUTFOLDER':
                                                        varValues[i] = varValues[whereOutputFolder] + tmp[1]
                                                    if tmp[0] == 'INPUTFOLDER':
                                                        varValues[i] = varValues[whereInputFolder] + tmp[1]
                                                    if tmp[0] == 'PARAMFOLDER':
                                                        varValues[i] = varValues[whereParamFolder] + tmp[1] 
                                                    if tmp[0] == 'DIMFOLDER':
                                                        varValues[i] = varValues[whereDimFolder] + tmp[1] 

                            # Warning for unknown argument in control file
                            if key.upper() not in self.varStrings:
                                errorMessage = (
                                    errorMessage +
                                    'Unknown parameter in control file: ' +
                                    key +
                                    "\n")
                                run = False

            for i in range(nVars):

                # Warnings for non-existing directories
                if self.varStrings[i] in dirVars:
                    if not os.path.isdir(varValues[i]) and varValues[i] != "":
                        errorMessage = (
                            errorMessage +
                            'The folder for parameter ' +
                            self.varStrings[i] +
                            ' does not exist: ' +
                            "'" + varValues[i] + "'" +
                            "\n")
                        run = False

                        # Can't write a logfile if the outputfolder
                        # does not exist
                        if self.varStrings[i] == "OUTPUTFOLDER":
                            writeLog = False

                # Warnings for non-existing files
                if self.varStrings[i] in fileVars:
                    if not os.path.isfile(varValues[i]) and varValues[i] != "":
                        errorMessage = (
                            errorMessage +
                            'The file for parameter ' +
                            self.varStrings[i] +
                            ' does not exist: ' +
                            "'" + varValues[i] + "'" +
                            "\n")
                        run = False

            # Warnings for omitted arguments in control file
            for i in range(nVars):
                if varValues[i] == "" and self.varStrings[i] not in optionalVars:
                    errorMessage = (
                        errorMessage +
                        'Warning, no value given for parameter ' +
                        self.varStrings[i] +
                        ' in the controle file.' +
                        "\n")
                    run = False                    

        except Exception:
            errorMessage = (
                'Could not find or read the following control file: ' +
                "'" + self.controlFile.get() + "'" +
                '\n\n' + str(sys.exc_info()[0]) +
                '\n\n' + str(traceback.format_exc()))
            run = False
            writeLog = False

        # Make a dictionary of the input arguments
        varDict = {}
        for i in range(nVars):
            varDict[self.varStrings[i]] = varValues[i]

        # Check for outputfolder files when not all modules are run
        if os.path.isdir(varDict['OUTPUTFOLDER']):
            outFileChecks = [
                ["SHIP",
                 "SIF",
                 "CommodityMatrixNUTS3.csv"],
                ["TOUR",
                 "SHIP",
                 "Shipments_" + varDict['LABEL'] + ".csv"],
                ["PARCEL_SCHD",
                 "PARCEL_DMND",
                 "ParcelDemand_" + varDict['LABEL'] + ".csv"],
                ["TRAF",
                 "TOUR",
                 "Tours_" + varDict['LABEL'] + ".csv"],
                ["TRAF",
                 "TOUR",
                 "tripmatrix_" + varDict['LABEL'] + ".txt"],
                ["TRAF",
                 "TOUR",
                 "tripmatrix_" + varDict['LABEL'] + "_TOD0" + ".txt"],
                ["TRAF",
                 "PARCEL_SCHD",
                 "ParcelSchedule_" + varDict['LABEL'] + ".csv"],
                ["TRAF",
                 "PARCEL_SCHD",
                 "tripmatrix_parcels_" + varDict['LABEL'] + ".txt"],
                ["TRAF",
                 "PARCEL_SCHD",
                 "tripmatrix_parcels_" + varDict['LABEL'] + "_TOD0" + ".txt"],
                ["TRAF",
                 "SERVICE",
                 "TripsVanService.mtx"],
                ["TRAF",
                 "SERVICE",
                 "TripsVanConstruction.mtx"]]

            if varDict['FIRMS_REF'] == '':
                outFileChecks.append([
                    "SHIP",
                    "FS",
                    "Firms.csv"])

            for x in outFileChecks:
                moduleWhichIsRun = x[0]
                moduleWhichIsNotRun = x[1]
                outfileToCheck = x[2]

                if moduleWhichIsRun in varDict['MODULES']:
                    if moduleWhichIsNotRun not in varDict['MODULES']:
                        if not os.path.isfile(varDict['OUTPUTFOLDER'] + outfileToCheck):
                            run = False
                            errorMessage = errorMessage + (
                                'Module ' +
                                moduleWhichIsRun +
                                ' is run but preceding module ' +
                                moduleWhichIsNotRun +
                                ' is not run. ' +
                                'In that case the following file is expected' +
                                ' in the OUTPUTFOLDER, but it is not found: "' +
                                outfileToCheck + '".\n')

        # Check on text files with dimensions / categories
        if os.path.isdir(varDict['DIMFOLDER']):
            dimFilenames = [
                'combustion_type.txt',
                'emission_type.txt',
                'employment_sector.txt',
                'flow_type.txt',
                'logistic_segment.txt',
                'municipality.txt',
                'nstr.txt',
                'shipment_size.txt',
                'vehicle_type.txt']
            for filename in dimFilenames:
                if not os.path.isfile(varDict['DIMFOLDER'] + filename):
                    run = False
                    errorMessage = errorMessage + (
                        'Expected a text file called ' +
                        '"' + filename + '"' +
                        ' in DIMFOLDER, but could not find it.')
            
        # Open the logfile and write the header, specified arguments and
        # possible error messages
        if writeLog:
            self.logFileName = (
                varValues[whereOutputFolder] +
                "Logfile_20" +
                datetime.datetime.now().strftime("%y%m%d_%H%M%S") +
                ".log")

            with open(self.logFileName, "w") as f:
                f.write('##################################################\n')
                f.write('### Tactical Freight Simulator HARMONY         ###\n')
                f.write('### Prototype version, January 2022            ###\n')
                f.write('##################################################\n')
                f.write('\n')

                f.write('##################################################\n')
                f.write('### Settings                                   ###\n')
                f.write('##################################################\n')

                f.write('Control file: ' + self.controlFile.get() + '\n')
                for i in range(len(varValues)):
                    f.write(self.varStrings[i] + ' = ' + str(varValues[i]) + '\n')

                    if self.varStrings[i] in obsoleteVars and self.varStrings[i] != '':
                        f.write(
                            '\t(Note that variable ' +
                            self.varStrings[i] +
                            ' has become obsolete.' +
                            ' It is not used in any of the modules anymore.)\n')
                f.write('\n')

                if not run:
                    f.write('###################################################\n')
                    f.write('### Errors while reading control file           ###\n')
                    f.write('###################################################\n')
                    f.write(errorMessage)

        if run:
            self.statusBar.configure(text="Start calculations...")
            result = self.main(varDict)
            self.statusBar.configure(text="")

            if result[0] == 1:
                self.statusBar.configure(text=(
                    "Error in calculation! " +
                    "(Tool will be closed automatically after 20 seconds.)"))
                self.root.after(20000, lambda: self.root.destroy())

            else:
                self.statusBar.configure(text="Calculations finished.")
                self.progressBar['value'] = 100
                self.root.after(5000, lambda: self.root.destroy())

        else:
            self.statusBar.configure(text=(
                "Run was not started. See error message. "))
            errorMessage = (
                "Could not start the run for the following reasons: \n\n" +
                errorMessage)
            self.error_screen(text=errorMessage, size=[950, 150])

    def error_screen(self, text='', event=None,
                     size=[950, 350], title='Error message'):
        '''
        Pop up a window with an error message
        '''
        windowError = tk.Toplevel(self.root)
        windowError.title(title)
        windowError.geometry(f'{size[0]}x{size[1]}+0+{self.height+50}')
        windowError.minsize(width=size[0], height=size[1])
        windowError.iconbitmap(bitmap=self.iconPath)
        labelError = tk.Label(
            windowError,
            text=text,
            anchor='w',
            justify='left')
        labelError.place(x=10, y=10)

    def main(self, varDict):

        run = True
        result = [0, 0]

        with open(self.logFileName, "a") as f:

            f.write('###################################################\n')
            f.write('### Progress                                    ###\n')
            f.write('###################################################\n')

            args = [self, varDict]

            if run and 'FS' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('--------------- Firm Synthesis --------------------')
                print('---------------------------------------------------')
                f.write("Firm Synthesis" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Firm Synthesis...')

                result = __module_FS__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Firm Synthesis module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run and 'SIF' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('--------- Spatial Interaction Freight -------------')
                print('---------------------------------------------------')
                f.write("Spatial Interaction Freight" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Spatial Interaction Freight...')

                result = __module_SIF__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Spatial Interaction Freight module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run and 'SHIP' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('------------- Shipment Synthesizer ----------------')
                print('---------------------------------------------------')
                f.write("Shipment Synthesizer" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Shipment Synthesizer...')

                result = __module_SHIP__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Shipment Synthesizer module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run and 'TOUR' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('---------------- Tour Formation -------------------')
                print('---------------------------------------------------')
                f.write("Tour Formation" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Tour Formation...')

                result = __module_TOUR__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Tour Formation module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run and 'PARCEL_DMND' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('---------------- Parcel Demand --------------------')
                print('---------------------------------------------------')
                f.write("Parcel Demand" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Parcel Demand...')

                result = __module_PARCEL_DMND__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Parcel Demand module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run and 'PARCEL_SCHD' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('-------------- Parcel Scheduling ------------------')
                print('---------------------------------------------------')
                f.write("Parcel Scheduling" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Parcel Scheduling...')

                result = __module_PARCEL_SCHD__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Parcel Scheduling module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run and 'SERVICE' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('---------- Vans Service/Construction --------------')
                print('---------------------------------------------------')
                f.write("Vans Service/Construction" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Vans Service/Construction...')

                result = __module_SERVICE__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Vans Service/Construction module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run and 'TRAF' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('-------------- Traffic Assignment -----------------')
                print('---------------------------------------------------')
                f.write("Traffic Assignment" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Traffic Assignment...')

                result = __module_TRAF__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Traffic Assignment module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run and 'OUTP' in varDict['MODULES']:
                print('\n')
                print('---------------------------------------------------')
                print('--------------- Output Indicators -----------------')
                print('---------------------------------------------------')
                f.write("Output Indicators" + '\n')
                f.write(
                    "\tStarted at:    " +
                    datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                    "\n")

                self.statusBar.configure(
                    text='Running Output Indicators...')

                result = __module_OUTP__.actually_run_module(args)

                if result[0] == 1:
                    errorMessage = []
                    errorMessage.append(
                        '\nError in Output Indicators module!\n\n')
                    errorMessage.append(
                        'See the log-file: ' +
                        str(self.logFileName).split('/')[-1] + '\n\n')
                    errorMessage.append(
                        str(result[1][0]) + '\n' +
                        str(result[1][1]) + '\n\n')
                    self.error_screen(text=(
                        errorMessage[0] +
                        errorMessage[1] +
                        errorMessage[2]))
                    run = False
                    f.write(errorMessage[0] + errorMessage[2])
                else:
                    f.write(
                        "\tFinished at: " +
                        datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S") +
                        "\n\n")

            if run:
                f.write('Finished all calculations.')
                self.statusBar.configure(text='Finished all calculations.')

        return result


# Run the script
if __name__ == '__main__':
    mp.freeze_support()
    root = Root()
