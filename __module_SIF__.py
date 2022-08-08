# -*- coding: utf-8 -*-
"""
Created on Wed Jan  6 10:53:26 2021

@author: modelpc
"""
import numpy as np
import pandas as pd
import time
import datetime

# Modules nodig voor de user interface
import tkinter as tk
from tkinter.ttk import Progressbar
import zlib
import base64
import tempfile
from threading import Thread


def main(varDict):
    '''
    Start the GUI object which runs the module
    '''
    root = Root(varDict)

    return root.returnInfo


class Root:

    def __init__(self, args):
        '''
        Initialize a GUI object
        '''
        # Set graphics parameters
        self.width = 500
        self.height = 60
        self.bg = 'black'
        self.fg = 'white'
        self.font = 'Verdana'

        # Create a GUI window
        self.root = tk.Tk()
        self.root.title("Progress Spatial Interaction Freight")
        self.root.geometry(f'{self.width}x{self.height}+0+200')
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=self.bg)
        self.canvas.place(
            x=0,
            y=0)
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

        # Create a progress bar
        self.progressBar = Progressbar(self.root, length=self.width - 20)
        self.progressBar.place(x=10, y=10)

        self.returnInfo = ""

        if __name__ == '__main__':
            self.args = [[self, args]]
        else:
            self.args = [args]

        self.run_module()

        # Keep GUI active until closed
        self.root.mainloop()

    def update_statusbar(self, text):
        self.statusBar.configure(text=text)

    def error_screen(self, text='', event=None,
                     size=[800, 50], title='Error message'):
        '''
        Pop up a window with an error message
        '''
        windowError = tk.Toplevel(self.root)
        windowError.title(title)
        windowError.geometry(f'{size[0]}x{size[1]}+0+{200+50+self.height}')
        windowError.minsize(width=size[0], height=size[1])
        windowError.iconbitmap(default=self.iconPath)
        labelError = tk.Label(
            windowError,
            text=text,
            anchor='w',
            justify='left')
        labelError.place(x=10, y=10)

    def run_module(self, event=None):
        Thread(target=actually_run_module, args=self.args, daemon=True).start()


def actually_run_module(args):

    try:

        root = args[0]
        varDict = args[1]

        start_time = time.time()

        log_file = open(
            varDict['OUTPUTFOLDER'] + "Logfile_SpatialInteractionFreight.log",
            "w")
        log_file.write(
            "Start simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")

        if varDict['NUTSLEVEL_INPUT'] not in [2, 3]:
            raise BaseException(
                "Error! NUTSLEVEL_INPUT needs to be either 2 or 3. " +
                "Current value is: " + str(varDict['NUTSLEVEL_INPUT']) + '.')

        dimNSTR = pd.read_csv(
            varDict['DIMFOLDER'] + 'nstr.txt',
            sep='\t')

        nNSTR = len(dimNSTR) - 1
        nForeignZones = 3

        # ------------------- Importing and preparing data --------------------

        print('Importing and preparing data...')
        log_file.write('Importing and preparing data...' + '\n')

        print('\tCoefficients for production and attraction...')
        log_file.write(
            '\tCoefficients for production and attraction...' + '\n')

        # Importing production/attraction coefficients
        coeffProd = pd.read_csv(
            varDict['PARAMS_SIF_PROD'],
            sep=',',
            index_col=[0])
        coeffAttr = pd.read_csv(
            varDict['PARAMS_SIF_ATTR'],
            sep=',',
            index_col=[0])
        coeffProd.index = np.arange(len(coeffProd))
        coeffAttr.index = np.arange(len(coeffAttr))

        message = (
            '\tCommodity matrix NUTS' +
            str(varDict['NUTSLEVEL_INPUT']) +
            '...')
        print(message)
        log_file.write(message + '\n')

        if varDict['NUTSLEVEL_INPUT'] == 2:
            comMatNUTS2 = pd.read_csv(varDict['COMMODITYMATRIX'], sep=',')
        elif varDict['NUTSLEVEL_INPUT'] == 3:
            comMatNUTS3 = pd.read_csv(varDict['COMMODITYMATRIX'], sep=',')

        print('\tCoupling table MRDH to NUTS3...')
        log_file.write('\tCoupling table MRDH to NUTS3...' + '\n')

        MRDHtoNUTS3 = pd.read_csv(varDict['MRDH_TO_NUTS3'], sep=',')
        MRDHtoNUTS3.index = MRDHtoNUTS3['AREANR']

        print('\tMRDH SEGS...')
        log_file.write('\tMRDH SEGS...' + '\n')

        segs = pd.read_csv(varDict['SEGS'], sep=',')
        segs.index = segs['zone']

        # Checking for which MRDH-zones in the SEGS we know the NUTS3-zone
        temp = np.array(MRDHtoNUTS3.index)
        toKeep = [x for x in segs['zone'] if x in temp]
        segs = segs.loc[toKeep, :]

        # Determing SEGS per NUTS3-zones
        segs['NUTS3'] = MRDHtoNUTS3.loc[segs['zone'], 'NUTS_ID']
        segs = pd.pivot_table(
            segs,
            values=[
                'INDUSTRIE', 'DETAIL',
                'LANDBOUW', 'DIENSTEN',
                'OVERHEID', 'OVERIG'],
            index='NUTS3',
            aggfunc=np.sum)

        print('\tDC surface per NUTS3..')
        log_file.write('\tDC surface per NUTS3...' + '\n')

        dcData = pd.read_csv(varDict['DC_OPP_NUTS3'], sep=',')
        dcData.index = dcData['ZONE']
        dcZones = set(np.array(dcData['ZONE']))
        surfaceDC = {}
        for nuts3 in segs.index:
            if nuts3 in dcZones:
                surface = dcData['oppervlak'][nuts3]
                surfaceDC[nuts3] = surface
            else:
                surfaceDC[nuts3] = 0
        surfaceDC = pd.DataFrame(surfaceDC.values(), index=surfaceDC.keys())

        # -------- Determine production and attraction per municipality -------

        print('Determining production and attraction per NUTS3...')
        log_file.write(
            'Determining production and attraction per NUTS3...' + '\n')

        nNUTS3 = len(segs)
        codesNUTS3 = list(segs.index)

        for country in ['BE', 'DE', 'FR']:
            codesNUTS3.append(country)
        codesNUTS3 = np.array(codesNUTS3, dtype=str)

        production = np.zeros((nNUTS3 + nForeignZones, nNSTR), dtype=float)
        attraction = np.zeros((nNUTS3 + nForeignZones, nNSTR), dtype=float)

        for nstr in range(nNSTR):
            production[:nNUTS3, nstr] = (
                coeffProd['INDUSTRIE'][nstr] * np.array(segs['INDUSTRIE']) +
                coeffProd['DETAIL'   ][nstr] * np.array(segs['DETAIL'   ]) +
                coeffProd['LANDBOUW' ][nstr] * np.array(segs['LANDBOUW' ]) +
                coeffProd['DIENSTEN' ][nstr] * np.array(segs['DIENSTEN' ]) +
                coeffProd['OVERHEID' ][nstr] * np.array(segs['OVERHEID' ]) +
                coeffProd['OVERIG'   ][nstr] * np.array(segs['OVERIG'   ]) +
                coeffProd['DC_OPP'   ][nstr] * np.array(surfaceDC[0]))

            attraction[:nNUTS3, nstr] = (
                coeffAttr['INDUSTRIE'][nstr] * np.array(segs['INDUSTRIE']) +
                coeffAttr['DETAIL'   ][nstr] * np.array(segs['DETAIL'   ]) +
                coeffAttr['LANDBOUW' ][nstr] * np.array(segs['LANDBOUW' ]) +
                coeffAttr['DIENSTEN' ][nstr] * np.array(segs['DIENSTEN' ]) +
                coeffAttr['OVERHEID' ][nstr] * np.array(segs['OVERHEID' ]) +
                coeffAttr['OVERIG'   ][nstr] * np.array(segs['OVERIG'   ]) +
                coeffAttr['DC_OPP'   ][nstr] * np.array(surfaceDC[0]))

            # 3 international zones
            i = nNUTS3
            for country in ['BE', 'DE', 'FR']:

                if varDict['NUTSLEVEL_INPUT'] == 2:
                    production[i, nstr] = np.sum(comMatNUTS2.loc[
                        comMatNUTS2['ORIG'] == country,
                        'NSTR' + str(nstr)])
                    attraction[i, nstr] = np.sum(comMatNUTS2.loc[
                        comMatNUTS2['DEST'] == country, 'NSTR' + str(nstr)])

                elif varDict['NUTSLEVEL_INPUT'] == 3:
                    production[i, nstr] = np.sum(comMatNUTS3.loc[
                        comMatNUTS3['ORIG'] == country, 'NSTR' + str(nstr)])
                    attraction[i, nstr] = np.sum(comMatNUTS3.loc[
                        comMatNUTS3['DEST'] == country, 'NSTR' + str(nstr)])

                i += 1

        production = pd.DataFrame(
            production,
            index=codesNUTS3,
            columns=['NSTR' + str(nstr) for nstr in range(nNSTR)])
        attraction = pd.DataFrame(
            attraction,
            index=codesNUTS3,
            columns=['NSTR' + str(nstr) for nstr in range(nNSTR)])

        # --------- Create initial matrix for the distribution procedure ------

        print('Creating initial matrices per NSTR...')
        log_file.write('Creating initial matrices per NSTR...' + '\n')

        # Initialize list with OD-arrays for tonnes between NUTS3-regions
        tonnes = [
            np.zeros((nNUTS3 + nForeignZones, nNUTS3 + nForeignZones))
            for nstr in range(nNSTR)]

        # Initial matrix with NUTS2-input
        if varDict['NUTSLEVEL_INPUT'] == 2:

            # Coupling from NUTS3 (index) to NUTS2
            NUTS3toNUTS2 = ['' for i in range(nNUTS3 + nForeignZones)]

            for i in range(nNUTS3):
                NUTS3toNUTS2[i] = codesNUTS3[i][:4]

            for i in range(nForeignZones):
                NUTS3toNUTS2[nNUTS3 + i] = ['BE', 'DE', 'FR'][i]

            NUTS3toNUTS2 = np.array(NUTS3toNUTS2, dtype=str)

            # Get NUTS2-matrix as list with OD-DataFrame per NSTR
            comMatNUTS2byNSTR = [
                pd.pivot_table(
                    comMatNUTS2,
                    values=['NSTR' + str(nstr)],
                    index=['ORIG'],
                    columns=['DEST']).fillna(0)
                for nstr in range(nNSTR)]

            for nstr in range(nNSTR):
                comMatNUTS2byNSTR[nstr].columns = [
                    comMatNUTS2byNSTR[nstr].columns[i][1]
                    for i in range(len(comMatNUTS2byNSTR[nstr].columns))]

            for nstr in range(nNSTR):

                # For each NUTS3 i-j the tonnes of the overarching NUTS2
                for i in range(nNUTS3 + nForeignZones):
                    origNUTS3 = i
                    destsNUTS3 = np.arange(nNUTS3 + nForeignZones)
                    origNUTS2 = NUTS3toNUTS2[origNUTS3]
                    destsNUTS2 = NUTS3toNUTS2[destsNUTS3]

                    tonnes[nstr][origNUTS3, destsNUTS3] = np.array(
                        comMatNUTS2byNSTR[nstr].loc[origNUTS2, destsNUTS2])

                # Per NUTS3-region the production of all NUTS3-regions
                # in the same NUTS2-region
                productionTotal = np.zeros(nNUTS3 + nForeignZones)
                for i in range(nNUTS3 + nForeignZones):
                    origNUTS2 = NUTS3toNUTS2[i]
                    NUTS3inSameNUTS2 = codesNUTS3[
                        np.where(NUTS3toNUTS2 == origNUTS2)[0]]
                    productionTotal[i] = np.sum(
                        production.loc[NUTS3inSameNUTS2, 'NSTR' + str(nstr)])

                # Per NUTS3-region the attraction of all NUTS3-regions
                # in the same NUTS2-region
                attractionTotal = np.zeros(nNUTS3 + nForeignZones)
                for i in range(nNUTS3 + nForeignZones):
                    destNUTS2 = NUTS3toNUTS2[i]
                    NUTS3inSameNUTS2 = codesNUTS3[
                        np.where(NUTS3toNUTS2 == destNUTS2)[0]]
                    attractionTotal[i] = np.sum(
                        attraction.loc[NUTS3inSameNUTS2, 'NSTR' + str(nstr)])

                # Create the initial matrix at the level of NUTS3-regions
                for i in range(nNUTS3 + 3):
                    if productionTotal[i] > 0:
                        tonnes[nstr][i, :] *= production.iat[i, nstr] / productionTotal[i]
                for j in range(nNUTS3 + 3):
                    if attractionTotal[j] > 0:
                        tonnes[nstr][:, j] *= attraction.iat[i, nstr] / attractionTotal[j]

        # Initial matrix with NUTS3-input
        if varDict['NUTSLEVEL_INPUT'] == 3:

            # Get NUTS3-matrix as list with OD-DataFrame per NSTR
            comMatNUTS3byNSTR = [
                pd.pivot_table(
                    comMatNUTS3,
                    values=['NSTR' + str(nstr)],
                    index=['ORIG'],
                    columns=['DEST']).fillna(0)
                for nstr in range(nNSTR)]
            for nstr in range(nNSTR):
                comMatNUTS3byNSTR[nstr].columns = [
                    comMatNUTS3byNSTR[nstr].columns[i][1]
                    for i in range(len(comMatNUTS3byNSTR[nstr].columns))]

            NUTS3inIndex = set(list(comMatNUTS3byNSTR[0].index))
            NUTS3inHeader = set(list(comMatNUTS3byNSTR[0].columns))

            for nstr in range(nNSTR):
                for i in range(nNUTS3 + nForeignZones):

                    if codesNUTS3[i] in NUTS3inIndex:
                        for j in range(nNUTS3 + nForeignZones):

                            if codesNUTS3[j] in NUTS3inHeader:
                                tonnes[nstr][i, j] = (
                                    comMatNUTS3byNSTR[nstr].at[
                                        codesNUTS3[i],
                                        codesNUTS3[j]])
                            else:
                                tonnes[nstr][i, j] = 0

                    else:
                        for j in range(nNUTS3 + nForeignZones):
                            tonnes[nstr][i, j] = 0

                        if nstr == 0:
                            message = (
                                'Warning! NUTS3-region ' +
                                codesNUTS3[i] +
                                ' was not found in the commodity matrix.' +
                                ' Defaulting to 0.0 tonnes for ' +
                                'this NUTS3-region.')
                            print(message)
                            log_file.write(message + '\n')

        # ------------------------ FRATAR distribution ------------------------

        tolerance = 0.005
        maxIter = 50

        print('FRATAR distribution...')
        log_file.write('FRATAR distribution...' + '\n')

        for nstr in range(nNSTR):
            itern = 0
            conv = tolerance + 100
            convPrevIteration = -99999

            while (itern < maxIter) and (conv > tolerance):
                itern += 1
                maxColScaleFac = 0
                totalRows = np.sum(tonnes[nstr], axis=0)

                # Scale to row totals
                for j in range(nNUTS3 + nForeignZones):
                    total = totalRows[j]

                    if total > 0:
                        scaleFacCol = attraction.iat[j, nstr] / total

                        if abs(scaleFacCol) > abs(maxColScaleFac):
                            maxColScaleFac = scaleFacCol

                        tonnes[nstr][:, j] *= scaleFacCol

                maxRowScaleFac = 0
                totalCols = np.sum(tonnes[nstr], axis=1)

                # Scale to column totals
                for i in range(nNUTS3 + nForeignZones):
                    total = totalCols[i]

                    if total > 0:
                        scaleFacRow = production.iat[i, nstr] / total

                        if abs(scaleFacRow) > abs(maxRowScaleFac):
                            maxRowScaleFac = scaleFacRow

                        tonnes[nstr][i, :] *= scaleFacRow

                # Calculate convergence to check if we should continue scaling
                conv = round(max(
                    abs(maxColScaleFac - 1),
                    abs(maxRowScaleFac - 1)), 5)

                # Stop if convergence is not improved anymore
                if conv == convPrevIteration:
                    break
                convPrevIteration = conv

            message = (
                '\tNSTR' + str(nstr) +
                ' (' + 'Iteration ' + str(itern) +
                ' / Convergence ' + str(round(conv, 4)) + ')')
            print(message)
            log_file.write(message + '\n')

        # -------------------- Exporting commodity matrix ---------------------

        print('Exporting commodity matrix...')
        log_file.write('Exporting commodity matrix...' + '\n')

        labelsNUTS3 = list(production.index)
        nZones = nNUTS3 + nForeignZones

        # Put in long-matrix-format (enumated)
        outputMat = np.zeros((nZones * nZones * nNSTR, 4), dtype=object)
        for nstr in range(nNSTR):
            for orig in range(nZones):
                indices = (
                    nstr * nZones * nZones +
                    orig * nZones +
                    np.arange(nZones))
                outputMat[indices, 0] = labelsNUTS3[orig]
                outputMat[indices, 1] = labelsNUTS3
                outputMat[indices, 2] = nstr
                outputMat[indices, 3] = tonnes[nstr][orig,:]

        # Formatting
        outputMat = pd.DataFrame(
            outputMat,
            columns=['ORIG', 'DEST', 'NSTR', 'TonnesYear'])
        outputMat['NSTR'] = outputMat['NSTR'].astype(int)
        outputMat['TonnesYear'] = outputMat['TonnesYear'].astype(float)
        outputMat['TonnesYear'] = np.round(outputMat['TonnesYear'], 3)

        # Exporting to CSV
        outputMat.to_csv(
            varDict['OUTPUTFOLDER'] + 'CommodityMatrixNUTS3.csv',
            sep=',',
            index=False)

        # ------------------------- End of module -----------------------------

        totaltime = round(time.time() - start_time, 2)
        print('Finished. Run time: ' + str(totaltime) + ' seconds')
        log_file.write(
            "Total runtime: %s seconds\n" % (totaltime))
        log_file.write(
            "End simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")
        log_file.close()

        if root != '':
            root.update_statusbar("Spatial Interaction Freight: Done")
            root.progressBar['value'] = 100

            # 0 means no errors in execution
            root.returnInfo = [0, [0, 0]]

            return root.returnInfo

        else:
            # 0 means no errors in execution
            return [0, [0, 0]]

    except Exception:
        import sys
        log_file.write(str(sys.exc_info()[0]) + "\n")
        import traceback
        log_file.write(str(traceback.format_exc()) + "\n")
        log_file.write("Execution failed!")
        log_file.close()
        print(sys.exc_info()[0])
        print(traceback.format_exc())
        print("Execution failed!")

        if root != '':
            # Use this information to display as error message in GUI
            root.returnInfo = [1, [sys.exc_info()[0], traceback.format_exc()]]

            if __name__ == '__main__':
                root.update_statusbar(
                    "Spatial Interaction Freight: Execution failed!")
                errorMessage = (
                    'Execution failed!\n\n' +
                    str(root.returnInfo[1][0]) +
                    '\n\n' +
                    str(root.returnInfo[1][1]))
                root.error_screen(text=errorMessage, size=[900, 350])                

            else:
                return root.returnInfo

        else:
            # Use this information to display as error message in GUI
            return [1, [sys.exc_info()[0], traceback.format_exc()]]


#%% For if you want to run the module from this script itself (instead of calling it from the GUI module)

if __name__ == '__main__':

    varDict = {}

    varDict['INPUTFOLDER']	 = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/data/2016/'
    varDict['OUTPUTFOLDER'] = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/output/RunREF2016/'
    varDict['PARAMFOLDER']	 = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/parameters/'
    varDict['DIMFOLDER']	 = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/dimensions/'

    varDict['SKIMTIME']     = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/data/LOS/2016/skimTijd_REF.mtx'
    varDict['SKIMDISTANCE'] = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/data/LOS/2016/skimAfstand_REF.mtx'
    varDict['LINKS'] = varDict['INPUTFOLDER'] + 'links_v5.shp'
    varDict['NODES'] = varDict['INPUTFOLDER'] + 'nodes_v5.shp'
    varDict['ZONES'] = varDict['INPUTFOLDER'] + 'Zones_v5.shp'
    varDict['SEGS']  = varDict['INPUTFOLDER'] + 'SEGS2016_verrijkt.csv'
    varDict['COMMODITYMATRIX']    = varDict['INPUTFOLDER'] + 'CommodityMatrixNUTS3_2016.csv'
    varDict['PARCELNODES']        = varDict['INPUTFOLDER'] + 'parcelNodes_v2.shp'
    varDict['DISTRIBUTIECENTRA']  = varDict['INPUTFOLDER'] + 'distributieCentra.csv'
    varDict['DC_OPP_NUTS3']       = varDict['INPUTFOLDER'] + 'DC_OPP_NUTS3.csv'
    varDict['NSTR_TO_LS']         = varDict['INPUTFOLDER'] + 'nstrToLogisticSegment.csv'
    varDict['MAKE_DISTRIBUTION']  = varDict['INPUTFOLDER'] + 'MakeDistribution.csv'
    varDict['USE_DISTRIBUTION']   = varDict['INPUTFOLDER'] + 'UseDistribution.csv'
    varDict['SUP_COORDINATES_ID'] = varDict['INPUTFOLDER'] + 'SupCoordinatesID.csv'
    varDict['CORRECTIONS_TONNES'] = varDict['INPUTFOLDER'] + 'CorrectionsTonnes2016.csv'
    varDict['DEPTIME_FREIGHT'] = varDict['INPUTFOLDER'] + 'departureTimePDF.csv'
    varDict['DEPTIME_PARCELS'] = varDict['INPUTFOLDER'] + 'departureTimeParcelsCDF.csv'
    varDict['FIRMSIZE']    = varDict['INPUTFOLDER'] + 'FirmSizeDistributionPerSector_6cat.csv'
    varDict['SBI_TO_SEGS'] = varDict['INPUTFOLDER'] + 'Koppeltabel_sectoren_SBI_SEGs.csv'

    varDict['COST_VEHTYPE']        = varDict['PARAMFOLDER'] + 'Cost_VehType_2016.csv'
    varDict['COST_SOURCING']       = varDict['PARAMFOLDER'] + 'Cost_Sourcing_2016.csv'
    varDict['MRDH_TO_NUTS3']       = varDict['PARAMFOLDER'] + 'MRDHtoNUTS32013.csv'
    varDict['MRDH_TO_COROP']       = varDict['PARAMFOLDER'] + 'MRDHtoCOROP.csv'
    varDict['NUTS3_TO_MRDH']       = varDict['PARAMFOLDER'] + 'NUTS32013toMRDH.csv'
    varDict['VEHICLE_CAPACITY']    = varDict['PARAMFOLDER'] + 'CarryingCapacity.csv'
    varDict['LOGISTIC_FLOWTYPES']  = varDict['PARAMFOLDER'] + 'LogFlowtype_Shares.csv'
    varDict['SERVICE_DISTANCEDECAY'] = varDict['PARAMFOLDER'] + 'Params_DistanceDecay_SERVICE.csv'
    varDict['SERVICE_PA']            = varDict['PARAMFOLDER'] + 'Params_PA_SERVICE.csv'
    varDict['PARAMS_TOD']     = varDict['PARAMFOLDER'] + 'Params_TOD.csv'
    varDict['PARAMS_SSVT']     = varDict['PARAMFOLDER'] + 'Params_ShipSize_VehType.csv'
    varDict['PARAMS_ET_FIRST'] = varDict['PARAMFOLDER'] + 'Params_EndTourFirst.csv'
    varDict['PARAMS_ET_LATER'] = varDict['PARAMFOLDER'] + 'Params_EndTourLater.csv'
    varDict['PARAMS_SIF_PROD'] = varDict['PARAMFOLDER'] + 'Params_PA_PROD.csv'
    varDict['PARAMS_SIF_ATTR'] = varDict['PARAMFOLDER'] + 'Params_PA_ATTR.csv'
    varDict['PARAMS_ECOMMERCE']    = varDict['PARAMFOLDER'] + 'Params_EcommerceDemand.csv'

    varDict['EMISSIONFACS_BUITENWEG_LEEG'] = varDict['INPUTFOLDER'] + 'EmissieFactoren_BUITENWEG_LEEG.csv'
    varDict['EMISSIONFACS_BUITENWEG_VOL' ] = varDict['INPUTFOLDER'] + 'EmissieFactoren_BUITENWEG_VOL.csv'
    varDict['EMISSIONFACS_SNELWEG_LEEG'] = varDict['INPUTFOLDER'] + 'EmissieFactoren_SNELWEG_LEEG.csv'
    varDict['EMISSIONFACS_SNELWEG_VOL' ] = varDict['INPUTFOLDER'] + 'EmissieFactoren_SNELWEG_VOL.csv'
    varDict['EMISSIONFACS_STAD_LEEG'] = varDict['INPUTFOLDER'] + 'EmissieFactoren_STAD_LEEG.csv'
    varDict['EMISSIONFACS_STAD_VOL' ] = varDict['INPUTFOLDER'] + 'EmissieFactoren_STAD_VOL.csv'

    varDict['ZEZ_CONSOLIDATION'] = varDict['INPUTFOLDER'] + 'ConsolidationPotential.csv'
    varDict['ZEZ_SCENARIO']      = varDict['INPUTFOLDER'] + 'ZEZscenario.csv'

    varDict['YEARFACTOR'] = 209

    varDict['NUTSLEVEL_INPUT'] = 3

    varDict['PARCELS_PER_HH']	 = 0.112
    varDict['PARCELS_PER_EMPL'] = 0.041
    varDict['PARCELS_MAXLOAD']	 = 180
    varDict['PARCELS_DROPTIME'] = 120
    varDict['PARCELS_SUCCESS_B2C']   = 0.75
    varDict['PARCELS_SUCCESS_B2B']   = 0.95
    varDict['PARCELS_GROWTHFREIGHT'] = 1.0

    varDict['MICROHUBS']    = varDict['INPUTFOLDER'] + 'Microhubs.csv'
    varDict['VEHICLETYPES'] = varDict['INPUTFOLDER'] + 'Microhubs_vehicleTypes.csv'

    varDict['SHIPMENTS_REF'] = ""
    varDict['FIRMS_REF'] = ""
    varDict['SELECTED_LINKS'] = ""
    varDict['N_CPU'] = ""

    varDict['FAC_LS0'] = ""
    varDict['FAC_LS1'] = ""
    varDict['FAC_LS2'] = ""
    varDict['FAC_LS3'] = ""
    varDict['FAC_LS4'] = ""
    varDict['FAC_LS5'] = ""
    varDict['FAC_LS6'] = ""
    varDict['FAC_LS7'] = ""
    varDict['NEAREST_DC'] = ""

    varDict['CROWDSHIPPING']    = False
    varDict['CRW_PARCELSHARE']  = ""
    varDict['CRW_MODEPARAMS']   = ""
    varDict['CRW_PDEMAND_CAR']  = ""
    varDict['CRW_PDEMAND_BIKE'] = ""
    
    varDict['SHIFT_FREIGHT_TO_COMB1'] = ""
    
    varDict['IMPEDANCE_SPEED'] = 'V_FR_OS'
    
    varDict['LABEL'] = 'REF'
    
    # Run the module
    main(varDict)
