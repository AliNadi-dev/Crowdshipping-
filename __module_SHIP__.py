# -*- coding: utf-8 -*-
"""
Created on Thu Oct 24 16:05:56 2019

@author: STH
"""

import numpy as np
import pandas as pd
import time
import datetime
import shapefile as shp
from numba import njit
from __functions__ import read_mtx, read_shape

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
        self.root.title("Progress Shipment Synthesizer")
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


@njit
def draw_choice(cumProbs):
    '''
    Draw one choice from a list of cumulative probabilities.
    '''
    nAlt = len(cumProbs)

    rand = np.random.rand()
    for alt in range(nAlt):
        if cumProbs[alt] >= rand:
            return alt

    raise Exception(
        '\nError in function "draw_choice", random draw ' +
        'was outside range of cumulative probability distribution.')


def actually_run_module(args):

    try:

        root = args[0]
        varDict = args[1]

        start_time = time.time()

        log_file = open(
            varDict['OUTPUTFOLDER'] + "Logfile_ShipmentSynthesizer.log",
            "w")
        log_file.write(
            "Start simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")

        chooseNearestDC = (varDict['NEAREST_DC'].upper() == 'TRUE')

        # Create shipments to/from external areas or not
        doExtArea = True

        # ----------------------- Import data --------------------------------

        print("Importing and preparing data...")
        log_file.write("Importing and preparing data...\n")

        if root != '':
            root.update_statusbar(
                "Shipment Synthesizer: Importing and preparing data")
            root.progressBar['value'] = 0

        dimNSTR = pd.read_csv(
            varDict['DIMFOLDER'] + 'nstr.txt',
            sep='\t')
        dimLS = pd.read_csv(
            varDict['DIMFOLDER'] + 'logistic_segment.txt',
            sep='\t')
        dimShipSize = pd.read_csv(
            varDict['DIMFOLDER'] + 'shipment_size.txt',
            sep='\t')
        dimVT = pd.read_csv(
            varDict['DIMFOLDER'] + 'vehicle_type.txt',
            sep='\t')
        dimFT = pd.read_csv(
            varDict['DIMFOLDER'] + 'flow_type.txt',
            sep='\t')

        nNSTR = len(dimNSTR) - 1
        nLS = len(dimLS) - 1
        nShipSize = len(dimShipSize)
        nVT = np.sum(dimVT['IsRefTypeFreight'] == 1)

        nFlowTypesInternal = np.sum(dimFT['IsExternal'] == 0)
        nFlowTypesExternal = np.sum(dimFT['IsExternal'] == 1)
        
        absoluteShipmentSizes = np.array(dimShipSize['Median'])

        # Distance decay parameters
        alpha = -6.172
        beta =  2.180

        # Factors for increasing or decreasing total flow of certain
        # logistics segments
        facLS = [1.0 for ls in range(nLS)]
        for ls in range(nLS):
            if varDict[f'FAC_LS{ls}'] != '':
                facLS[ls] = float(varDict[f'FAC_LS{ls}'])

        # Which NSTR belongs to which Logistic Segments
        nstrToLS = np.array(pd.read_csv(
            varDict['NSTR_TO_LS'],
            header=None), dtype=float)
        for nstr in range(nNSTR):
            nstrToLS[nstr, :] = (
                nstrToLS[nstr, :] / np.sum(nstrToLS[nstr, :]))

        # Which Logistic Segment belongs to which NSTRs
        lsToNstr = np.array(pd.read_csv(
            varDict['NSTR_TO_LS'],
            header=None), dtype=float)
        for ls in range(nLS):
            lsToNstr[:, ls] = (
                lsToNstr[:, ls] / np.sum(lsToNstr[:, ls]))

        if root != '':
            root.progressBar['value'] = 0.2

        # Import make/use distribution tables (by NSTR and industry sector)
        makeDistribution = np.array(pd.read_csv(varDict['MAKE_DISTRIBUTION']))
        useDistribution = np.array(pd.read_csv(varDict['USE_DISTRIBUTION']))

        if root != '':
            root.progressBar['value'] = 0.4

        # Import external zones demand and coordinates
        if varDict['SHIPMENTS_REF'] == "":
            superComMatNSTR = pd.read_csv(
                varDict['OUTPUTFOLDER'] + 'CommodityMatrixNUTS3.csv',
                sep=',')
            superComMatNSTR['WeightDay'] = (
                superComMatNSTR['TonnesYear'] / varDict['YEARFACTOR'])
            superComMatNSTR = np.array(
                superComMatNSTR[['ORIG', 'DEST', 'NSTR', 'WeightDay']],
                dtype=object)

        # Locations of the external zones
        superCoordinates = pd.read_csv(varDict['SUP_COORDINATES_ID'])
        superZoneX = np.array(superCoordinates['Xcoor'])
        superZoneY = np.array(superCoordinates['Ycoor'])
        nSuperZones = len(superCoordinates)

        NUTS3toAREANR = pd.read_csv(varDict['NUTS3_TO_MRDH'], sep=',')
        NUTS3toAREANR = dict(
            (NUTS3toAREANR.at[i, 'NUTS_ID'], NUTS3toAREANR.at[i, 'AREANR'])
            for i in NUTS3toAREANR.index)
        AREANRtoNUTS3 = {}
        for nuts3, areanr in NUTS3toAREANR.items():
            if areanr in AREANRtoNUTS3.keys():
                AREANRtoNUTS3[areanr].append(nuts3)
            else:
                AREANRtoNUTS3[areanr] = [nuts3]

        # Convert demand from NSTR to logistic segments
        if varDict['SHIPMENTS_REF'] == "":
            nRows = (nSuperZones + 1) * (nSuperZones + 1) * nLS

            superComMat = np.zeros((nRows, 4))
            superComMat[:, 0] = (
                np.floor(np.arange(nRows) / (nSuperZones + 1) / nLS))
            superComMat[:, 1] = (
                np.floor(np.arange(nRows) / nLS) -
                superComMat[:, 0] * (nSuperZones + 1))

            for ls in range(nLS):
                superComMat[
                    np.arange(ls, nRows, nLS), 2] = ls

            zonesWithKnownNUTS3 = set(list(AREANRtoNUTS3.keys()))

            for i in range(nSuperZones + 1):
                if (99999900 + i) in zonesWithKnownNUTS3:

                    for j in range(nSuperZones + 1):
                        if (99999900 + j) in zonesWithKnownNUTS3:

                            origNUTS3 = AREANRtoNUTS3[99999900 + i]
                            destNUTS3 = AREANRtoNUTS3[99999900 + j]

                            weightDayNSTR = [0.0 for nstr in range(nNSTR)]

                            for z in range(len(superComMatNSTR)):
                                if superComMatNSTR[z, 0] in origNUTS3:
                                    if superComMatNSTR[z, 1] in destNUTS3:
                                        tmpNSTR = superComMatNSTR[z, 2]
                                        tmpWeight = superComMatNSTR[z, 3]
                                        weightDayNSTR[tmpNSTR] += tmpWeight

                            for nstr in range(nNSTR):

                                if weightDayNSTR[nstr] > 0:

                                    for ls in range(nLS):
                                        row = (
                                            i * (nSuperZones + 1) * nLS +
                                            j * nLS + ls)
                                        superComMat[row, 3] += (
                                            nstrToLS[nstr, ls] *
                                            float(weightDayNSTR[nstr]))

                                        # Apply growth to parcel market
                                        if ls == 6:
                                            growth = float(varDict[
                                                'PARCELS_GROWTHFREIGHT'])
                                            superComMat[row, 3] *= growth

                                        # Apply increase/decrease factor
                                        # for logistics segment
                                        superComMat[row, 3] *= facLS[ls]

            superComMat = pd.DataFrame(
                superComMat,
                columns=['From', 'To', 'LS', 'WeightDay'])
            superComMat.loc[
                (superComMat['From'] != 0) & (superComMat['To'] != 0),
                'WeightDay'] = 0

        if root != '':
            root.progressBar['value'] = 1

        # Socio-economic data of zones
        segs = pd.read_csv(varDict['SEGS'])
        segs.index = segs['zone']

        # Import internal zones data
        zonesShape = read_shape(varDict['ZONES'])
        zonesShape = zonesShape.sort_values('AREANR')
        zonesShape.index = zonesShape['AREANR']
        zoneID = np.array(zonesShape['AREANR'])
        zoneX = np.array(zonesShape['X'])
        zoneY = np.array(zonesShape['Y'])
        zoneLognode = np.array(zonesShape['LOGNODE'])
        zoneSurface = np.array(zonesShape['area'])
        nInternalZones = len(zonesShape)
        zoneDict = dict(np.transpose(np.vstack((
            np.arange(nInternalZones),
            zoneID))))
        for i in range(nSuperZones):
            zoneDict[nInternalZones + i] = superCoordinates['AREANR'][i]
        invZoneDict = dict((v, k) for k, v in zoneDict.items())
        zoneID = np.arange(nInternalZones)

        # Calculate urban density of zones
        urbanDensityCat = {}
        for i in range(nInternalZones):
            tmpNumHouses = segs.at[zoneDict[i], '1: woningen']
            tmpNumJobs = segs.at[zoneDict[i], '9: arbeidspl_totaal']
            urbanDensity = (
                (tmpNumHouses + tmpNumJobs) /
                (zonesShape.at[zoneDict[i], 'area'] / 100000))

            if urbanDensity < 500:
                urbanDensityCat[zoneDict[i]] = 1
            elif urbanDensity < 1000:
                urbanDensityCat[zoneDict[i]] = 2
            elif urbanDensity < 1500:
                urbanDensityCat[zoneDict[i]] = 3
            elif urbanDensity < 2500:
                urbanDensityCat[zoneDict[i]] = 4
            else:
                urbanDensityCat[zoneDict[i]] = 5

        for i in range(nSuperZones):
            urbanDensityCat[99999901 + i] = 1

        # Is a zone a DC, a TT or Producer/Consumer zone
        isDC = {}
        isTT = {}
        isPC = {}
        for i in zonesShape.index:
            isDC[i] = int(zonesShape.at[i, 'LOGNODE'] == 2)
            isTT[i] = int(zonesShape.at[i, 'LOGNODE'] == 1)
            isPC[i] = int(zonesShape.at[i, 'LOGNODE'] == 0)
        for i in range(nSuperZones):
            isDC[99999901 + i] = 0
            isTT[99999901 + i] = 0
            isPC[99999901 + i] = 0

        if root != '':
            root.progressBar['value'] = 1.2

        # Import firm data
        if varDict['SHIPMENTS_REF'] == "":
            if varDict['FIRMS_REF'] == "":
                firms = pd.read_csv(varDict['OUTPUTFOLDER'] + 'Firms.csv')
            else:
                firms = pd.read_csv(varDict['FIRMS_REF'])
            firmID = np.array(firms['FIRM_ID'])
            firmZone = np.array([
                invZoneDict[firms['MRDH_ZONE'][i]] for i in firms.index])
            firmSize = np.array(firms['EMPL'])
            firmX = np.array(firms['X'])
            firmY = np.array(firms['Y'])

            sectorDict = {
                'LANDBOUW': 1,
                'INDUSTRIE': 2,
                'DETAIL': 3,
                'DIENSTEN':4,
                'OVERHEID': 5,
                'OVERIG': 6}
            firmSector = np.array([
                sectorDict[firms['SECTOR'][i]] for i in firms.index])

            nFirms = len(firms)

        if root != '':
            root.progressBar['value'] = 1.5

        # Import logistic nodes data
        logNodes = pd.read_csv(varDict['DISTRIBUTIECENTRA'])
        logNodes = logNodes[~pd.isna(logNodes['AREANR'])]
        logNodes['AREANR'] = [invZoneDict[x] for x in logNodes['AREANR']]
        logNodesAREANR = np.array(logNodes['AREANR'], dtype=int)
        logNodesX = np.array(logNodes['Xcoor'])
        logNodesY = np.array(logNodes['Ycoor'])

        # List of zone numbers Transshipment Terminals and Logistic Nodes
        ttZones = np.where(zoneLognode==1)[0]
        dcZones = np.array(logNodes['AREANR'])

        # Flowtype distribution (10 NSTRs and 12 flowtypes)
        ftShares = np.array(pd.read_csv(
            varDict['LOGISTIC_FLOWTYPES'],
            index_col=0))

        # Corrections
        if varDict['CORRECTIONS_TONNES'] != '':
            corrections = pd.read_csv(varDict['CORRECTIONS_TONNES'], sep=',')
            nCorrections = len(corrections)

        if root != '':
            root.progressBar['value'] = 1.5

        # Skim with travel times and distances
        skimTravTime = read_mtx(varDict['SKIMTIME'])
        skimDistance = read_mtx(varDict['SKIMDISTANCE'])
        nZones = int(len(skimTravTime)**0.5)

        skimTravTime[skimTravTime < 0] = 0
        skimDistance[skimDistance < 0] = 0

        # For zero times and distances assume half the value to
        # the nearest (non-zero) zone
        # (otherwise we get problem in the distance decay function)
        for orig in range(nZones):
            whereZero = np.where(
                skimTravTime[orig * nZones + np.arange(nZones)] == 0)[0]
            whereNonZero = np.where(
                skimTravTime[orig * nZones + np.arange(nZones)] != 0)[0]
            if len(whereZero) > 0:
                skimTravTime[orig * nZones + whereZero] = (
                    0.5 * np.min(skimTravTime[orig * nZones + whereNonZero]))

            whereZero = np.where(
                skimDistance[orig * nZones + np.arange(nZones)] == 0)[0]
            whereNonZero = np.where(
                skimDistance[orig * nZones + np.arange(nZones)] != 0)[0]
            if len(whereZero) > 0:
                skimDistance[orig * nZones + whereZero] = (
                    0.5 * np.min(skimDistance[orig * nZones + whereNonZero]))

        if root != '':
            root.progressBar['value'] = 2.5

        # Cost parameters by vehicle type with size (small/medium/large)
        costParams = pd.read_csv(varDict['COST_VEHTYPE'], index_col=0)
        costPerKm = np.array(costParams['CostPerKm'])
        costPerHour = np.array(costParams['CostPerH'])

        # Cost parameters generic for sourcing
        # (vehicle type is now known yet then)
        costParamsSourcing = pd.read_csv(varDict['COST_SOURCING'])
        costPerKmSourcing = costParamsSourcing['CostPerKm'][0]
        costPerHourSourcing = costParamsSourcing['CostPerHour'][0]

        # Estimated parameters MNL for combined shipment size and vehicle type
        paramsShipSizeVehType = pd.read_csv(
            varDict['PARAMS_SSVT'],
            index_col=0)

        def try_float(number, filename=''):
            try:
                if '_' in str(number):
                    number = str(number)
                else:
                    number = float(number)
            except ValueError:
                message = "Could not convert '" + str(number) + "' to float.\n"
                if filename != '':
                    message = (
                        message +
                        "This value was found in: " + filename + ".")
                raise ValueError(message)
            return number

        # Estimated parameters MNL for delivery time
        paramsTimeOfDay = pd.read_csv(varDict['PARAMS_TOD'], index_col=0)
        paramsTimeOfDay = [
            dict(zip(
                paramsTimeOfDay.index,
                [try_float(x, varDict['PARAMS_TOD'])
                 for x in paramsTimeOfDay.loc[:, str(ls + 1)]]))
            for ls in range(nLS)]
            
        nTimeIntervals = len([
            x for x in paramsTimeOfDay[0].keys()
            if x.split('_')[0] == 'Interval'])

        timeIntervals = []
        timeIntervalsDur = []
        nTimeIntervalsLS = [0 for ls in range(nLS)]
        for ls in range(nLS):
            tmp = [
                paramsTimeOfDay[ls][f'Interval_{t+1}'].split('_')
                for t in range(nTimeIntervals)]
            timeIntervalsDur.append([])
            for t in range(nTimeIntervals):
                if len(tmp[t]) > 1:
                    tmp[t] = [int(tmp[t][i]) for i in range(len(tmp[t]))]
                    timeIntervalsDur[ls].append(int(tmp[t][1] - tmp[t][0]))
                    nTimeIntervalsLS[ls] += 1
            timeIntervals.append(tmp)

        # Which NSTR belongs to which goods type used in estimation of MNL
        dictNSTR = {
            0: 'climate controlled',
            1: 'climate controlled',
            2: 'heavy bulk',
            3: 'heavy bulk',
            4: 'heavy bulk',
            5: 'heavy bulk',
            6: 'heavy bulk',
            7: 'chemicals',
            8: 'chemicals',
            9: 'manufactured'}

        if root != '':
            root.progressBar['value'] = 2.6

        # Consolidation potential per logistic segment (for UCC scenario)
        probConsolidation = np.array(pd.read_csv(
            varDict['ZEZ_CONSOLIDATION'],
            index_col='Segment'))

        # Vehicle/combustion shares (for UCC scenario)
        sharesUCC = pd.read_csv(varDict['ZEZ_SCENARIO'], index_col='Segment')
        vtNamesUCC = [
            'LEVV', 'Moped', 'Van',
            'Truck', 'TractorTrailer',
            'WasteCollection', 'SpecialConstruction']

        # Assume no consolidation potential and vehicle type switch
        # for dangerous goods
        sharesUCC = np.array(sharesUCC)[:-1, :-1]

        # Only vehicle shares (summed up combustion types)
        sharesVehUCC = np.zeros((nLS, len(vtNamesUCC)))
        for ls in range(nLS - 1):
            sharesVehUCC[ls, 0] = np.sum(sharesUCC[ls, 0:5])
            sharesVehUCC[ls, 1] = np.sum(sharesUCC[ls, 5:10])
            sharesVehUCC[ls, 2] = np.sum(sharesUCC[ls, 10:15])
            sharesVehUCC[ls, 3] = np.sum(sharesUCC[ls, 15:20])
            sharesVehUCC[ls, 4] = np.sum(sharesUCC[ls, 20:25])
            sharesVehUCC[ls, 5] = np.sum(sharesUCC[ls, 25:30])
            sharesVehUCC[ls, 6] = np.sum(sharesUCC[ls, 30:35])
            sharesVehUCC[ls, :] = (
                np.cumsum(sharesVehUCC[ls, :]) / np.sum(sharesVehUCC[ls, :]))

        # Couple these vehicle types from ZEZ_SCENARIO to the
        # default TFS vehicle types
        vehUccToVeh = {
            0: 8,
            1: 9,
            2: 7,
            3: 1,
            4: 5,
            5: 6,
            6: 6}

        # Depots for parcel deliveries
        parcelNodes = read_shape(varDict['PARCELNODES'])
        parcelNodes.index = parcelNodes['id'].astype(int)
        parcelNodes = parcelNodes.sort_index()

        # Remove parcel nodes in external zones
        parcelNodes = parcelNodes[parcelNodes['AREANR']<99999900]

        # Convert zone numbers to index in skim
        parcelNodes['AREANR'] = [invZoneDict[x] for x in parcelNodes['AREANR']]
        nParcelNodes = len(parcelNodes)
        parcelNodes.index = np.arange(nParcelNodes)

        # Market shares of the different parcel couriers
        cepShares = pd.read_csv(varDict['CEP_SHARES'], index_col=0)
        cepList = list(cepShares.index)
        nDepots = [np.sum(parcelNodes['CEP'] == str(cep)) for cep in cepList]

        cepShares['ShareInternal'] = cepShares['ShareNL']
        cepShares.iloc[np.array(nDepots) == 1, -1] = 0
        cepSharesTotal = np.array(
            np.cumsum(cepShares['ShareTotal']) /
            np.sum(cepShares['ShareTotal']), dtype=float)
        cepSharesInternal = np.array(
            np.cumsum(cepShares['ShareInternal']) /
            np.sum(cepShares['ShareInternal']), dtype=float)

        cepDepotZones = [
            np.array(
                parcelNodes.loc[parcelNodes['CEP'] == str(cep), 'AREANR'],
                dtype=int)
            for cep in cepList]
        cepDepotShares = [
            np.array(
                parcelNodes.loc[parcelNodes['CEP'] == str(cep), 'Surface'])
            for cep in cepList]
        cepDepotShares = [
            np.array(
                np.cumsum(cepDepotShares[i]) / np.sum(cepDepotShares[i]),
                dtype=float)
            for i in range(len(cepList))]

        cepDepotX = [
            np.array(zonesShape['X'][[zoneDict[x] for x in cepDepotZones[i]]])
            for i in range(len(cepList))]
        cepDepotY = [
            np.array(zonesShape['Y'][[zoneDict[x] for x in cepDepotZones[i]]])
            for i in range(len(cepList))]

        truckCapacities = np.array(pd.read_csv(
            varDict['VEHICLE_CAPACITY'],
            index_col=0))[:, 0] / 1000

        if root != '':
            root.progressBar['value'] = 2.8

        # ----------- Cumulative probability functions for allocation ---------

        if varDict['SHIPMENTS_REF'] == "":
            # Cumulative probability function of firms being receiver or sender
            probReceive = np.zeros((nFirms, nNSTR))
            probSend = np.zeros((nFirms, nNSTR))
            cumProbReceive = np.zeros((nFirms, nNSTR))
            cumProbSend = np.zeros((nFirms, nNSTR))

            # Per goods type, determine probability based on
            # firm size and make/use share
            for nstr in range(nNSTR):
                probReceive[:, nstr] = (
                    firmSize *
                    [useDistribution[nstr, sector - 1]
                        for sector in firmSector])
                probSend[:, nstr] = (
                    firmSize *
                    [makeDistribution[nstr, sector - 1]
                        for sector in firmSector])
                cumProbReceive[:, nstr] = np.cumsum(probReceive[:, nstr])
                cumProbReceive[:, nstr] /= cumProbReceive[-1, nstr]
                cumProbSend[:, nstr] = np.cumsum(probSend[:, nstr])
                cumProbSend[:, nstr] /= cumProbSend[-1, nstr]

            # Cumulative probability function of a shipment being allocated
            # to a particular DC/TT (based on surface)
            probDC = np.array(logNodes['oppervlak'])
            cumProbDC = np.cumsum(probDC)
            cumProbDC = cumProbDC / cumProbDC[-1]

            probTT = zoneSurface[ttZones]
            cumProbTT = np.cumsum(probTT)
            cumProbTT = cumProbTT / cumProbTT[-1]

        if root != '':
            root.progressBar['value'] = 2.9

        # ----------------------- Demand by flowtype -------------------------

        if varDict['SHIPMENTS_REF'] == "":
            # Split demand by internal/export/import and goods type
            demandInternal = np.array(
                superComMat['WeightDay'][:nLS],
                dtype=float)
            demandExport = np.zeros((nSuperZones, nLS), dtype=float)
            demandImport = np.zeros((nSuperZones, nLS), dtype=float)

            for superZone in range(nSuperZones):
                for ls in range(nLS):

                    exportIndex = (
                        (superZone + 1) * (nSuperZones + 1) * nLS +
                        ls)
                    demandExport[superZone][ls] = (
                        superComMat['WeightDay'][exportIndex])

                    importIndex = (
                        (superZone + 1) * nLS +
                        ls)
                    demandImport[superZone][ls] = (
                        superComMat['WeightDay'][importIndex])

            # Then split demand by flowtype
            demandInternalByFT = [None for i in range(nFlowTypesInternal)]
            demandExportByFT = [None for i in range(nFlowTypesExternal)]
            demandImportByFT = [None for i in range(nFlowTypesExternal)]

            for ft in range(nFlowTypesInternal):
                demandInternalByFT[ft] = (
                    demandInternal.copy() * ftShares[ft, :])

            for ft in range(nFlowTypesExternal):
                demandExportByFT[ft] = (
                    demandExport.copy() * ftShares[nFlowTypesInternal + ft, :])
                demandImportByFT[ft] = (
                    demandImport.copy() * ftShares[nFlowTypesInternal + ft, :])

        if root != '':
            root.progressBar['value'] = 3

        # ------------------- Shipment synthesizer procedure ------------------

        if varDict['SHIPMENTS_REF'] == "":

            # Initialize a counter for the procedure
            count = 0

            # Initialize shipment attributes as dictionaries
            fromFirm = {}
            toFirm = {}
            flowType = {}
            goodsType = {}
            logisticSegment = {}
            shipmentSize = {}
            shipmentSizeCat = {}
            vehicleType = {}
            destZone = {}
            origZone = {}
            origX = {}
            origY = {}
            destX = {}
            destY = {}

            print("Synthesizing shipments within study area...")
            log_file.write("Synthesizing shipments within study area...\n")

            percStart = 3
            percEnd = 40

            if root != '':
                root.update_statusbar(
                    "Shipment Synthesizer: " +
                    "Synthesizing shipments within study area")
                root.progressBar['value'] = percStart

            # For progress bar
            totalWeightInternal = np.sum([
                np.sum(demandInternalByFT[ft])
                for ft in range(nFlowTypesInternal)])
            allocatedWeightInternal = 0

            for ls in range(nLS):

                for nstr in range(nNSTR):

                    if lsToNstr[nstr, ls] > 0:

                        print(
                            f"\tFor logistic segment {ls} (NSTR{nstr})",
                            end='\r')
                        log_file.write(
                            f"\tFor logistic segment {ls} (NSTR{nstr})\n")

                        if root != '':
                            root.update_statusbar(
                                "Shipment Synthesizer: " +
                                "Synthesizing shipments within study area " +
                                "(LS " + str(ls) +
                                " and NSTR " + str(nstr) + ")")

                        # Selecting the logit parameters for this NSTR group
                        tmpParams = paramsShipSizeVehType[dictNSTR[nstr]]
                        B_TransportCosts = tmpParams['B_TransportCosts']
                        B_InventoryCosts = tmpParams['B_InventoryCosts']
                        B_FromDC = tmpParams['B_FromDC']
                        B_ToDC = tmpParams['B_ToDC']
                        B_LongHaul_TruckTrailer = (
                            tmpParams['B_LongHaul_TruckTrailer'])
                        B_LongHaul_TractorTrailer = (
                            tmpParams['B_LongHaul_TractorTrailer'])
                        ASC_VT = [
                            tmpParams[f'ASC_VT_{i+1}']
                            for i in range(nVT)]

                        for ft in range(nFlowTypesInternal):

                            allocatedWeight = 0
                            totalWeight = (
                                demandInternalByFT[ft][ls] *
                                lsToNstr[nstr, ls])

                            # While the weight of all synthesized shipment
                            # for this segment so far does not exceed the
                            # total weight for this segment
                            while allocatedWeight < totalWeight:
                                flowType[count] = ft + 1
                                goodsType[count] = nstr
                                logisticSegment[count] = ls

                                # Flows between parcel depots
                                if ls == 6:
                                    cep = draw_choice(cepSharesInternal)
                                    depot = draw_choice(cepDepotShares[cep])
                                    toFirm[count] = 0
                                    destZone[count] = cepDepotZones[cep][depot]
                                    destX[count] = cepDepotX[cep][depot]
                                    destY[count] = cepDepotY[cep][depot]
                                    toDC = 1

                                # Determine receiving firm
                                # for flows to consumer
                                elif (flowType[count] in (1, 3, 6)):
                                    toFirm[count] = draw_choice(
                                        cumProbReceive[:, nstr])
                                    destZone[count] = firmZone[toFirm[count]]
                                    destX[count] = firmX[toFirm[count]]
                                    destY[count] = firmY[toFirm[count]]
                                    toDC = 0
                                # Determine receiving DC
                                # for flows to DC
                                elif (flowType[count] in (2, 5, 8)):
                                    toFirm[count] = draw_choice(cumProbDC)
                                    destZone[count] = dcZones[toFirm[count]]
                                    destX[count] = logNodesX[toFirm[count]]
                                    destY[count] = logNodesY[toFirm[count]]
                                    toDC = 1
                                # Determine receiving Transshipment Terminal
                                # for flows to TT
                                elif (flowType[count] in (4, 7, 9)):
                                    toFirm[count] = ttZones[
                                        draw_choice(cumProbTT)]
                                    destZone[count] = toFirm[count]
                                    destX[count] = zoneX[toFirm[count]]
                                    destY[count] = zoneY[toFirm[count]]
                                    toDC = 0

                                tmpCostTime = (
                                    costPerHourSourcing *
                                    skimTravTime[destZone[count]::nZones] /
                                    3600)
                                tmpCostDist = (
                                    costPerKmSourcing *
                                    skimDistance[destZone[count]::nZones] /
                                    1000)
                                tmpCost = tmpCostTime + tmpCostDist

                                distanceDecay = (
                                    1 / (1 + np.exp(
                                        alpha + beta * np.log(tmpCost))))

                                if (flowType[count] in (1, 2, 4)):
                                    distanceDecay = distanceDecay[firmZone]
                                elif (flowType[count] in (3, 5, 7)):
                                    distanceDecay = distanceDecay[dcZones]
                                elif (flowType[count] in (6, 8, 9)):
                                    distanceDecay = distanceDecay[ttZones]

                                distanceDecay /= np.sum(distanceDecay)

                                if ls == 6:
                                    origDepot = draw_choice(
                                        cepDepotShares[cep])

                                    if origDepot == depot:
                                        if depot == 0:
                                            origDepot = origDepot + 1
                                        elif depot == len(cepDepotShares[cep]) - 1:
                                            origDepot -= 1
                                        else:
                                            origDepot += [-1, 1][np.random.randint(2)]
                                    depot = origDepot

                                    fromFirm[count] = 0
                                    origZone[count] = cepDepotZones[cep][depot]
                                    origX[count] = cepDepotX[cep][depot]
                                    origY[count] = cepDepotY[cep][depot]
                                    fromDC = 1

                                # Determine sending firm
                                # forflows from consumer
                                elif (flowType[count] in (1, 2, 4)):
                                    prob = probSend[:, nstr] * distanceDecay
                                    prob = np.cumsum(prob)
                                    prob /= prob[-1]
                                    fromFirm[count] = draw_choice(prob)
                                    origZone[count] = firmZone[fromFirm[count]]
                                    origX[count] = firmX[fromFirm[count]]
                                    origY[count] = firmY[fromFirm[count]]
                                    fromDC = 0

                                # Determine sending DC
                                # for flows from DC
                                elif (flowType[count] in (3, 5 ,7)):
                                    if chooseNearestDC and flowType[count] == 3:
                                        dists = skimDistance[
                                            logNodesAREANR * nZones +
                                            destZone[count]]
                                        fromFirm[count] = np.argmin(dists)
                                    else:
                                        prob = probDC * distanceDecay
                                        prob = np.cumsum(prob)
                                        prob /= prob[-1]
                                        fromFirm[count] = draw_choice(prob)
                                    origZone[count] = dcZones[fromFirm[count]]
                                    origX[count] = logNodesX[fromFirm[count]]
                                    origY[count] = logNodesY[fromFirm[count]]
                                    fromDC = 1

                                # Determine sending Transshipment Terminal
                                # for flows from TT
                                elif (flowType[count] in (6, 8, 9)):
                                    prob = probTT * distanceDecay
                                    prob = np.cumsum(prob)
                                    prob /= prob[-1]
                                    fromFirm[count] = ttZones[
                                        draw_choice(prob)]
                                    origZone[count] = fromFirm[count]
                                    origX[count] = zoneX[fromFirm[count]]
                                    origY[count] = zoneY[fromFirm[count]]
                                    fromDC = 0

                                # Determine values for attributes in the
                                # utility function of the
                                # shipment size/vehicle type MNL
                                travTime = skimTravTime[
                                    (origZone[count]) * nZones +
                                    (destZone[count])] / 3600
                                distance = skimDistance[
                                    (origZone[count]) * nZones +
                                    (destZone[count])] / 1000
                                inventoryCosts = absoluteShipmentSizes
                                longHaul = (distance > 100)

                                # Determine the utility and probability
                                # for each alternative
                                utilities = np.zeros(nVT * nShipSize)

                                for ss in range(nShipSize):
                                    for vt in range(nVT):
                                        transportCosts = (
                                            costPerHour[vt] * travTime +
                                            costPerKm[vt] * distance)

                                        # Multiply transport costs by
                                        # number of required vehicles
                                        transportCosts *= np.ceil(
                                            absoluteShipmentSizes[ss] /
                                            truckCapacities[vt])

                                        # Utility function
                                        index = ss * nVT + vt
                                        utilities[index] = (
                                            B_TransportCosts * transportCosts +
                                            B_InventoryCosts * inventoryCosts[ss] +
                                            B_FromDC * fromDC * (vt == 0) +
                                            B_ToDC * toDC * (vt in [3, 4, 5]) +
                                            B_LongHaul_TruckTrailer * longHaul * (vt in [3, 4]) +
                                            B_LongHaul_TractorTrailer * longHaul * (vt == 5) +
                                            ASC_VT[vt])

                                probabilities = (
                                    np.exp(utilities) /
                                    np.sum(np.exp(utilities)))
                                cumProbabilities = np.cumsum(probabilities)

                                # Sample one choice based on the
                                # cumulative probability distribution
                                ssvt = draw_choice(cumProbabilities)

                                # The chosen shipment size category
                                ssChosen = int(np.floor(ssvt / nVT))
                                shipmentSizeCat[count] = ssChosen
                                shipmentSize[count] = min(
                                    absoluteShipmentSizes[ssChosen],
                                    totalWeight - allocatedWeight)

                                # The chosen vehicle type
                                vehicleType[count] = (
                                    ssvt - ssChosen * nVT)

                                # Update weight and counter
                                allocatedWeight += shipmentSize[count]
                                allocatedWeightInternal += shipmentSize[count]
                                count += 1

                                if root != '':
                                    if count % 300 == 0:
                                        root.progressBar['value'] = (
                                            percStart +
                                            (percEnd - percStart) *
                                            (allocatedWeightInternal / totalWeightInternal))

            if doExtArea:

                print("Synthesizing shipments leaving study area...")
                log_file.write("Synthesizing shipments leaving study area...\n")

                percStart = 40
                percEnd = 65

                if root != '':
                    root.update_statusbar(
                        "Shipment Synthesizer: " +
                        "Synthesizing shipments leaving study area")
                    root.progressBar['value'] = percStart

                # For progress bar
                totalWeightExport = np.sum([
                    np.sum(np.sum(demandExportByFT[ft]))
                    for ft in range(nFlowTypesExternal)])
                allocatedWeightExport = 0

                for ls in range(nLS):

                    for nstr in range(nNSTR):

                        if lsToNstr[nstr, ls] > 0:
                            print(
                                f"\tFor logistic segment {ls} (NSTR{nstr})",
                                end='\r')
                            log_file.write(
                                f"\tFor logistic segment {ls} (NSTR{nstr})\n")

                            if root != '':
                                root.update_statusbar(
                                    "Shipment Synthesizer: " +
                                    "Synthesizing shipments leaving study area" +
                                    " (LS " + str(ls) +
                                    " and NSTR " + str(nstr) + ")")

                            # Selecting the logit parameter for this NSTR group
                            tmpParams = paramsShipSizeVehType[dictNSTR[nstr]]
                            B_TransportCosts = tmpParams['B_TransportCosts']
                            B_InventoryCosts = tmpParams['B_InventoryCosts']
                            B_FromDC = tmpParams['B_FromDC']
                            B_ToDC = tmpParams['B_ToDC']
                            B_LongHaul_TruckTrailer = (
                                tmpParams['B_LongHaul_TruckTrailer'])
                            B_LongHaul_TractorTrailer = (
                                tmpParams['B_LongHaul_TractorTrailer'])
                            ASC_VT = [
                                tmpParams[f'ASC_VT_{i+1}']
                                for i in range(nVT)]

                            for ft in range(nFlowTypesExternal):

                                for dest in range(nSuperZones):
                                    allocatedWeight = 0
                                    totalWeight = (
                                        demandExportByFT[ft][dest, ls] *
                                        lsToNstr[nstr, ls])

                                    tmpCostTime = (
                                        costPerHourSourcing *
                                        skimTravTime[(nInternalZones + dest)::nZones] /
                                        3600)
                                    tmpCostDist = (
                                        costPerKmSourcing *
                                        skimDistance[(nInternalZones + dest)::nZones] /
                                        1000)
                                    tmpCost = tmpCostTime + tmpCostDist

                                    distanceDecay = (
                                        1 / (1 + np.exp(
                                            alpha + beta * np.log(tmpCost))))

                                    if ft + 1 + nFlowTypesInternal == 10:
                                        distanceDecay = distanceDecay[firmZone]
                                    elif ft + 1 + nFlowTypesInternal == 11:
                                        distanceDecay = distanceDecay[dcZones]
                                    elif ft + 1 + nFlowTypesInternal == 12:
                                        distanceDecay = distanceDecay[ttZones]

                                    distanceDecay /= np.sum(distanceDecay)

                                    while allocatedWeight < totalWeight:
                                        flowType[count] = ft + 1 + nFlowTypesInternal
                                        logisticSegment[count] = ls
                                        goodsType[count] = nstr
                                        toFirm[count] = 0
                                        destZone[count] = nInternalZones + dest
                                        destX[count] = superZoneX[dest]
                                        destY[count] = superZoneY[dest]

                                        if ls == 6:
                                            cep = draw_choice(cepSharesTotal)
                                            depot = draw_choice(
                                                cepDepotShares[cep])
                                            fromFirm[count] = 0
                                            origZone[count] = cepDepotZones[cep][depot]
                                            origX[count] = cepDepotX[cep][depot]
                                            origY[count] = cepDepotY[cep][depot]
                                            fromDC = 1

                                        # From consumer
                                        elif flowType[count] == 10:
                                            prob = np.cumsum(
                                                probSend[:, nstr] *
                                                distanceDecay)
                                            prob /= prob[-1]
                                            fromFirm[count] = draw_choice(prob)
                                            origZone[count] = firmZone[fromFirm[count]]
                                            origX[count] = firmX[fromFirm[count]]
                                            origY[count] = firmY[fromFirm[count]]
                                            fromDC = 0

                                        # From distribution center
                                        elif flowType[count] == 11:
                                            prob = np.cumsum(
                                                probDC * distanceDecay)
                                            prob /= prob[-1]
                                            fromFirm[count] = draw_choice(prob)
                                            origZone[count] = dcZones[fromFirm[count]]
                                            origX[count] = logNodesX[fromFirm[count]]
                                            origY[count] = logNodesY[fromFirm[count]]
                                            fromDC = 1

                                        # From transshipment terminal
                                        elif flowType[count] == 12:
                                            prob = np.cumsum(
                                                probTT * distanceDecay)
                                            prob /= prob[-1]
                                            fromFirm[count] = ttZones[
                                                draw_choice(prob)]
                                            origZone[count] = fromFirm[count]
                                            origX[count] = zoneX[fromFirm[count]]
                                            origY[count] = zoneY[fromFirm[count]]
                                            fromDC = 0

                                        # Determine values for attributes in
                                        # the utility function of the
                                        # shipment size/vehicle type MNL
                                        travTime = skimTravTime[
                                            (origZone[count]) * nZones +
                                            (destZone[count])] / 3600
                                        distance = skimDistance[
                                            (origZone[count]) * nZones +
                                            (destZone[count])] / 1000
                                        inventoryCosts = absoluteShipmentSizes
                                        longHaul = (distance > 100)

                                        # Determine the utility and probability
                                        # for each alternative
                                        utilities = np.zeros(nVT * nShipSize)

                                        for ss in range(nShipSize):
                                            for vt in range(nVT):
                                                transportCosts = (
                                                    costPerHour[vt] * travTime +
                                                    costPerKm[vt] * distance)
                                                transportCosts *= np.ceil(
                                                    absoluteShipmentSizes[ss] /
                                                    truckCapacities[vt])

                                                index = ss * nVT + vt
                                                utilities[index] = (
                                                    B_TransportCosts * transportCosts +
                                                    B_InventoryCosts * inventoryCosts[ss] +
                                                    B_FromDC * fromDC * (vt == 0) +
                                                    B_ToDC * toDC * (vt in [3, 4, 5]) +
                                                    B_LongHaul_TruckTrailer * longHaul * (vt in [3, 4]) +
                                                    B_LongHaul_TractorTrailer * longHaul * (vt == 5) +
                                                    ASC_VT[vt])

                                        probabilities = (
                                            np.exp(utilities) /
                                            np.sum(np.exp(utilities)))
                                        cumProbabilities = np.cumsum(probabilities)

                                        # Sample one choice based on the
                                        # cumulative probability distribution
                                        ssvt = draw_choice(cumProbabilities)

                                        # The chosen shipment size category
                                        ssChosen = int(np.floor(
                                            ssvt / nVT))
                                        shipmentSizeCat[count] = ssChosen
                                        shipmentSize[count] = min(
                                            absoluteShipmentSizes[ssChosen],
                                            totalWeight - allocatedWeight)

                                        # The chosen vehicle type
                                        vehicleType[count] = (
                                            ssvt - ssChosen * nVT)

                                        # Update weight and counter
                                        allocatedWeight += shipmentSize[count]
                                        allocatedWeightExport += shipmentSize[count]
                                        count += 1

                                        if root != '':
                                            if count % 300 == 0:
                                                root.progressBar['value'] = (
                                                    percStart +
                                                    (percEnd - percStart) *
                                                    (allocatedWeightExport/ totalWeightExport))

                fromDC = 0

                print("Synthesizing shipments entering study area...")
                log_file.write("Synthesizing shipments entering study area...\n")

                percStart = 65
                percEnd = 90

                if root != '':
                    root.progressBar['value'] = percStart
                    root.update_statusbar(
                        "Shipment Synthesizer: " +
                        "Synthesizing shipments entering study area")

                totalWeightImport = np.sum([
                    np.sum(np.sum(demandImportByFT[ft]))
                    for ft in range(nFlowTypesExternal)])
                allocatedWeightImport  = 0

                for ls in range(nLS):

                    for nstr in range(nNSTR):

                        if lsToNstr[nstr, ls] > 0:
                            print(
                                f"\tFor logistic segment {ls} (NSTR{nstr})",
                                end='\r')
                            log_file.write(
                                f"\tFor logistic segment {ls} (NSTR{nstr})\n")

                            if root != '':
                                root.update_statusbar(
                                    "Shipment Synthesizer: " +
                                    "Synthesizing shipments entering study area" +
                                    " (LS " + str(ls) +
                                    " and NSTR " + str(nstr) + ")")

                            # Selecting the logit parameter for this NSTR group
                            tmpParams = paramsShipSizeVehType[dictNSTR[nstr]]
                            B_TransportCosts = tmpParams['B_TransportCosts']
                            B_InventoryCosts = tmpParams['B_InventoryCosts']
                            B_FromDC = tmpParams['B_FromDC']
                            B_ToDC = tmpParams['B_ToDC']
                            B_LongHaul_TruckTrailer = (
                                tmpParams['B_LongHaul_TruckTrailer'])
                            B_LongHaul_TractorTrailer = (
                                tmpParams['B_LongHaul_TractorTrailer'])
                            ASC_VT = [
                                tmpParams[f'ASC_VT_{i+1}']
                                for i in range(nVT)]

                            for ft in range(nFlowTypesExternal):

                                for orig in range(nSuperZones):
                                    allocatedWeight = 0
                                    totalWeight = (
                                        demandImportByFT[ft][orig, ls] *
                                        lsToNstr[nstr, ls])

                                    tmpCostTime = (
                                        costPerHourSourcing *
                                        skimTravTime[(nInternalZones + orig) * nZones + np.arange(nZones)] /
                                        3600)
                                    tmpCostDist = (
                                        costPerKmSourcing *
                                        skimDistance[(nInternalZones + orig) * nZones + np.arange(nZones)] /
                                        1000)
                                    tmpCost = tmpCostTime + tmpCostDist

                                    distanceDecay = (
                                        1 / (1 + np.exp(
                                            alpha + beta * np.log(tmpCost))))

                                    if ft + 1 + nFlowTypesInternal == 10:
                                        distanceDecay = distanceDecay[firmZone]
                                    elif ft + 1 + nFlowTypesInternal == 11:
                                        distanceDecay = distanceDecay[dcZones]
                                    elif ft + 1 + nFlowTypesInternal == 12:
                                        distanceDecay = distanceDecay[ttZones]

                                    distanceDecay /= np.sum(distanceDecay)

                                    while allocatedWeight < totalWeight:
                                        flowType[count] = ft + 1 + nFlowTypesInternal
                                        logisticSegment[count] = ls
                                        goodsType[count] = nstr
                                        fromFirm[count] = 0
                                        origZone[count] = nInternalZones + orig
                                        origX[count] = superZoneX[orig]
                                        origY[count] = superZoneY[orig]

                                        if ls == 6:
                                            cep = draw_choice(cepSharesTotal)
                                            depot = draw_choice(
                                                cepDepotShares[cep])
                                            toFirm[count] = 0
                                            destZone[count] = cepDepotZones[cep][depot]
                                            destX[count] = cepDepotX[cep][depot]
                                            destY[count] = cepDepotY[cep][depot]
                                            toDC = 1

                                        # To consumer
                                        elif flowType[count] == 10:
                                            prob = np.cumsum(
                                                probReceive[:, nstr] *
                                                distanceDecay)
                                            prob /= prob[-1]
                                            toFirm[count] = draw_choice(prob)
                                            destZone[count] = firmZone[toFirm[count]]
                                            destX[count] = firmX[toFirm[count]]
                                            destY[count] = firmY[toFirm[count]]
                                            toDC = 0

                                        # To distribution center
                                        elif flowType[count] == 11:
                                            prob = np.cumsum(
                                                probDC * distanceDecay)
                                            prob /= prob[-1]
                                            toFirm[count] = draw_choice(prob)
                                            destZone[count] = dcZones[toFirm[count]]
                                            destX[count] = logNodesX[toFirm[count]]
                                            destY[count] = logNodesY[toFirm[count]]
                                            toDC = 1

                                        # To transshipment terminal
                                        elif flowType[count] == 12:
                                            prob = np.cumsum(
                                                probTT * distanceDecay)
                                            prob /= prob[-1]
                                            toFirm[count] = ttZones[
                                                draw_choice(prob)]
                                            destZone[count] = toFirm[count]
                                            destX[count] = zoneX[toFirm[count]]
                                            destY[count] = zoneY[toFirm[count]]
                                            toDC = 0

                                        # Determine values for attributes in
                                        # the utility function of the
                                        # shipment size/vehicle type MNL
                                        travTime = skimTravTime[
                                            (origZone[count]) * nZones +
                                            (destZone[count])] / 3600
                                        distance = skimDistance[
                                            (origZone[count]) * nZones +
                                            (destZone[count])] / 1000
                                        inventoryCosts = absoluteShipmentSizes
                                        longHaul = (distance > 100)

                                        # Determine the utility and
                                        # probability for each alternative
                                        utilities = np.zeros(nVT * nShipSize)

                                        for ss in range(nShipSize):
                                            for vt in range(nVT):
                                                transportCosts = (
                                                    costPerHour[vt] * travTime +
                                                    costPerKm[vt] * distance)
                                                transportCosts *= np.ceil(
                                                    absoluteShipmentSizes[ss] /
                                                    truckCapacities[vt])

                                                index = ss * nVT + vt
                                                utilities[index] = (
                                                    B_TransportCosts * transportCosts +
                                                    B_InventoryCosts * inventoryCosts[ss] +
                                                    B_FromDC * fromDC * (vt == 0) + \
                                                    B_ToDC * toDC * (vt in [3, 4, 5]) +
                                                    B_LongHaul_TruckTrailer * longHaul * (vt in [3, 4]) +
                                                    B_LongHaul_TractorTrailer * longHaul * (vt == 5) +
                                                    ASC_VT[vt])

                                        probabilities = (
                                            np.exp(utilities) /
                                            np.sum(np.exp(utilities)))
                                        cumProbabilities = np.cumsum(probabilities)

                                        # Sample one choice based on the
                                        # cumulative probability distribution
                                        ssvt = draw_choice(cumProbabilities)

                                        # The chosen shipment size category
                                        ssChosen = int(np.floor(ssvt / nVT))
                                        shipmentSizeCat[count] = ssChosen
                                        shipmentSize[count] = min(
                                            absoluteShipmentSizes[ssChosen],
                                            totalWeight - allocatedWeight)

                                        # The chosen vehicle type
                                        vehicleType[count] = (
                                            ssvt - ssChosen * nVT)

                                        # Update weight and counter
                                        allocatedWeight += shipmentSize[count]
                                        allocatedWeightImport += shipmentSize[count]
                                        count += 1

                                        if root != '':
                                            if count % 300 == 0:
                                                root.progressBar['value'] = (
                                                    percStart +
                                                    (percEnd - percStart) *
                                                    (allocatedWeightImport / totalWeightImport))

            if varDict['CORRECTIONS_TONNES'] != '':
                print("Synthesizing additional shipments (corrections)...")
                log_file.write(
                    "Synthesizing additional shipments (corrections)...\n")

                percStart = 90
                percEnd = 92

                if root != '':
                    root.progressBar['value'] = percStart
                    root.update_statusbar(
                        "Shipment Synthesizer: " +
                        "Synthesizing additional shipments (corrections)")

                for cor in range(nCorrections):
                    orig = corrections.at[cor, 'ORIG']
                    dest = corrections.at[cor, 'DEST']

                    print(f"\tAdditional shipments (correction {cor+1})")
                    log_file.write(
                        f"\tAdditional shipments (correction {cor+1})\n")

                    if root != '':
                        root.update_statusbar(
                            "Shipment Synthesizer: " +
                            "Synthesizing additional shipments (corrections)")

                    for ls in range(nLS):

                        if corrections.at[cor, f'LS{ls}'] > 0:

                            for nstr in range(nNSTR):

                                if lsToNstr[nstr, ls] > 0:

                                    # Selecting the logit parameters for
                                    # this NSTR group
                                    tmpParams = paramsShipSizeVehType[dictNSTR[nstr]]
                                    B_TransportCosts = tmpParams['B_TransportCosts']
                                    B_InventoryCosts = tmpParams['B_InventoryCosts']
                                    B_FromDC = tmpParams['B_FromDC']
                                    B_ToDC = tmpParams['B_ToDC']
                                    B_LongHaul_TruckTrailer = (
                                        tmpParams['B_LongHaul_TruckTrailer'])
                                    B_LongHaul_TractorTrailer = (
                                        tmpParams['B_LongHaul_TractorTrailer'])
                                    ASC_VT = [
                                        tmpParams[f'ASC_VT_{i+1}']
                                        for i in range(nVT)]

                                    totalWeight = (
                                        corrections.at[cor, f'LS{ls}'] *
                                        lsToNstr[nstr, ls])
                                    allocatedWeight = 0

                                    # While the weight of all synthesized
                                    # shipments for this segment so far
                                    # does not exceed the total weight
                                    # for this segment
                                    while allocatedWeight < totalWeight:
                                        flowType[count] = 1
                                        goodsType[count] = nstr
                                        logisticSegment[count] = ls

                                        # Determine receiving firm
                                        if dest == -1:
                                            toFirm[count] = draw_choice(
                                                cumProbReceive[:, nstr])
                                            destZone[count] = firmZone[toFirm[count]]
                                            destX[count] = firmX[toFirm[count]]
                                            destY[count] = firmY[toFirm[count]]
                                        else:
                                            toFirm[count] = -99999
                                            destZone[count] = invZoneDict[dest]
                                            destX[count] = zoneX[destZone[count]]
                                            destY[count] = zoneY[destZone[count]]

                                        toDC = 0

                                        tmpCostTime = (
                                            costPerHourSourcing *
                                            skimTravTime[destZone[count]::nZones] /
                                            3600) 
                                        tmpCostDist = (
                                            costPerKmSourcing *
                                            skimDistance[destZone[count]::nZones] /
                                            1000)
                                        tmpCost = tmpCostTime + tmpCostDist

                                        distanceDecay = (
                                            1 / (1 + np.exp(
                                                alpha + beta * np.log(tmpCost))))
                                        distanceDecay = distanceDecay[firmZone]

                                        distanceDecay /= np.sum(distanceDecay)

                                        # Determine sending firm
                                        if orig == -1:
                                            prob = probSend[:, nstr].copy()
                                            prob *= distanceDecay
                                            prob = np.cumsum(prob)
                                            prob /= prob[-1]
                                            fromFirm[count] = draw_choice(prob)
                                            origZone[count] = firmZone[fromFirm[count]]
                                            origX[count] = firmX[fromFirm[count]]
                                            origY[count] = firmY[fromFirm[count]]
                                        else:
                                            fromFirm[count] = -99999
                                            origZone[count] = invZoneDict[orig]
                                            origX[count]    = zoneX[origZone[count]]
                                            origY[count]    = zoneY[origZone[count]]

                                        fromDC          = 0

                                        # Determine values for attributes
                                        # in the utility function of the
                                        # shipment size/vehicle type MNL
                                        travTime = skimTravTime[
                                            (origZone[count]) * nZones +
                                            (destZone[count])] / 3600
                                        distance = skimDistance[
                                            (origZone[count]) * nZones +
                                            (destZone[count])] / 1000
                                        inventoryCosts = absoluteShipmentSizes
                                        longHaul = (distance > 100)

                                        # Determine the utility and probability for each alternative
                                        utilities = np.zeros(nVT * nShipSize)

                                        for ss in range(nShipSize):
                                            for vt in range(nVT):
                                                transportCosts = (
                                                    costPerHour[vt] * travTime +
                                                    costPerKm[vt] * distance)
                                                
                                                # Multiply transport costs by number of required vehicles
                                                transportCosts *= np.ceil(
                                                    absoluteShipmentSizes[ss] /
                                                    truckCapacities[vt])

                                                # Utility function
                                                index = ss * nVT + vt
                                                utilities[index] = (
                                                    B_TransportCosts * transportCosts +
                                                    B_InventoryCosts * inventoryCosts[ss] +
                                                    B_FromDC * fromDC * (vt == 0) +
                                                    B_ToDC * toDC * (vt in [3, 4, 5]) +
                                                    B_LongHaul_TruckTrailer * longHaul * (vt in [3, 4]) +
                                                    B_LongHaul_TractorTrailer * longHaul * (vt == 5) +
                                                    ASC_VT[vt])

                                        probabilities = (
                                            np.exp(utilities) /
                                            np.sum(np.exp(utilities)))
                                        cumProbabilities = np.cumsum(probabilities)
                                                    
                                        # Sample one choice based on the
                                        # cumulative probability distribution
                                        ssvt = draw_choice(cumProbabilities)

                                        # The chosen shipment size category
                                        ssChosen = int(np.floor(ssvt / nVT))
                                        shipmentSizeCat[count] = ssChosen
                                        shipmentSize[count] = min(
                                            absoluteShipmentSizes[ssChosen],
                                            totalWeight - allocatedWeight)

                                        # The chosen vehicle type
                                        vehicleType[count] = (
                                            ssvt - ssChosen * nVT)

                                        # Update weight and counter
                                        allocatedWeight += shipmentSize[count]
                                        count += 1

                    if root != '':
                        root.progressBar['value'] = (
                            percStart +
                            (percEnd - percStart) * (cor / nCorrections))

            nShips = count

            # ------------------------ Delivery time choice -------------------

            print('Delivery time choice...')
            log_file.write('Delivery time choice...\n')

            if root != '':
                root.progressBar['value'] = 92
                root.update_statusbar(
                    "Shipment Synthesizer: " +
                    "Delivery time choice")
                
            # Determine delivery time period for each shipment
            deliveryTimePeriod = {}
            lowerTOD = {}
            upperTOD = {}
            
            for i in range(nShips):
                    
                orig = zoneDict[origZone[i]]
                dest = zoneDict[destZone[i]]
                ls = logisticSegment[i]

                ASC = {}
                beta_ToTT   = {}
                beta_ToPC   = {}
                beta_FromTT = {}
                beta_FromPC = {}
                beta_SmallTruck     = {}
                beta_MediumTruck    = {}
                beta_TruckTrailer   = {}
                beta_TractorTrailer = {}
                
                beta_durTimePeriod = paramsTimeOfDay[ls]['DurTimePeriod']
                
                for t in range(nTimeIntervalsLS[ls]):
                    ASC[t] = paramsTimeOfDay[ls][f'ASC_{t+1}']
                    beta_ToTT[t] = paramsTimeOfDay[ls][f'ToTT_{t+1}']
                    beta_ToPC[t] = paramsTimeOfDay[ls][f'ToPC_{t+1}']
                    beta_FromTT[t] = paramsTimeOfDay[ls][f'FromTT_{t+1}']
                    beta_FromPC[t] = paramsTimeOfDay[ls][f'FromPC_{t+1}']
                    beta_SmallTruck[t] = paramsTimeOfDay[ls][f'VT_SmallTruck_{t+1}']
                    beta_MediumTruck[t] = paramsTimeOfDay[ls][f'VT_MediumTruck_{t+1}']
                    beta_TruckTrailer[t] = paramsTimeOfDay[ls][f'VT_TruckTrailer_{t+1}']
                    beta_TractorTrailer[t] = paramsTimeOfDay[ls][f'VT_TractorTrailer_{t+1}']
                
                utilities = {}
                for t in range(nTimeIntervalsLS[ls]):
                    utilities[t] = (
                        ASC[t] +
                        beta_durTimePeriod     * np.log(2 * timeIntervalsDur[ls][t]) +
                        beta_ToTT[t]           * isTT[dest] * urbanDensityCat[dest] +
                        beta_ToPC[t]           * isPC[dest] * urbanDensityCat[dest] +
                        beta_FromTT[t]         * isTT[orig] * urbanDensityCat[orig] +
                        beta_FromPC[t]         * isPC[orig] * urbanDensityCat[orig] +
                        beta_SmallTruck[t]     * (vehicleType[i] == 0) +
                        beta_MediumTruck[t]    * (vehicleType[i] == 1) +
                        beta_TruckTrailer[t]   * (vehicleType[i] in (3, 4)) +
                        beta_TractorTrailer[t] * (vehicleType[i] == 5))

                utilities = np.array(list(utilities.values()))
                probs = np.exp(utilities)
                probs /= np.sum(probs)
                cumProbs = np.cumsum(probs)
                cumProbs /= cumProbs[-1]

                deliveryTimePeriod[i] = draw_choice(cumProbs)
                lowerTOD[i] = timeIntervals[ls][deliveryTimePeriod[i]][0]
                upperTOD[i] = timeIntervals[ls][deliveryTimePeriod[i]][1]

            # --------------------- Creating shipments CSV --------------------

            # Shipment attributes in a list instead of a dictionary
            fromFirm        = list(fromFirm.values())
            toFirm          = list(toFirm.values())
            flowType        = list(flowType.values())
            logisticSegment = list(logisticSegment.values())
            goodsType       = list(goodsType.values())
            shipmentSize    = list(shipmentSize.values())
            shipmentSizeCat = list(shipmentSizeCat.values())
            vehicleType     = list(vehicleType.values())
            origZone        = list(origZone.values())
            destZone        = list(destZone.values())
            lowerTOD        = list(lowerTOD.values())
            upperTOD        = list(upperTOD.values())
            periodTOD       = list(deliveryTimePeriod.values())
            
            shipCols  = [
                "SHIP_ID",
                "ORIG", "DEST",
                "NSTR",
                "WEIGHT", "WEIGHT_CAT", 
                "FLOWTYPE", "LS", 
                "VEHTYPE",
                "SEND_FIRM", "RECEIVE_FIRM",
                "SEND_DC", "RECEIVE_DC",
                "TOD_PERIOD", "TOD_LOWER", "TOD_UPPER"]

            shipments = pd.DataFrame(
                np.zeros((nShips, len(shipCols))),
                columns=shipCols)
    
            shipments['SHIP_ID'     ] = np.arange(nShips)
            shipments['ORIG'        ] = [zoneDict[x] for x in origZone]
            shipments['DEST'        ] = [zoneDict[x] for x in destZone]
            shipments['NSTR'        ] = goodsType
            shipments['WEIGHT'      ] = shipmentSize
            shipments['WEIGHT_CAT'  ] = shipmentSizeCat
            shipments['FLOWTYPE'    ] = flowType
            shipments['LS'          ] = logisticSegment
            shipments['VEHTYPE'     ] = vehicleType
            shipments['SEND_FIRM'   ] = [firmID[x] if x != -99999 else -99999 for x in fromFirm]
            shipments['RECEIVE_FIRM'] = [firmID[x] if x != -99999 else -99999 for x in   toFirm]
            shipments['SEND_DC'     ] = -99999
            shipments['RECEIVE_DC'  ] = -99999
            shipments['TOD_PERIOD'  ] = periodTOD
            shipments['TOD_LOWER'   ] = lowerTOD
            shipments['TOD_UPPER'   ] = upperTOD

            # For the external zones and logistical nodes there is no firm, hence firm ID -99999
            shipments.loc[
                shipments['ORIG'] > 99999900,
                'SEND_FIRM'] = -99999
            shipments.loc[
                shipments['DEST'] > 99999900,
                'RECEIVE_FIRM'] = -99999
            shipments.loc[
                np.array(logisticSegment) == 6,
                ['SEND_FIRM','RECEIVE_FIRM']] = -99999
            shipments.loc[
                np.array(flowType) > 10,
                ['SEND_FIRM','RECEIVE_FIRM']] = -99999
            shipments.loc[
                (np.array(flowType) == 2) | (np.array(flowType) == 5) | (np.array(flowType) == 8),
                'RECEIVE_FIRM'] = -99999
            shipments.loc[
                (np.array(flowType) == 4) | (np.array(flowType) == 7) | (np.array(flowType) == 9),
                'RECEIVE_FIRM'] = -99999
            shipments.loc[
                (np.array(flowType) == 3) | (np.array(flowType) == 5) | (np.array(flowType) == 7),
                'SEND_FIRM'] = -99999
            shipments.loc[
                (np.array(flowType) == 6) | (np.array(flowType) == 8) | (np.array(flowType) == 9),
                'SEND_FIRM'] = -99999

            # Only fill in DC ID for shipments to and from DC
            whereToDC = (
                (shipments['FLOWTYPE'] == 2) |
                (shipments['FLOWTYPE'] == 5) |
                (shipments['FLOWTYPE'] == 8) |
                ((shipments['FLOWTYPE'] == 11) & (shipments['ORIG'] > 99999900)))
            whereFromDC = (
                (shipments['FLOWTYPE'] == 3) |
                (shipments['FLOWTYPE'] == 5) |
                (shipments['FLOWTYPE'] == 7) |
                ((shipments['FLOWTYPE'] == 11) & (shipments['DEST'] > 99999900)))                    
            shipments.loc[whereToDC,  'RECEIVE_DC'] = np.array(toFirm)[whereToDC]
            shipments.loc[whereFromDC,'SEND_DC'   ] = np.array(fromFirm)[whereFromDC]

        else:
            # Import the reference shipments
            shipments = pd.read_csv(varDict['SHIPMENTS_REF'])

        # Get the datatypes right
        intCols = [
            "SHIP_ID",
            "ORIG", "DEST",
            "NSTR",
            "WEIGHT_CAT",
            "FLOWTYPE",
            "LS", 
            "VEHTYPE",
            "SEND_FIRM", "RECEIVE_FIRM",
            "SEND_DC", "RECEIVE_DC",
            "TOD_PERIOD", "TOD_LOWER", "TOD_UPPER"]
        floatCols = ['WEIGHT']
        shipments[intCols  ] = shipments[intCols].astype(int)
        shipments[floatCols] = shipments[floatCols].astype(float)

        # Redirect shipments via UCCs and change vehicle type
        if varDict['LABEL'] == 'UCC':
            if varDict['SHIPMENTS_REF'] == "":

                message = (
                    'Exporting REF shipments to ' +
                    varDict['OUTPUTFOLDER'] +
                    "Shipments_REF.csv")
                print(message)
                log_file.write(message + "\n")
                
                if root != '':
                    root.progressBar['value'] = 93
                    root.update_statusbar(
                        "Shipment Synthesizer: " +
                        "Exporting REF shipments to CSV")

                shipments.to_csv(varDict['OUTPUTFOLDER'] + 'Shipments_REF.csv')

            print("Redirecting shipments via UCC...")
            log_file.write("Redirecting shipments via UCC...\n")

            if root != '':
                root.progressBar['value'] = 94
                root.update_statusbar(
                    "Shipment Synthesizer: " +
                    "Redirecting shipments via UCC")

            shipments['FROM_UCC'] = 0
            shipments['TO_UCC'  ] = 0

            whereOrigZEZ = np.array([
                i for i in shipments[shipments['ORIG'] < 99999900].index
                if zonesShape['ZEZ'][shipments['ORIG'][i]] >= 1], dtype=int)
            whereDestZEZ = np.array([
                i for i in shipments[shipments['DEST'] < 99999900].index
                if zonesShape['ZEZ'][shipments['DEST'][i]] >= 1], dtype=int)
            setWhereOrigZEZ = set(whereOrigZEZ)
            setWhereDestZEZ = set(whereDestZEZ)

            whereBothZEZ = [
                i for i in shipments.index
                if i in setWhereOrigZEZ and i in setWhereDestZEZ]

            newShipments = pd.DataFrame(np.zeros(shipments.shape))
            newShipments.columns = shipments.columns
            newShipments[intCols  ] = newShipments[intCols].astype(int)
            newShipments[floatCols] = newShipments[floatCols].astype(float)

            count = 0

            for i in whereOrigZEZ:

                if i not in setWhereDestZEZ:
                    ls = int(shipments['LS'][i])

                    if probConsolidation[ls][0] > np.random.rand():
                        trueOrigin = int(shipments['ORIG'][i])
                        newOrigin = zonesShape['UCC_zone'][trueOrigin]

                        # Redirect to UCC
                        shipments.at[i,'ORIG'    ] = newOrigin
                        shipments.at[i,'FROM_UCC'] = 1
                        if varDict['SHIPMENTS_REF'] == "":
                            origX[i] = zoneX[invZoneDict[newOrigin]]
                            origY[i] = zoneY[invZoneDict[newOrigin]]

                        # Add shipment from ZEZ to UCC
                        newShipments.loc[count, :] = list(shipments.loc[i, :].copy())
                        newShipments.at[count,'ORIG'    ] = trueOrigin
                        newShipments.at[count,'DEST'    ] = newOrigin
                        newShipments.at[count,'FROM_UCC'] = 0
                        newShipments.at[count,'TO_UCC'  ] = 1
                        newShipments.at[count,'VEHTYPE' ] = vehUccToVeh[
                            draw_choice(sharesVehUCC[ls, :])]
                        if varDict['SHIPMENTS_REF'] == "":
                            origX[nShips+count] = zoneX[invZoneDict[trueOrigin]]
                            origY[nShips+count] = zoneY[invZoneDict[trueOrigin]]
                            destX[nShips+count] = zoneX[invZoneDict[newOrigin]]
                            destY[nShips+count] = zoneY[invZoneDict[newOrigin]]

                        count += 1

            for i in whereDestZEZ:

                if i not in setWhereOrigZEZ:
                    ls = int(shipments['LS'][i])

                    if probConsolidation[ls][0] > np.random.rand():
                        trueDest = int(shipments['DEST'][i])
                        newDest = zonesShape['UCC_zone'][trueDest]

                        # Redirect to UCC
                        shipments.at[i,'DEST'  ] = newDest
                        shipments.at[i,'TO_UCC'] = 1
                        if varDict['SHIPMENTS_REF'] == "":
                            destX[i] = zoneX[invZoneDict[newDest]]
                            destY[i] = zoneY[invZoneDict[newDest]]   

                        # Add shipment to ZEZ from UCC
                        newShipments.loc[count, :] = list(shipments.loc[i, :].copy())
                        newShipments.at[count,'ORIG'    ] = newDest
                        newShipments.at[count,'DEST'    ] = trueDest
                        newShipments.at[count,'FROM_UCC'] = 1
                        newShipments.at[count,'TO_UCC'  ] = 0
                        newShipments.at[count,'VEHTYPE' ] = vehUccToVeh[
                            draw_choice(sharesVehUCC[ls, :])]
                        if varDict['SHIPMENTS_REF'] == "":
                            origX[nShips+count] = zoneX[invZoneDict[newDest]]
                            origY[nShips+count] = zoneY[invZoneDict[newDest]]
                            destX[nShips+count] = zoneX[invZoneDict[trueDest]]
                            destY[nShips+count] = zoneY[invZoneDict[trueDest]]

                        count += 1

            # Also change vehicle type and rerouting
            # for shipments that go from a ZEZ area to a ZEZ area
            for i in whereBothZEZ:
                ls = int(shipments['LS'][i])

                # Als het binnen dezelfde gemeente (i.e. dezelfde ZEZ) blijft,
                # dan hoeven we alleen maar het voertuigtype aan te passen

                # Assume dangerous goods keep the same vehicle type
                gemeenteOrig = zonesShape['Gemeentena'][shipments['ORIG'][i]]
                gemeenteDest = zonesShape['Gemeentena'][shipments['DEST'][i]]
                if gemeenteOrig == gemeenteDest:
                    if ls != 7:
                        shipments.at[i,'VEHTYPE'] = vehUccToVeh[
                            draw_choice(sharesVehUCC[ls, :])]

                # Als het van de ene ZEZ naar de andere ZEZ gaat,
                # maken we 3 legs: ZEZ1--> UCC1, UCC1-->UCC2, UCC2-->ZEZ2
                else:
                    if probConsolidation[ls][0] > np.random.rand():
                        trueOrigin = int(shipments['ORIG'][i])
                        trueDest   = int(shipments['DEST'][i])
                        newOrigin  = zonesShape['UCC_zone'][trueOrigin]
                        newDest    = zonesShape['UCC_zone'][trueDest]

                        # Redirect to UCC
                        shipments.at[i,'ORIG'    ] = newOrigin
                        shipments.at[i,'FROM_UCC'] = 1
                        if varDict['SHIPMENTS_REF'] == "":
                            origX[i] = zoneX[invZoneDict[newOrigin]]
                            origY[i] = zoneY[invZoneDict[newOrigin]]

                        # Add shipment from ZEZ1 to UCC1
                        newShipments.loc[count, :] = list(shipments.loc[i, :].copy())
                        newShipments.at[count,'ORIG'    ] = trueOrigin
                        newShipments.at[count,'DEST'    ] = newOrigin
                        newShipments.at[count,'FROM_UCC'] = 0
                        newShipments.at[count,'TO_UCC'  ] = 1
                        newShipments.at[count,'VEHTYPE' ] = vehUccToVeh[
                            draw_choice(sharesVehUCC[ls, :])]
                        if varDict['SHIPMENTS_REF'] == "":
                            origX[nShips + count] = zoneX[invZoneDict[trueOrigin]]
                            origY[nShips + count] = zoneY[invZoneDict[trueOrigin]]
                            destX[nShips + count] = zoneX[invZoneDict[newOrigin]]
                            destY[nShips + count] = zoneY[invZoneDict[newOrigin]]

                        count += 1

                        # Redirect to UCC
                        shipments.at[i,'DEST'  ] = newDest
                        shipments.at[i,'TO_UCC'] = 1
                        if varDict['SHIPMENTS_REF'] == "":
                            destX[i] = zoneX[invZoneDict[newDest]]
                            destY[i] = zoneY[invZoneDict[newDest]]

                        # Add shipment from UCC2 to ZEZ2
                        newShipments.loc[count, :] = list(shipments.loc[i, :].copy())
                        newShipments.at[count,'ORIG'    ] = newDest
                        newShipments.at[count,'DEST'    ] = trueDest
                        newShipments.at[count,'FROM_UCC'] = 1
                        newShipments.at[count,'TO_UCC'  ] = 0
                        newShipments.at[count,'VEHTYPE' ] = vehUccToVeh[
                            draw_choice(sharesVehUCC[ls, :])]
                        if varDict['SHIPMENTS_REF'] == "":
                            origX[nShips+count] = zoneX[invZoneDict[newDest]]
                            origY[nShips+count] = zoneY[invZoneDict[newDest]]
                            destX[nShips+count] = zoneX[invZoneDict[trueDest]]
                            destY[nShips+count] = zoneY[invZoneDict[trueDest]]

                        count += 1

            newShipments = newShipments.iloc[np.arange(count), :]

            shipments = shipments.append(newShipments)
            nShips = len(shipments)
            shipments['SHIP_ID'] = np.arange(nShips)
            shipments.index      = np.arange(nShips)

        message = (
            'Exporting ' + str(varDict['LABEL']) +' shipments to ' +
            varDict['OUTPUTFOLDER'] + f"Shipments_{varDict['LABEL']}.csv")
        print(message)
        log_file.write(message + "\n")

        if root != '':
            root.progressBar['value'] = 95
            root.update_statusbar(
                "Shipment Synthesizer: " +
                "Exporting shipments to CSV")
            
        dtypes = {
            'SHIP_ID': int,
            'ORIG': int,
            'DEST': int,
            'NSTR': int,
            'WEIGHT': float,
            'WEIGHT_CAT': int,
            'FLOWTYPE': int,
            'LS': int,
            'VEHTYPE': int,
            'SEND_FIRM': int,
            'RECEIVE_FIRM': int,
            'SEND_DC': int,
            'RECEIVE_DC': int}

        for col in dtypes.keys():
            shipments[col] = shipments[col].astype(dtypes[col])
            
        shipments.to_csv(
            varDict['OUTPUTFOLDER'] + f"Shipments_{varDict['LABEL']}.csv",
            index=False)  

        if varDict['SHIPMENTS_REF'] == "":

            # ---------------- Zonal productions and attractions --------------
            print("Writing zonal productions/attractions...")
            log_file.write("Writing zonal productions/attractions...\n")

            if root != '':
                root.progressBar['value'] = 97
                root.update_statusbar(
                    "Shipment Synthesizer: " +
                    "Writing zonal productions/attractions")
                
            prodWeight = pd.pivot_table(
                shipments,
                values=['WEIGHT'],
                index=['ORIG', 'LS'],
                aggfunc=np.sum)
            attrWeight = pd.pivot_table(
                shipments,
                values=['WEIGHT'],
                index=['DEST', 'LS'],
                aggfunc=np.sum)
            nRows = nInternalZones + nSuperZones
            nCols = nLS
            zonalProductions = np.zeros((nRows, nCols))
            zonalAttractions = np.zeros((nRows, nCols))

            for x in prodWeight.index:
                orig = invZoneDict[x[0]]
                ls   = x[1]
                zonalProductions[orig, ls] += prodWeight['WEIGHT'][x]
            for x in attrWeight.index:
                orig = invZoneDict[x[0]]
                ls   = x[1]
                zonalAttractions[orig, ls] += attrWeight['WEIGHT'][x]

            cols = ['LS0', 'LS1', 'LS2', 'LS3', 
                    'LS4', 'LS5', 'LS6', 'LS7']
            zonalProductions = pd.DataFrame(zonalProductions, columns=cols)
            zonalAttractions = pd.DataFrame(zonalAttractions, columns=cols)
            zonalProductions['ZONE'] = list(zoneDict.values())
            zonalAttractions['ZONE'] = list(zoneDict.values())
            zonalProductions['TOT_WEIGHT'] = np.sum(zonalProductions[cols], axis=1)
            zonalAttractions['TOT_WEIGHT'] = np.sum(zonalAttractions[cols], axis=1)

            cols = ['ZONE',
                    'LS0', 'LS1', 'LS2', 'LS3',
                    'LS4', 'LS5', 'LS6', 'LS7',
                    'TOT_WEIGHT']
            zonalProductions = zonalProductions[cols]
            zonalAttractions = zonalAttractions[cols]

            # Export to csv
            zonalProductions.to_csv(
                varDict['OUTPUTFOLDER'] + f"zonal_productions_{varDict['LABEL']}.csv",
                index=False)
            zonalAttractions.to_csv(
                varDict['OUTPUTFOLDER'] + f"zonal_attractions_{varDict['LABEL']}.csv",
                index=False)

            # --------------------- Creating shipments SHP --------------------
            
            print("Writing Shapefile...")
            log_file.write("Writing Shapefile...\n")

            percStart = 97
            percEnd = 100
            if root != '':
                root.progressBar['value'] = percStart
                root.update_statusbar(
                    "Shipment Synthesizer: " +
                    "Writing Shapefile")

            Ax = list(origX.values())
            Ay = list(origY.values())
            Bx = list(destX.values())
            By = list(destY.values())

            # Initialize shapefile fields
            w = shp.Writer(
                varDict['OUTPUTFOLDER'] + f"Shipments_{varDict['LABEL']}.shp")
            w.field('SHIP_ID',      'N', size=6, decimal=0)
            w.field('ORIG',         'N', size=8, decimal=0)
            w.field('DEST',         'N', size=8, decimal=0)
            w.field('NSTR',         'N', size=2, decimal=0)
            w.field('WEIGHT',       'N', size=4, decimal=2)
            w.field('WEIGHT_CAT',   'N', size=2, decimal=0)
            w.field('FLOWTYPE',     'N', size=2, decimal=0)
            w.field('LS',           'N', size=2, decimal=0)
            w.field('VEHTYPE',      'N', size=2, decimal=0)
            w.field('SEND_FIRM',    'N', size=8, decimal=0)
            w.field('RECEIVE_FIRM', 'N', size=8, decimal=0)
            w.field('SEND_DC',      'N', size=6, decimal=0)
            w.field('RECEIVE_DC',   'N', size=6, decimal=0)
            w.field('TOD_PERIOD',   'N', size=2, decimal=0)
            w.field('TOD_LOWER',    'N', size=2, decimal=0)
            w.field('TOD_UPPER',    'N', size=2, decimal=0)
            if varDict['LABEL'] == 'UCC':
                w.field('FROM_UCC', 'N', size=2, decimal=0)
                w.field('TO_UCC',   'N', size=2, decimal=0)
                  
            dbfData = np.array(shipments, dtype=object)
            for i in range(nShips):

                # Add geometry
                w.line([[
                    [Ax[i], Ay[i]],
                    [Bx[i], By[i]]]])
                
                # Add data fields
                w.record(*dbfData[i, :])
                                
                if i % int(round(nShips / 20)) == 0:
                    print(
                        '\t' + str(round(i / nShips * 100, 1)) + '%',
                        end='\r')

                    if root != '':
                        root.progressBar['value'] = (
                            percStart +
                            (percEnd - percStart) * i / nShips)

            w.close()

        # ------------------------- End of module -----------------------------
            
        totaltime = round(time.time() - start_time, 2)
        print('Finished. Run time: ' + str(totaltime) + ' seconds')
        log_file.write("Total runtime: %s seconds\n" % (totaltime))
        log_file.write(
            "End simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") +
            "\n")
        log_file.close()

        if root != '':
            root.update_statusbar("Shipment Synthesizer: Done")
            root.progressBar['value'] = 100

            # 0 means no errors in execution
            root.returnInfo = [0, [0, 0]]

            return root.returnInfo

        else:
            return [0, [0, 0]]
        
    except BaseException:
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
                root.update_statusbar("Shipment Synthesizer: Execution failed!")
                errorMessage = (
                    'Execution failed!' +
                    '\n\n' +
                    str(root.returnInfo[1][0]) +
                    '\n\n' +
                    str(root.returnInfo[1][1]))
                root.error_screen(text=errorMessage, size=[900, 350])
            
            else:
                return root.returnInfo

        else:
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
    varDict['CEP_SHARES'] = varDict['INPUTFOLDER'] + 'CEPshares.csv'

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
    root = ''
    main(varDict)
