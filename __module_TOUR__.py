# -*- coding: utf-8 -*-
"""
Created on Fri Jan 25 09:35:21 2019

@author: STH
"""

import numpy as np
import pandas as pd
import time
import datetime
import multiprocessing as mp
import shapefile as shp
import functools
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
        self.root.title("Progress Tour Formation")
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

        start_time = time.time()

        root = args[0]
        varDict = args[1]

        if root != '':
            root.progressBar['value'] = 0

        log_file = open(
            varDict['OUTPUTFOLDER'] + "Logfile_TourFormation.log",
            "w")
        log_file.write(
            "Start simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")

        shiftFreightToComb1 = varDict['SHIFT_FREIGHT_TO_COMB1']
        shiftFreightToComb2 = varDict['SHIFT_FREIGHT_TO_COMB2']
        doShiftToElectric = (shiftFreightToComb1 != "")
        doShiftToHydrogen = (shiftFreightToComb2 != "")

        dimNSTR = pd.read_csv(
            varDict['DIMFOLDER'] + 'nstr.txt',
            sep='\t')
        dimLS = pd.read_csv(
            varDict['DIMFOLDER'] + 'logistic_segment.txt',
            sep='\t')
        dimVT = pd.read_csv(
            varDict['DIMFOLDER'] + 'vehicle_type.txt',
            sep='\t')
        dimCombType = pd.read_csv(
            varDict['DIMFOLDER'] + 'combustion_type.txt',
            sep='\t')

        nNSTR = len(dimNSTR) - 1
        nLS = len(dimLS) - 1
        nVT = len(dimVT)
        nCombType = len(dimCombType)

        maxCPU = 16
        if varDict['N_CPU'] not in ['', '""', "''"]:
            try:
                nCPU = int(varDict['N_CPU'])
                if nCPU > mp.cpu_count():
                    nCPU = max(1, min(mp.cpu_count() - 1, maxCPU))
                    message = (
                        'N_CPU parameter too high. Only ' +
                        str(mp.cpu_count()) +
                        ' CPUs available. Hence defaulting to ' +
                        str(nCPU) +
                        'CPUs.')
                    print(message)
                    log_file.write(message + '\n')
                if nCPU < 1:
                    nCPU = max(1, min(mp.cpu_count() - 1, maxCPU))
            except ValueError:
                nCPU = max(1, min(mp.cpu_count() - 1, maxCPU))
                message = (
                    'Could not convert N_CPU parameter to an integer.' +
                    ' Hence defaulting to ' +
                    str(nCPU) +
                    'CPUs.')
                print(message)
                log_file.write(message + '\n')
        else:
            nCPU = max(1, min(mp.cpu_count() - 1, maxCPU))

        # Carrying capacity for each vehicle type
        if varDict['LABEL'] == 'REF':
            carryingCapacity = np.array(pd.read_csv(
                varDict['VEHICLE_CAPACITY'], index_col=0))[:-1, 0]
        elif varDict['LABEL'] == 'UCC':
            # In the UCC scenario we also need to define a capacity
            # for zero emission vehicles, the last one in the list
            carryingCapacity = np.array(pd.read_csv(
                varDict['VEHICLE_CAPACITY'], index_col=0))[:, 0]

        # The number of carriers that transport the shipments not
        # going to or from a DC
        nCarriersNonDC = 100

        # Maximum number of shipments in tour
        maxNumShips = 10

        # Average dwell time at a stop (in hours)
        avgDwellTime = 0.25

        if root != '':
            root.progressBar['value'] = 0.1

        print("Importing shipments and zones...")
        log_file.write("Importing shipments and zones...\n")

        # Import zones
        zones = read_shape(varDict['ZONES'])
        zones = zones.sort_values('AREANR')

        UCCzones = np.unique(zones['UCC_zone'])[1:]

        # Add level of urbanization based on segs (# houses / jobs)
        # and surface (square m)
        segs = pd.read_csv(varDict['SEGS'])
        segs.index = segs['zone']
        zones.index = zones['AREANR']
        zones['HOUSEDENSITY'] = segs['1: woningen'] / zones['area']
        zones['JOBDENSITY'] = segs['9: arbeidspl_totaal'] / zones['area']

        # Approximately highest 10% percentile
        zones['STED'] = (
            (zones['HOUSEDENSITY'] > 0.0075) |
            (zones['JOBDENSITY'] > 0.0050))

        # Clean up zones
        # (remove unnecessary columns and replace NaNs in LOGNODE with 0)
        zones = zones[['AREANR', 'X', 'Y', 'LOGNODE', 'STED', 'ZEZ']]
        zones.loc[pd.isna(zones['LOGNODE']), 'LOGNODE'] = 0
        zones = np.array(zones)

        if root != '':
            root.progressBar['value'] = 0.5

        # Get coordinates of the external zones
        coropCoordinates = pd.read_csv(varDict['SUP_COORDINATES_ID'])
        coropCoordinates.index = np.arange(len(coropCoordinates))

        nSupZones = len(coropCoordinates)
        nIntZones = len(zones)

        zoneDict = dict(np.transpose(np.vstack((
            np.arange(1, nIntZones + 1),
            zones[:, 0]))))
        zoneDict = {int(a): int(b) for a, b in zoneDict.items()}
        for i in range(nSupZones):
            zoneDict[nIntZones + i + 1] = 99999900 + i + 1
        invZoneDict = dict((v, k) for k, v in zoneDict.items())

        # Add external zones to zone matrix
        zones = np.append(zones, np.zeros((nSupZones, zones.shape[1])), axis=0)
        for i in range(nSupZones):
            # ZoneID, X coordinate, Y coordinate
            zones[nIntZones + i][0] = nIntZones + i
            zones[nIntZones + i][1] = coropCoordinates['Xcoor'][i]
            zones[nIntZones + i][2] = coropCoordinates['Ycoor'][i]

            # No logistic node
            zones[nIntZones + i][3] = 0

            # No urbanized zone
            zones[nIntZones + i][4] = False

        # Import logistic nodes data
        logNodes = pd.read_csv(varDict['DISTRIBUTIECENTRA'])
        logNodes = logNodes[~pd.isna(logNodes['AREANR'])]
        logNodes['AREANR'] = [invZoneDict[x] for x in logNodes['AREANR']]
        nDC = len(logNodes)
        logNodes.index = np.arange(nDC)
        dcZones = np.array(logNodes['AREANR'])

        # Import shipments data
        shipments = pd.read_csv(
            varDict['OUTPUTFOLDER'] + f"Shipments_{varDict['LABEL']}.csv")

        if root != '':
            root.progressBar['value'] = 1.0

        # Import ZEZ scenario input
        if varDict['LABEL'] == 'UCC':
            # Vehicle/combustion shares (for UCC scenario)
            sharesUCC = pd.read_csv(
                varDict['ZEZ_SCENARIO'],
                index_col='Segment')

            # Assume no consolidation potential and vehicle type switch
            # for dangerous goods
            sharesUCC = np.array(sharesUCC)[:-1, :-1]

            # Combustion type shares per vehicle type and logistic segment
            cumProbCombustion = [
                np.zeros((nLS, nCombType), dtype=float)
                for vt in range(nVT)]

            for ls in range(nLS - 1):

                # Truck_Small, Truck_Medium, Truck_Large
                # TruckTrailer_Small, TruckTrailer_Large
                if np.all(sharesUCC[ls, 15:20] == 0):
                    for vt in range(5):
                        cumProbCombustion[vt][ls] = (
                            np.ones((1, nCombType)))
                else:
                    for vt in range(5):
                        cumProbCombustion[vt][ls] = (
                            np.cumsum(sharesUCC[ls, 15:20]) /
                            np.sum(sharesUCC[ls, 15:20]))

                # TractorTrailer
                if np.all(sharesUCC[ls, 20:25] == 0):
                    cumProbCombustion[5][ls] = np.ones((1, nCombType))
                else:
                    cumProbCombustion[5][ls] = (
                        np.cumsum(sharesUCC[ls, 20:25]) /
                        np.sum(sharesUCC[ls, 20:25]))

                # SpecialVehicle
                if np.all(sharesUCC[ls, 30:35] == 0):
                    cumProbCombustion[6][ls] = np.ones((1, nCombType))
                else:
                    cumProbCombustion[6][ls] = (
                        np.cumsum(sharesUCC[ls, 30:35]) /
                        np.sum(sharesUCC[ls, 30:35]))

                # Van
                if np.all(sharesUCC[ls, 10:15] == 0):
                    cumProbCombustion[7][ls] = np.ones((1, nCombType))
                else:
                    cumProbCombustion[7][ls] = (
                        np.cumsum(sharesUCC[ls, 10:15]) /
                        np.sum(sharesUCC[ls, 10:15]))

                # LEVV
                if np.all(sharesUCC[ls, 0:5] == 0):
                    cumProbCombustion[8][ls] = np.ones((1, nCombType))
                else:
                    cumProbCombustion[8][ls] = (
                        np.cumsum(sharesUCC[ls, 0:5]) /
                        np.sum(sharesUCC[ls, 0:5]))

                # Moped
                if np.all(sharesUCC[ls, 5:10] == 0):
                    cumProbCombustion[9][ls] = np.ones((1, nCombType))
                else:
                    cumProbCombustion[9][ls] = (
                        np.cumsum(sharesUCC[ls, 5:10]) /
                        np.sum(sharesUCC[ls, 5:10]))

                # Waste: SpecialVehicle
                if ls == 5:
                    cumProbCombustion[6][ls] = (
                        np.cumsum(sharesUCC[ls, 25:30]) /
                        np.sum(sharesUCC[ls, 25:30]))

        print("Preparing shipments for tour formation...")
        log_file.write("Preparing shipments for tour formation...\n")

        shipments['ORIG'] = [invZoneDict[x] for x in shipments['ORIG']]
        shipments['DEST'] = [invZoneDict[x] for x in shipments['DEST']]
        shipments['WEIGHT'] *= 1000

        # Is the shipment loaded at a distribution center?
        shipments['LOGNODE_LOADING'] = 0
        isLoadDC = (shipments['SEND_DC'] != -99999)
        isLoadTT = ((zones[shipments['ORIG'] - 1][:, 3] == 1) &
                    (shipments['SEND_DC'] == -99999))
        shipments.loc[isLoadDC, 'LOGNODE_LOADING'] = 2
        shipments.loc[isLoadTT, 'LOGNODE_LOADING'] = 1

        # Is the shipment UNloaded at a distribution center?
        shipments['LOGNODE_UNLOADING'] = 0
        isReceiveDC = (shipments['RECEIVE_DC'] != -99999)
        isReceiveTT = ((zones[shipments['DEST'] - 1][:, 3] == 1) &
                       (shipments['RECEIVE_DC'] == -99999))
        shipments.loc[isReceiveDC, 'LOGNODE_UNLOADING'] = 2
        shipments.loc[isReceiveTT, 'LOGNODE_LOADING'] = 1

        # Is the loading or unloading point in an urbanized region?
        shipments['URBAN'] = (
            (zones[shipments['ORIG'] - 1][:, 4]) |
            (zones[shipments['DEST'] - 1][:, 4]))

        # Determine the carrier ID for each shipment
        # Shipments are first grouped by DC
        # (one carrier per DC assumed, carrierID = 0 to nDC)
        shipments['CARRIER'] = 0
        whereLoadDC = shipments['SEND_DC'] != -99999
        whereUnloadDC = shipments['RECEIVE_DC'] != -99999

        # Shipments not loaded or unloaded at DC are randomly assigned
        # to the other carriers, carrierID = nDC to nDC + nCarriersNonDC]
        whereBothDC = (whereLoadDC) & (whereUnloadDC)
        whereNoDC = ~(whereLoadDC) & ~(whereUnloadDC)

        shipments.loc[whereLoadDC, 'CARRIER'] = (
            shipments['SEND_DC'][whereLoadDC])
        shipments.loc[whereUnloadDC, 'CARRIER'] = (
            shipments['RECEIVE_DC'][whereUnloadDC])
        shipments.loc[whereBothDC, 'CARRIER'] = [
            [shipments['SEND_DC'][i], shipments['RECEIVE_DC'][i]][
                np.random.randint(0, 2)]
            for i in shipments.loc[whereBothDC, :].index]
        shipments.loc[whereNoDC, 'CARRIER'] = (
            nDC + np.random.randint(0, nCarriersNonDC, np.sum(whereNoDC)))

        if root != '':
            root.progressBar['value'] = 2.0

        # Extra carrierIDs for shipments transported from
        # Urban Consolidation Centers
        if varDict['LABEL'] == 'UCC':
            whereToUCC = np.where(shipments['TO_UCC'] == 1)[0]
            whereFromUCC = np.where(shipments['FROM_UCC'] == 1)[0]

            ZEZzones = set(zones[zones[:, 5] >= 1, 0])

            for i in whereToUCC:
                if zoneDict[shipments['ORIG'][i]] in ZEZzones:
                    shipments.loc[i, 'CARRIER'] = (
                        nDC +
                        nCarriersNonDC +
                        np.where(UCCzones == zoneDict[shipments['DEST'][i]])[0]
                    )

            for i in whereFromUCC:
                if zoneDict[shipments['DEST'][i]] in ZEZzones:
                    shipments.loc[i, 'CARRIER'] = (
                        nDC +
                        nCarriersNonDC +
                        np.where(UCCzones == zoneDict[shipments['ORIG'][i]])[0]
                    )

        shipments = shipments[['SHIP_ID', 'ORIG', 'DEST', 'CARRIER',
                               'VEHTYPE', 'NSTR', 'WEIGHT',
                               'LOGNODE_LOADING', 'LOGNODE_UNLOADING',
                               'URBAN', 'LS',
                               'SEND_FIRM', 'RECEIVE_FIRM',
                               'TOD_PERIOD', 'TOD_LOWER', 'TOD_UPPER']]
        shipments = np.array(shipments)

        # Divide shipments that are larger than the vehicle capacity
        # into multiple shipments
        weight = shipments[:, 6]
        vehicleType = shipments[:, 4]
        capacityExceedence = np.array([
            weight[i] / carryingCapacity[int(vehicleType[i])]
            for i in range(len(shipments))])
        whereCapacityExceeded = np.where(capacityExceedence > 1)[0]
        nNewShipmentsTotal = int(np.sum(np.ceil(
            capacityExceedence[whereCapacityExceeded])))

        newShipments = np.zeros((nNewShipmentsTotal, shipments.shape[1]))

        count = 0
        for i in whereCapacityExceeded:
            nNewShipments = int(np.ceil(capacityExceedence[i]))
            newWeight = weight[i] / nNewShipments
            newShipment = shipments[i, :].copy()
            newShipment[6] = newWeight

            for n in range(nNewShipments):
                newShipments[count, :] = newShipment
                count += 1

        shipments = np.append(shipments, newShipments, axis=0)
        shipments = np.delete(shipments, whereCapacityExceeded, axis=0)
        shipments[:, 0] = np.arange(len(shipments))
        shipments = shipments.astype(int)

        # Sort shipments by carrierID
        shipments = shipments[shipments[:, 3].argsort()]
        shipmentDict = dict(np.transpose(np.vstack((
            np.arange(len(shipments)),
            shipments[:, 0].copy()))))

        # Give the shipments a new shipmentID after orderingthe array
        # by carrierID
        shipments[:, 0] = np.arange(len(shipments))

        if root != '':
            root.progressBar['value'] = 2.5

        print('Importing skims...')
        log_file.write('Importing skims...\n')

        # Import binary skim files
        skimTravTime = read_mtx(varDict['SKIMTIME'])
        skimAfstand = read_mtx(varDict['SKIMDISTANCE'])
        nZones = int(len(skimTravTime)**0.5)

        # For zero times and distances assume half the value to the
        # nearest (non-zero) zone
        for orig in range(nZones):

            whereZero = np.where(
                skimTravTime[orig * nZones + np.arange(nZones)] == 0)[0]
            whereNonZero = np.where(
                skimTravTime[orig * nZones + np.arange(nZones)] != 0)[0]

            skimTravTime[orig * nZones + whereZero] = (
                0.5 * np.min(skimTravTime[orig * nZones + whereNonZero]))
            skimAfstand[orig * nZones + whereZero] = (
                0.5 * np.min(skimAfstand[orig * nZones + whereNonZero]))

        # Concatenate time and distance arrays as a 2-column matrix
        skim = np.array(np.c_[skimTravTime, skimAfstand], dtype=int)

        if root != '':
            root.progressBar['value'] = 4.0

        print('Importing logit parameters...')
        log_file.write('Importing logit parameters...\n')

        logitParams_ETfirst = np.array(pd.read_csv(
            varDict['PARAMS_ET_FIRST'],
            index_col=0))[:, 0]
        logitParams_ETlater = np.array(pd.read_csv(
            varDict['PARAMS_ET_LATER'],
            index_col=0))[:, 0]

        paramsTOD = pd.read_csv(varDict['PARAMS_TOD'], index_col=0)
        nTOD = len([
            x for x in paramsTOD.index
            if x.split('_')[0] == 'Interval'])

        print('Obtaining other information required before tour formation...')
        log_file.write(
            'Obtaining other information required before tour formation...\n')

        # Total number of shipments and carriers
        nShipments = len(shipments)
        nCarriers = len(np.unique(shipments[:, 3]))

        # At which index is the first shipment of each carrier
        carmarkers = [0]
        for i in range(1, nShipments):
            if shipments[i, 3] != shipments[i - 1, 3]:
                carmarkers.append(i)
        carmarkers.append(nShipments)

        # How many shipments does each carrier have?
        nShipmentsPerCarrier = [None for car in range(nCarriers)]
        if nCarriers == 1:
            nShipmentsPerCarrier[0] = nShipments
        else:
            for i in range(nCarriers):
                nShipmentsPerCarrier[i] = carmarkers[i + 1] - carmarkers[i]

        print(f'Start tour formation (parallelized over {nCPU} cores)')
        log_file.write(
            f'Start tour formation (parallelized over {nCPU} cores)\n')

        # Initialization of lists with information regarding tours
        # tours:         here we store the shipmentIDs of each tour
        # tourSequences: here we store the order of (un)loading locations
        #                of each tour
        # nTours:        number of tours constructed for each carrier
        tours = [
            [np.zeros(1, dtype=int)
                for ship in range(nShipmentsPerCarrier[car])]
            for car in range(nCarriers)]
        tourSequences = [
            [np.zeros(nShipmentsPerCarrier[car], dtype=int)
                for ship in range(nShipmentsPerCarrier[car])]
            for car in range(nCarriers)]
        nTours = np.zeros(nCarriers)

        if root != '':
            root.progressBar['value'] = 5.0

        # Bepaal het aantal CPUs dat we gebruiken en welke CPU
        # welke carriers doet
        chunks = [np.arange(nCarriers)[i::nCPU] for i in range(nCPU)]

        # Initialiseer een pool object dat de taken verdeelt over de CPUs
        p = mp.Pool(nCPU)

        # Voer de tourformatie uit
        tourformationResult = p.map(functools.partial(
            tourformation,
            carmarkers,
            shipments,
            skim,
            nZones,
            maxNumShips,
            carryingCapacity,
            dcZones,
            nShipmentsPerCarrier,
            nCarriers,
            nTOD,
            nNSTR,
            logitParams_ETfirst,
            logitParams_ETlater), chunks)

        if root != '':
            root.progressBar['value'] = 80.0

        # Pak de tourformatieresultaten uit
        for cpu in range(nCPU):
            for car in chunks[cpu]:
                tours[car], tourSequences[car], nTours[car] = (
                    tourformationResult[cpu][0][car],
                    tourformationResult[cpu][1][car],
                    tourformationResult[cpu][2][car])

        # Wait for completion of parallellization processes
        p.close()
        p.join()

        nTours = nTours.astype(int)

        print('\tTour formation completed for all carriers')
        log_file.write('\tTour formation completed for all carriers\n')

        if root != '':
            root.progressBar['value'] = 81.0

        print('Adding empty trips...')
        log_file.write('Adding empty trips...\n')

        # Add empty trips
        emptytripadded = [
            [None for tour in range(nTours[car])]
            for car in range(nCarriers)]

        for car in range(nCarriers):
            for tour in range(nTours[car]):
                tourSequences[car][tour] = [
                    x for x in tourSequences[car][tour] if x != 0]

                # If tour does not end at start location
                if tourSequences[car][tour][0] != tourSequences[car][tour][-1]:
                    tourSequences[car][tour].append(
                        tourSequences[car][tour][0])
                    emptytripadded[car][tour] = True
                else:
                    emptytripadded[car][tour] = False

        if root != '':
            root.progressBar['value'] = 82.0

        print('Obtaining number of shipments and trip weights...')
        log_file.write('Obtaining number of shipments and trip weights...\n')

        # Number of shipments and trips of each tour
        nShipmentsPerTour = [
            [len(tours[car][tour]) for tour in range(nTours[car])]
            for car in range(nCarriers)]
        nTripsPerTour = [
            [len(tourSequences[car][tour]) - 1 for tour in range(nTours[car])]
            for car in range(nCarriers)]
        nTripsTotal = np.sum(np.sum(nTripsPerTour))

        # Weight per trip
        tripWeights = [
            [np.zeros(nTripsPerTour[car][tour], dtype=int)
                for tour in range(nTours[car])]
            for car in range(nCarriers)]

        # Time windows of arrival at the destination of each trip
        tripLowerWindow = [
            [-1 * np.ones(nTripsPerTour[car][tour], dtype=int)
                for tour in range(nTours[car])]
            for car in range(nCarriers)]
        tripUpperWindow = [
            [1000 * np.ones(nTripsPerTour[car][tour], dtype=int)
                for tour in range(nTours[car])]
            for car in range(nCarriers)]

        for car in range(nCarriers):
            for tour in range(nTours[car]):

                nShipsThisTour = nShipmentsPerTour[car][tour]
                shipmentIsLoaded = [False for i in range(nShipsThisTour)]
                shipmentIsUnloaded = [False for i in range(nShipsThisTour)]
                
                timeOfDayPeriodsInTour = np.unique(shipments[
                    tours[car][tour], 13])
                tourPastMidnight = (
                    0 in timeOfDayPeriodsInTour and
                    (nTOD - 1) in timeOfDayPeriodsInTour)

                for trip in range(nTripsPerTour[car][tour]):
                    # Startzone of trip
                    orig = tourSequences[car][tour][trip]

                    # If it's the first trip of the tour,
                    # then initialize a counter to add and subtract weight from
                    if trip == 0:
                        tmpTripWeight = 0

                    for i in range(nShipsThisTour):
                        ship = tours[car][tour][i]

                        # If loading location of the shipment was the
                        # startpoint of the trip and shipment has not been
                        # loaded/unloaded yet
                        addWeightToTrip = (
                            shipments[ship][1] == orig and not
                            (shipmentIsLoaded[i] or shipmentIsUnloaded[i]))

                        # Add weight of shipment to counter
                        if addWeightToTrip:
                            tmpTripWeight += shipments[ship][6]
                            shipmentIsLoaded[i] = True

                        # If unloading location of the shipment was the
                        # startpoint of the trip and shipment has not been
                        # unloaded yet
                        subtractWeightFromTrip = (
                            shipments[ship][2] == orig and
                            shipmentIsLoaded[i] and not
                            shipmentIsUnloaded[i])

                        # Remove weight of shipment from counter
                        # and update delivery time window
                        if subtractWeightFromTrip:
                            tmpTripWeight -= shipments[ship][6]
                            shipmentIsUnloaded[i] = True

                            shipPeriod = shipments[ship][13]
                            shipLower = shipments[ship][14]
                            shipUpper = shipments[ship][15]
                            tripLower = tripLowerWindow[car][tour][trip]
                            tripUpper = tripUpperWindow[car][tour][trip]
                            
                            if shipPeriod == 0 and tourPastMidnight:
                                shipLower += 24
                                shipUpper += 24

                            # Update lower end of delivery time window
                            if tripLower < 0 or shipLower < tripLower:
                                tripLowerWindow[car][tour][trip] = shipLower

                            # Update upper end of delivery time window
                            if tripUpper > 999 or shipUpper > tripUpper:
                                tripUpperWindow[car][tour][trip] = shipUpper

                    tripWeights[car][tour][trip] = tmpTripWeight

        if root != '':
            root.progressBar['value'] = 84.0

        print('Determining departure times...')
        log_file.write('Determining departure times...\n')

        # Initialize arrays for departure time of each tour
        depTimeTour = [
            [None for tour in range(nTours[car])]
            for car in range(nCarriers)]

        # Initialize arrays for departure and arrival time of each trip
        depTimeTrip = [
            [np.zeros(nTripsPerTour[car][tour])
                for tour in range(nTours[car])]
            for car in range(nCarriers)]
        arrTimeTrip = [
            [np.zeros(nTripsPerTour[car][tour])
                for tour in range(nTours[car])]
            for car in range(nCarriers)]

        for car in range(nCarriers):
            for tour in range(nTours[car]):
                tmpTimeEarly = [None for i in range(nTripsPerTour[car][tour])]
                tmpTimeLate = [None for i in range(nTripsPerTour[car][tour])]

                # Get initial deviation from time windows if the tour were to
                # depart at 00:00 midnight
                for trip in range(nTripsPerTour[car][tour]):
                    # Travel time to destination of the current trip
                    travTime = get_traveltime(
                        tourSequences[car][tour][trip],
                        tourSequences[car][tour][trip + 1],
                        skim,
                        nZones)
                    
                    # Time spent at the destination of the current trip
                    dwellTime = avgDwellTime * 2 * np.random.rand()

                    # Arrival time at the destination of the current trip
                    tmpArrTimeTrip = (
                        depTimeTrip[car][tour][trip] +
                        travTime)
                    arrTimeTrip[car][tour][trip] = tmpArrTimeTrip

                    # Departure time from the destination of the current trip
                    if (trip + 1) < nTripsPerTour[car][tour]:
                        depTimeTrip[car][tour][trip + 1] = (
                            tmpArrTimeTrip + dwellTime)

                    if tripLowerWindow[car][tour][trip] > -1:
                        tmpTimeEarly[trip] = (
                            tripLowerWindow[car][tour][trip] -
                            tmpArrTimeTrip)

                    if tripUpperWindow[car][tour][trip] < 1000:
                        tmpTimeLate[trip] = (
                            tripUpperWindow[car][tour][trip] -
                            tmpArrTimeTrip)

                # Determine the optimal tour departure time
                # (minimal deviation from time windows)
                tmpTimeEarly = [x for x in tmpTimeEarly if x is not None]
                tmpTimeLate = [x for x in tmpTimeLate if x is not None]
                avgTimeEarly = (
                    np.average(tmpTimeEarly) if len(tmpTimeEarly) > 0 else 0.0)
                avgTimeLate = (
                    np.average(tmpTimeLate) if len(tmpTimeLate) > 0 else 0.0)

                depTimeTour[car][tour] = np.average([avgTimeEarly, avgTimeLate])

                if depTimeTour[car][tour] < 0:
                    depTimeTour[car][tour] += 24

                # Update the trip departure and arrival times based on this
                # tour departure time
                depTimeTrip[car][tour] += depTimeTour[car][tour]
                arrTimeTrip[car][tour] += depTimeTour[car][tour]

        if root != '':
            root.progressBar['value'] = 85.0

        print('Determining combustion type of tours...')
        log_file.write('Determining combustion type of tours...\n')

        combTypeTour = [
            [None for tour in range(nTours[car])]
            for car in range(nCarriers)]

        if varDict['LABEL'] == 'UCC':
            ZEZzones = set(zones[zones[:, 5] >= 1, 0])

            for car in range(nCarriers):
                for tour in range(nTours[car]):

                    # Combustion type for tours from/to UCCs
                    if car >= nDC + nCarriersNonDC:
                        ls = shipments[tours[car][tour][0], 10]
                        vt = shipments[tours[car][tour][0], 4]
                        combTypeTour[car][tour] = np.where(
                            cumProbCombustion[vt][ls, :] > np.random.rand()
                        )[0][0]

                    else:
                        inZEZ = [
                            zoneDict[x] in ZEZzones
                            for x in np.unique(tourSequences[car][tour])
                            if x != 0]

                        # Combustion type for tours within ZEZ
                        # (but not from/to UCCs)
                        if np.all(inZEZ):
                            combTypeTour[car][tour] = np.where(
                                cumProbCombustion[vt][ls, :] >
                                np.random.rand())[0][0]

                        # Hybrids for tours directly entering/leaving the ZEZ
                        elif np.any(inZEZ):
                            combTypeTour[car][tour] = 3

                        # Fuel for all other tours that do not go to the ZEZ
                        else:
                            combTypeTour[car][tour] = 0

        # In the not-UCC scenario everything is assumed to be fuel
        if varDict['LABEL'] == 'REF':
            for car in range(nCarriers):
                for tour in range(nTours[car]):
                    combTypeTour[car][tour] = 0

        # Unless the shift-to-electric or shift-to-hydrogen
        # parameter is set (SHIFT_FREIGHT_TO_COMB1 or _COMB2)
        if doShiftToElectric or doShiftToHydrogen:
            for car in range(nCarriers):
                for tour in range(nTours[car]):
                    if doShiftToElectric:
                        if np.random.rand() <= shiftFreightToComb1:
                            combTypeTour[car][tour] = 1
                    if doShiftToHydrogen:
                        if combTypeTour[car][tour] != 1:
                            if np.random.rand() <= shiftFreightToComb2:
                                combTypeTour[car][tour] = 2

        if root != '':
            root.progressBar['value'] = 86.0

        # ---------------------------- Create Tours CSV ----------------------

        print('Writing tour data to CSV...')
        log_file.write('Writing tour data to CSV...\n')

        outputTours = np.zeros((nTripsTotal, 20), dtype=object)
        tripcount = 0

        for car in range(nCarriers):
            for tour in range(nTours[car]):
                for trip in range(nTripsPerTour[car][tour]):

                    # CarrierID, tourID, tripID
                    outputTours[tripcount][0] = car
                    outputTours[tripcount][1] = tour
                    outputTours[tripcount][2] = trip

                    # Origin and destination zone number
                    outputTours[tripcount][[3, 4]] = (
                        zoneDict[tourSequences[car][tour][trip]],
                        zoneDict[tourSequences[car][tour][trip + 1]])

                    # X coordinates of origin and destination
                    outputTours[tripcount][[5, 6]] = (
                        zones[tourSequences[car][tour][trip] - 1][1],
                        zones[tourSequences[car][tour][trip + 1] - 1][1])

                    # Y coordinates of origin and destination
                    outputTours[tripcount][[7, 8]] = (
                        zones[tourSequences[car][tour][trip] - 1][2],
                        zones[tourSequences[car][tour][trip + 1] - 1][2])

                    # Vehicle type
                    outputTours[tripcount][9] = (
                        shipments[tours[car][tour][0], 4])

                    # Dominant NSTR goods type (by weight)
                    outputTours[tripcount][10] = max_nstr(
                        tours[car][tour],
                        shipments,
                        nNSTR)

                    # Number of shipments transported in tour
                    outputTours[tripcount][11] = nShipmentsPerTour[car][tour]

                    # ID for DC zones
                    outputTours[tripcount][12] = (
                        zoneDict[dcZones[outputTours[tripcount][0]]]
                        if car < nDC else -99999)

                    # Weight: sum of tour and for individual trip
                    outputTours[tripcount][13] = sum_weight(
                        tours[car][tour],
                        shipments)
                    outputTours[tripcount][14] = (
                        tripWeights[car][tour][trip] / 1000)

                    # Departure time of the tour
                    outputTours[tripcount][15] = depTimeTour[car][tour]

                    # Departure and arrival time of the trip
                    outputTours[tripcount][16] = depTimeTrip[car][tour][trip]
                    outputTours[tripcount][17] = arrTimeTrip[car][tour][trip]

                    # Logistic segment of tour
                    outputTours[tripcount][18] = (
                        shipments[tours[car][tour][0], 10])

                    # Combustion type of the vehicle
                    outputTours[tripcount][19] = combTypeTour[car][tour]

                    tripcount += 1

                # NSTR of empty trips is -1
                if emptytripadded[car][tour]:
                    outputTours[tripcount - 1][10] = -1

        nTripsTotal = tripcount

        if root != '':
            root.progressBar['value'] = 87.0

        # Create DataFrame object for easy formatting and exporting to csv
        columns = [
            "CARRIER_ID", "TOUR_ID", "TRIP_ID",
            "ORIG", "DEST",
            "X_ORIG", "X_DEST", "Y_ORIG", "Y_DEST",
            "VEHTYPE",
            "NSTR",
            "N_SHIP",
            "DC_ID",
            "TOUR_WEIGHT", "TRIP_WEIGHT",
            "TOUR_DEPTIME", "TRIP_DEPTIME", "TRIP_ARRTIME",
            "LS",
            "COMBTYPE"]
        dTypes = [
            str, str, str,
            int, int,
            float, float,  float,  float,
            int,
            int,
            int,
            int,
            float, float,
            int, float, float,
            int,
            int]

        outputTours = pd.DataFrame(outputTours, columns=columns)
        for i in range(len(outputTours.columns)):
            outputTours.iloc[:, i] = outputTours.iloc[:, i].astype(dTypes[i])

        outputTours.to_csv(
            f"{varDict['OUTPUTFOLDER']}Tours_{varDict['LABEL']}.csv",
            index=None,
            header=True)
        message = (
            "CSV written to " +
            str(varDict['OUTPUTFOLDER']) +
            f"Tours_{varDict['LABEL']}.csv")
        print(message)
        log_file.write(message + "\n")

        if root != '':
            root.progressBar['value'] = 89.0

        # ----------------------- Enrich Shipments CSV ------------------------

        print('Enriching Shipments CSV...')
        log_file.write('Enriching Shipments CSV...\n')

        shipmentTourID = {}
        for car in range(nCarriers):
            for tour in range(nTours[car]):
                for ship in range(len(tours[car][tour])):
                    shipID = tours[car][tour][ship]
                    shipmentTourID[shipmentDict[shipID]] = f'{car}_{tour}'

        # Add TOUR_ID to shipments csv and export again
        shipments = pd.DataFrame(shipments)
        shipments.columns = [
            'SHIP_ID',
            'ORIG', 'DEST',
            'CARRIER',
            'VEHTYPE',
            'NSTR',
            'WEIGHT',
            'LOGNODE_LOADING', 'LOGNODE_UNLOADING',
            'URBAN',
            'LS',
            'SEND_FIRM', 'RECEIVE_FIRM',
            'TOD_PERIOD', 'TOD_LOWER', 'TOD_UPPER']

        shipments['SHIP_ID'] = [
            shipmentDict[x] for x in shipments['SHIP_ID']]
        shipments['TOUR_ID'] = [
            shipmentTourID[x] for x in shipments['SHIP_ID']]
        shipments['ORIG'] = [zoneDict[x] for x in shipments['ORIG']]
        shipments['DEST'] = [zoneDict[x] for x in shipments['DEST']]
        shipments['WEIGHT'] /= 1000

        selectCols = [
            'SHIP_ID',
            'ORIG', 'DEST',
            'CARRIER',
            'VEHTYPE',
            'NSTR',
            'WEIGHT',
            'LS',
            'TOUR_ID',
            'SEND_FIRM', 'RECEIVE_FIRM',
            'TOD_PERIOD']
        shipments = shipments[selectCols]
        shipments = shipments.sort_values('SHIP_ID')
        filename = (
            varDict['OUTPUTFOLDER'] +
            "Shipments_AfterScheduling_" +
            varDict['LABEL'] +
            '.csv')
        shipments.to_csv(
            filename,
            index=False)

        if root != '':
            root.progressBar['value'] = 90.0

        # -------------------------- Write GeoJSON ----------------------------

        print('Writing Shapefile...'), log_file.write('Writing Shapefile...\n')

        percStart = 90.0
        percEnd = 97.0

        Ax = list(outputTours['X_ORIG'])
        Ay = list(outputTours['Y_ORIG'])
        Bx = list(outputTours['X_DEST'])
        By = list(outputTours['Y_DEST'])

        # Initialize shapefile fields
        w = shp.Writer(
            varDict['OUTPUTFOLDER'] +
            'Tours_' +
            varDict['LABEL'] +
            '.shp')
        w.field('CARRIER_ID',   'N', size=5, decimal=0)
        w.field('TOUR_ID',      'N', size=5, decimal=0)
        w.field('TRIP_ID',      'N', size=3, decimal=0)
        w.field('ORIG',         'N', size=8, decimal=0)
        w.field('DEST',         'N', size=8, decimal=0)
        w.field('VEHTYPE',      'N', size=2, decimal=0)
        w.field('NSTR',         'N', size=2, decimal=0)
        w.field('N_SHIP',       'N', size=3, decimal=0)
        w.field('DC_ID',        'N', size=8, decimal=0)
        w.field('TOUR_WEIGHT',  'N', size=5, decimal=2)
        w.field('TRIP_WEIGHT',  'N', size=5, decimal=2)
        w.field('TOUR_DEPTIME', 'N', size=4, decimal=2)
        w.field('TRIP_DEPTIME', 'N', size=5, decimal=2)
        w.field('TRIP_ARRTIME', 'N', size=5, decimal=2)
        w.field('LS',           'N', size=2, decimal=0)
        w.field('COMBTYPE',     'N', size=2, decimal=0)

        dbfData = np.array(
            outputTours.drop(columns=[
                'X_ORIG', 'Y_ORIG',
                'X_DEST', 'Y_DEST']),
            dtype=object)

        for i in range(nTripsTotal):
            # Add geometry
            w.line([[
                [Ax[i], Ay[i]],
                [Bx[i], By[i]]]])

            # Add data fields
            w.record(*dbfData[i, :])

            if i % 500 == 0:
                print('\t' + str(round(i / nTripsTotal * 100, 1)) + '%',
                      end='\r')

                if root != '':
                    root.progressBar['value'] = (
                        percStart +
                        (percEnd - percStart) * i / nTripsTotal)

        w.close()

        message = (
            'Tours written to ' +
            varDict['OUTPUTFOLDER'] +
            'Tours_' +
            varDict['LABEL'] +
            '.shp')
        print(message)
        log_file.write(message + '\n')

        # ----------- Create trip matrices for traffic assignment -------------

        print('Generating trip matrix...')
        log_file.write('Generating trip matrix...\n')

        cols = ['ORIG', 'DEST',
                'N_LS0', 'N_LS1', 'N_LS2', 'N_LS3',
                'N_LS4', 'N_LS5', 'N_LS6', 'N_LS7',
                'N_VEH0', 'N_VEH1', 'N_VEH2', 'N_VEH3', 'N_VEH4',
                'N_VEH5', 'N_VEH6', 'N_VEH7', 'N_VEH8', 'N_VEH9',
                'N_TOT']

        # Maak dummies in tours variabele per logistiek segment,
        # voertuigtype en N_TOT (altijd 1 hier)
        for ls in range(nLS):
            outputTours['N_LS' + str(ls)] = (
                outputTours['LS'] == ls).astype(int)
        for vt in range(nVT):
            outputTours['N_VEH' + str(vt)] = (
                outputTours['VEHTYPE'] == vt).astype(int)
        outputTours['N_TOT'] = 1

        # Gebruik deze dummies om het aantal ritten per HB te bepalen
        # voor elk logistiek segment, voertuigtype en totaal
        pivotTable = pd.pivot_table(
            outputTours,
            values=cols[2:],
            index=['ORIG', 'DEST'],
            aggfunc=np.sum)
        pivotTable['ORIG'] = [x[0] for x in pivotTable.index]
        pivotTable['DEST'] = [x[1] for x in pivotTable.index]
        pivotTable = pivotTable[cols]

        pivotTable.to_csv(
            varDict['OUTPUTFOLDER'] + f"tripmatrix_{varDict['LABEL']}.txt",
            index=False,
            sep='\t')

        message = (
            "Trip matrix written to " +
            str(varDict['OUTPUTFOLDER']) +
            "tripmatrix_" +
            str(varDict['LABEL']) +
            ".txt")
        print(message)
        log_file.write(message + '\n')

        if root != '':
            root.progressBar['value'] = 98.0

        tours = pd.read_csv(
            varDict['OUTPUTFOLDER'] + f"Tours_{varDict['LABEL']}.csv")
        tours.loc[tours['TRIP_DEPTIME'] > 24, 'TRIP_DEPTIME'] -= 24
        tours.loc[tours['TRIP_DEPTIME'] > 24, 'TRIP_DEPTIME'] -= 24

        for tod in range(24):

            print(f'\t Also generating trip matrix for TOD {tod}...')
            log_file.write(
                f'\t Also generating trip matrix for TOD {tod}...\n')

            output = tours[
                (tours['TRIP_DEPTIME'] >= tod) &
                (tours['TRIP_DEPTIME'] < tod + 1)].copy()

            # Maak dummies in tours variabele
            # per logistiek segment, voertuigtypeen N_TOT (altijd 1 hier)
            for ls in range(nLS):
                output['N_LS' + str(ls)] = (
                    output['LS'] == ls).astype(int)
            for vt in range(nVT):
                output['N_VEH' + str(vt)] = (
                    output['VEHTYPE'] == vt).astype(int)
            output['N_TOT'] = 1

            # Gebruik deze dummies om het aantal ritten per HB te bepalen
            # voor elk logistiek segment, voertuigtype en totaal
            pivotTable = pd.pivot_table(
                output,
                values=cols[2:],
                index=['ORIG', 'DEST'],
                aggfunc=np.sum)
            pivotTable['ORIG'] = [x[0] for x in pivotTable.index]
            pivotTable['DEST'] = [x[1] for x in pivotTable.index]
            pivotTable = pivotTable[cols]

            filename = (
                str(varDict['OUTPUTFOLDER']) +
                "tripmatrix_" +
                str(varDict['LABEL']) +
                "_TOD" +
                str(tod) +
                ".txt")
            pivotTable.to_csv(filename, index=False, sep='\t')

            if root != '':
                root.progressBar['value'] = (
                    98.0 +
                    (100.0 - 98.0) * (tod + 1) / 24)

        # ------------------------- End of module -----------------------------

        totaltime = round(time.time() - start_time, 2)
        print('Finished. Run time: ' + str(totaltime) + ' seconds')
        log_file.write("Total runtime: %s seconds\n" % (totaltime))
        log_file.write(
            "End simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")
        log_file.close()

        if root != '':
            root.update_statusbar("Tour Formation: Done")
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
                root.update_statusbar("Tour Formation: Execution failed!")
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


#%% Other functions


def get_traveltime(orig, dest, skim, nZones):
    '''
    Obtain the travel time [h] for orig to a destination zone.
    '''
    return skim[(orig - 1) * nZones + (dest - 1)][0] / 3600


def get_distance(orig, dest, skim, nZones):
    '''
    Obtain the distance [km] for orig to a destination zone.
    '''
    return skim[(orig - 1) * nZones + (dest - 1)][1] / 1000


def nearest_neighbor(ships, TODs, dc, skim, nZones, nTOD):
    '''
    Creates a tour sequence to visit all loading and unloading locations.
    First a nearest-neighbor search is applied,then a 2-opt posterior
    improvement phase.

    ships = array with loading locations of shipments in column 0,
        and unloading locations in column 1
    dc = zone ID of the DC in case the carrier is located in a DC zone
    '''
    # ------------------------ Initialization -------------------------------
    # Arrays of unique loading and unloading locations to be visited
    loading = np.unique(ships[:, 0])
    unloading = np.unique(ships[:, 1])

    # Total number of loading and unloading locations to visit
    nLoad = len(loading)
    nUnload = len(unloading)

    # Here we will store the sequence of locations
    tourSequence = np.zeros(nLoad + nUnload, dtype=int)

    # Codes of the first and last period of a day
    firstCategoryTOD = 0
    lastCategoryTOD = (nTOD - 1)

    # Earliest and latest time-of-day in the tour
    if (firstCategoryTOD in TODs) and (lastCategoryTOD in TODs):
        firstTourTOD = lastCategoryTOD
        lastTourTOD = firstCategoryTOD
    else:
        firstTourTOD = np.min(TODs)
        lastTourTOD = np.max(TODs)
    allSameTOD = (firstTourTOD == lastTourTOD)

    # Which zones need to be visited in the earliest time-of-day of the tour
    unloadingFirstTOD = np.unique([
        ships[i, 1] for i in range(len(ships))
        if TODs[i] == firstTourTOD])
    nUnloadFirstTOD = len(unloadingFirstTOD)

    # Which zones need to be visited in the last time-of-day of the tour
    if not allSameTOD:
        unloadingLastTOD = np.unique([
            ships[i, 1] for i in range(len(ships))
            if TODs[i] == lastTourTOD and ships[i, 1] not in unloadingFirstTOD])
        nUnloadLastTOD = len(unloadingLastTOD)

    # ----------------------- Loading sequence -------------------------------
    # First visited location = first listed location
    tourSequence[0] = ships[0, 0]

    # This location has already been visited,
    # remove from list of remaining loading locations
    loading = loading[loading != ships[0, 0]]

    # For each shipment (except the last), decide the one that is
    # visited for loading
    for currentship in range(nLoad - 1):

        # (Re)initialize array with travel times from current to
        # each remaining shipment
        timeCurrentToRemaining = np.zeros(len(loading))

        # Go over all remaining loading locations
        for remainship in range(len(loading)):

            # Fill in travel time current location to
            # each remaining loading location
            timeCurrentToRemaining[remainship] = get_traveltime(
                tourSequence[currentship],
                loading[remainship],
                skim,
                nZones)

        # Index of the nearest unvisited loading location
        nearestShipment = np.argmin(timeCurrentToRemaining)

        # Fill in as the next location in tour sequence
        tourSequence[currentship + 1] = loading[nearestShipment]

        # Remove this shipment from list of remaining loading locations
        loading = np.delete(loading, nearestShipment)

    # --------------- Unloading sequence (first time-of-day) ------------------
    for currentship in range(nUnloadFirstTOD):

        # (Re)initialize array with travel times from current to
        # each remaining shipment
        timeCurrentToRemaining = np.zeros(len(unloadingFirstTOD))

        # Go over all remaining unloading locations
        for remainship in range(len(unloadingFirstTOD)):

            # Fill in travel time current location to
            # each remaining loading location
            timeCurrentToRemaining[remainship] = get_traveltime(
                tourSequence[nLoad - 1 + currentship],
                unloadingFirstTOD[remainship],
                skim,
                nZones)

        # Index of the nearest unvisited unloading location
        nearestShipment = np.argmin(timeCurrentToRemaining)

        # Fill in as the next location in tour sequence
        tourSequence[nLoad + currentship] = unloadingFirstTOD[nearestShipment]

        # Remove this shipment from list of remaining unloading locations
        unloadingFirstTOD = np.delete(unloadingFirstTOD, nearestShipment)

    # --------------- Unloading sequence (last time-of-day) -------------------
    if not allSameTOD:
        for currentship in range(nUnloadLastTOD):
            timeCurrentToRemaining = np.zeros(len(unloadingLastTOD))
    
            for remainship in range(len(unloadingLastTOD)):
                timeCurrentToRemaining[remainship] = get_traveltime(
                    tourSequence[nLoad + nUnloadFirstTOD - 1 + currentship],
                    unloadingLastTOD[remainship],
                    skim,
                    nZones)
    
            nearestShipment = np.argmin(timeCurrentToRemaining)
    
            tourSequence[nLoad + nUnloadFirstTOD + currentship] = (
                    unloadingLastTOD[nearestShipment])
    
            unloadingLastTOD = np.delete(unloadingLastTOD, nearestShipment)

    # ---------- Some restructuring of tourSequence variable ------------------

    tourSequence = list(tourSequence)

    # If the carrier is at a DC, start the tour here
    # (not always necessarily the first loading location)
    if dc is not None:
        if tourSequence[0] != dc:
            tourSequence.insert(0, int(dc))

    # Make sure the tour does not visit the homebase in between
    # (otherwise it's not 1 tour but 2 tours)
    nStartLoc = set(np.where(np.array(tourSequence) == tourSequence[0])[0][1:])
    if len(nStartLoc) > 1:
        tourSequence = [
            tourSequence[x]
            for x in range(len(tourSequence))
            if x not in nStartLoc]
        tourSequence.append(tourSequence[0])
    lenTourSequence = len(tourSequence)

    # ------------------ 2-opt posterior improvement ------------------
    # Only do 2-opt if tour has more than 3 stops
    if lenTourSequence > 3:
        startLocations = np.array(tourSequence[:-1]) - 1
        endLocations = np.array(tourSequence[1:]) - 1
        tourDuration = np.sum(
            skim[startLocations * nZones + endLocations, 0]) / 3600

        for shiftLocA in range(1, lenTourSequence - 1):
            for shiftLocB in range(1, lenTourSequence - 1):
                if shiftLocA != shiftLocB:
                    swappedTourSequence = tourSequence.copy()
                    swappedTourSequence[shiftLocA] = tourSequence[shiftLocB]
                    swappedTourSequence[shiftLocB] = tourSequence[shiftLocA]

                    swappedStartLocations = np.array(
                        swappedTourSequence[:-1]) - 1
                    swappedEndLocations = np.array(
                        swappedTourSequence[1:]) - 1
                    swappedTourDuration = np.sum(
                        skim[swappedStartLocations * nZones +
                             swappedEndLocations, 0]) / 3600

                    # Only make the swap definitive
                    # if it reduces the tour duration
                    if swappedTourDuration < tourDuration:

                        # Check if the loading locations are visited
                        # before the unloading locations
                        precedence = [None for i in range(len(ships))]
                        for i in range(len(ships)):
                            load, unload = ships[i, 0], ships[i, 1]
                            precedence[i] = (
                                np.where(swappedTourSequence == unload)[0][-1] >
                                np.where(swappedTourSequence == load)[0][0])

                        if np.all(precedence):
                            tourSequence = swappedTourSequence.copy()
                            tourDuration = swappedTourDuration

    return np.array(tourSequence, dtype=int)


def tourdur(tourSequence, skim, nZones):
    '''
    Calculates the tour duration of the tour (so far)

    tourSequence = array with ordered sequence of visited locations in tour
    '''
    tourSequence = np.array(tourSequence)
    tourSequence = tourSequence[tourSequence != 0]
    startLocations = tourSequence[: -1] - 1
    endLocations = tourSequence[1:] - 1
    tourDuration = np.sum(
        skim[startLocations * nZones + endLocations, 0]) / 3600

    return tourDuration


def tourdist(tourSequence, skim, nZones):
    '''
    Calculates the tour distance of the tour (so far)

    tourSequence = array with ordered sequence of visited locations in tour
    '''
    tourSequence = np.array(tourSequence)
    tourSequence = tourSequence[tourSequence != 0]
    startLocations = tourSequence[:-1] - 1
    endLocations = tourSequence[1:] - 1
    tourDistance = np.sum(
        skim[startLocations * nZones + endLocations, 1]) / 1000

    return tourDistance


def cap_utilization(veh, weights, carryingCapacity):
    '''
    Calculates the capacity utilzation of the tour (so far).
    Assume that vehicle type chosen for 1st shipment in tour
    defines the carrying capacity.
    '''
    cap = carryingCapacity[veh]
    weight = sum(weights)
    return weight / cap


def proximity(tourlocs, universal, skim, nZones):
    '''
    Reports the proximity value [km] of each shipment in
    the universal choice set

    tourlocs = array with the locations visited in the tour so far
    universal = the universal choice set
    '''
    # Unique locations visited in the tour so far
    # (except for tour starting point)
    if tourlocs[0, 0] == tourlocs[0, 1]:
        tourlocs = [
            x for x in np.unique(tourlocs)
            if x != 0]
    else:
        tourlocs = [
            x for x in np.unique(tourlocs)
            if x != 0 and x != tourlocs[0, 0]]

    # Loading and unloading locations of the remaining shipments
    otherShipments = universal[:, 1:3].astype(int)
    nOtherShipments = len(otherShipments)

    # Initialization
    distancesLoading = np.zeros((len(tourlocs), nOtherShipments))
    distancesUnloading = np.zeros((len(tourlocs), nOtherShipments))

    for i in range(len(tourlocs)):
        distancesLoading[i, :] = skim[
            (tourlocs[i] - 1) * nZones + (otherShipments[:, 0] - 1), 1] / 1000
        distancesUnloading[i, :] = skim[
            (tourlocs[i] - 1) * nZones + (otherShipments[:, 1] - 1), 1] / 1000

    # Proximity measure = distance to nearest loading and unloading
    # location summed up
    distances = np.min(distancesLoading + distancesUnloading, axis=0)

    return distances


def lognode_loading(tour, shipments):
    '''
    Returns a Boolean that states whether a logistical node is visited in
    the tour for loading
    '''
    if len(tour) == 1:
        return shipments[tour][0][7] == 2
    else:
        return np.any(shipments[tour][0][7] == 2)


def lognode_unloading(tour, shipments):
    '''
    Returns a Boolean that states whether a logistical node is visited in
    the tour for unloading
    '''
    if len(tour) == 1:
        return shipments[tour][0][8] == 2
    else:
        return np.any(shipments[tour][0][8] == 2)


def transship(tour, shipments):
    '''
    Returns a Boolean that states whether a transshipment zone is visited in
    the tour
    '''
    if len(tour) == 1:
        return (
            shipments[tour][0][7] == 1 or
            shipments[tour][0][8] == 1)
    else:
        return (
            np.any(shipments[tour][0][7] == 1) or
            np.any(shipments[tour][0][8] == 1))


def urbanzone(tour, shipments):
    '''
    Returns a Boolean that states whether an urban zone is visited in the tour
    '''
    if len(tour) == 1:
        return shipments[tour][0][9]
    else:
        return np.any(shipments[tour][0][9] == 1)


def is_concrete():
    '''
    Returns a Boolean that states whether concrete is transported in the tour.
    This was part of the estimated ET model but is not modelled in the TFS.
    '''
    return False


def max_nstr(tour, shipments, nNSTR):
    '''
    Returns the NSTR goods type (0-9) of which the highest weight is
    transported in the tour (so far)

    tour = array with the IDs of all shipments in the tour
    '''
    nstrWeight = np.zeros(nNSTR)

    for i in range(len(tour)):
        shipNSTR = shipments[tour[i], 5]
        shipWeight = shipments[tour[i], 6]
        nstrWeight[shipNSTR] += shipWeight

    return np.argmax(nstrWeight)


def sum_weight(tour, shipments):
    '''
    Returns the weight of all goods that are transported in the tour

    tour = array with the IDs of all shipments in the tour
    '''
    sumWeight = 0

    for i in range(len(tour)):
        # The weights of the shipments in the tour are summed up
        # and converted to tonnes
        shipWeight = shipments[tour[i], 6]
        sumWeight += (shipWeight / 1000)

    return sumWeight


def endtour_first(tourDuration, capUt, tour, params, shipments, nNSTR):
    '''
    Returns True if we decide to end the tour, False if we decide
    to add another shipment
    '''
    # Calculate explanatory variables
    vehicleTypeIs0 = (shipments[tour[0], 4] == 0) * 1
    vehicleTypeIs1 = (shipments[tour[0], 4] == 1) * 1
    maxNSTR = max_nstr(tour, shipments, nNSTR)
    nstrIs0 = (maxNSTR == 0) * 1
    nstrIs1 = (maxNSTR == 1) * 1
    nstrIs2to5 = (maxNSTR in [2, 3, 4, 5]) * 1
    nstrIs6 = (maxNSTR == 6) * 1
    nstrIs7 = (maxNSTR == 7) * 1
    nstrIs8 = (maxNSTR == 8) * 1

    # Calculate utility
    etUtility = (params[0] +
                 params[1] * tourDuration**0.5 +
                 params[2] * capUt**2 +
                 params[3] * transship(tour, shipments) +
                 params[4] * lognode_loading(tour, shipments) +
                 params[5] * lognode_unloading(tour, shipments) +
                 params[6] * urbanzone(tour, shipments) +
                 params[7] * vehicleTypeIs0 +
                 params[8] * vehicleTypeIs1 +
                 params[9] * nstrIs0 +
                 params[10] * nstrIs1 +
                 params[11] * nstrIs2to5 +
                 params[12] * nstrIs6 +
                 params[13] * nstrIs7 +
                 params[14] * nstrIs8)

    # Calculate probability
    etProbability = np.exp(etUtility) / (np.exp(etUtility) + np.exp(0))

    # Monte Carlo to simulate choice based on probability
    return np.random.rand() < etProbability


def endtour_later(tour, tourlocs, tourSequence, universal, skim,
                  nZones, carryingCapacity, params, shipments, nNSTR):
    '''
    Returns True if we decide to end the tour, False if we decide
    to add another shipment
    '''
    # Calculate explanatory variables
    tourDuration = tourdur(
        tourSequence,
        skim,
        nZones)
    prox = np.min(proximity(
        tourlocs,
        universal,
        skim,
        nZones))
    capUt = cap_utilization(
        shipments[tour[0], 4],
        shipments[tour, 6],
        carryingCapacity)
    numberOfStops = len(np.unique(tourlocs))
    vehicleTypeIs0 = (shipments[tour[0], 4] == 0) * 1
    vehicleTypeIs1 = (shipments[tour[0], 4] == 1) * 1
    maxNSTR = max_nstr(tour, shipments, nNSTR)
    nstrIs0 = (maxNSTR == 0) * 1
    nstrIs1 = (maxNSTR == 1) * 1
    nstrIs6 = (maxNSTR == 6) * 1
    nstrIs7 = (maxNSTR == 7) * 1
    nstrIs8 = (maxNSTR == 8) * 1

    # Calculate utility
    etUtility = (params[0] +
                 params[1] * (tourDuration) +
                 params[2] * capUt +
                 params[3] * prox +
                 params[4] * transship(tour, shipments) +
                 params[5] * np.log(numberOfStops) +
                 params[6] * lognode_loading(tour, shipments) +
                 params[7] * lognode_unloading(tour, shipments) +
                 params[8] * urbanzone(tour, shipments) +
                 params[9] * vehicleTypeIs0 +
                 params[10] * vehicleTypeIs1 +
                 params[11] * nstrIs0 +
                 params[12] * nstrIs1 +
                 params[13] * nstrIs6 +
                 params[14] * nstrIs7 +
                 params[15] * nstrIs8)

    # Calculate probability
    etProbability = np.exp(etUtility) / (np.exp(etUtility) + np.exp(0))

    # Monte Carlo to simulate choice based on probability
    return np.random.rand() < etProbability


def selectshipment(tour, tourlocs, universal, skim,
                   nZones, nTOD, carryingCapacity, shipments):
    '''
    Returns the chosen shipment based on Select Shipment MNL
    '''
    # Some tour characteristics as input for the constraint checks
    if type(tour) == int:
        tourLS = shipments[tour][10]
        tourVT = shipments[tour][4]
        tourTODs = [shipments[tour][13]]
    else:
        tourLS = shipments[tour[0]][10]
        tourVT = shipments[tour[0]][4]
        tourTODs = [shipments[i][13] for i in tour]

    # Check capacity utilization
    tourWeight = np.sum(shipments[tour, 6])
    shipsCapUt = (tourWeight + universal[:, 6]) / carryingCapacity[tourVT]

    # Check proximity of other shipments to the tour
    shipsProx = proximity(tourlocs, universal, skim, nZones)

    # Which shipments belong to the same logistic segment and have
    # the same vehicle type as the tour
    shipsSameLS = np.array(universal[:, 10] == tourLS)
    shipsSameVT = np.array(universal[:, 4] == tourVT)

    # Which shipments have a delivery time matching with the tour
    shipsTOD = universal[:, 13]

    if len(tourTODs) == 1:

        # Codes of the first and last period of a day
        firstCategoryTOD = 0
        lastCategoryTOD = (nTOD - 1)

        # Only two aligning time periods allowed in a tour
        if tourTODs[0] == firstCategoryTOD:
            shipsFeasibleTOD = (
                (np.abs(shipsTOD - tourTODs[0]) <= 1) |
                (shipsTOD == lastCategoryTOD))
        elif tourTODs[0] == lastCategoryTOD:
            shipsFeasibleTOD = (
                (np.abs(shipsTOD - tourTODs[0]) <= 1) |
                (shipsTOD == firstCategoryTOD))
        else:
            shipsFeasibleTOD = (
                np.abs(shipsTOD - tourTODs[0]) <= 1)

    else:
        shipsFeasibleTOD = (
            (universal[:, 13] == tourTODs[0]) |
            (universal[:, 13] == tourTODs[1]))

    # Initialize feasible choice set, those shipments that
    # comply with constraints
    selectShipConstraints = (
        (shipsCapUt < 1.1) &
        shipsSameLS &
        shipsFeasibleTOD)
    feasibleChoiceSet = universal[selectShipConstraints]

    # If there are no feasible shipments, the return -2 statement
    # is used to end the tour
    if len(feasibleChoiceSet) == 0:
        return -2

    else:
        shipsSameVT = shipsSameVT[selectShipConstraints]
        shipsProx = shipsProx[selectShipConstraints]

        # Make shipments of same vehicle type more likely to be chosen
        # (through lower proximity value)
        shipsProx[shipsSameVT] /= 2

        # Select the shipment with minimum distance to the tour (proximity)
        ssChoice = np.argmin(shipsProx)
        chosenShipment = feasibleChoiceSet[ssChoice]

        return chosenShipment


def tourformation(carMarkers, shipments, skim, nZones, maxNumShips,
                  carryingCapacity, dcZones,
                  nShipmentsPerCarrier, nCarriers, nTOD, nNSTR,
                  logitParams_ETfirst, logitParams_ETlater,
                  cars):
    '''
    Run the tour formation procedure for a set of carriers with a
    set of shipments.
    '''
    tours = [
        [np.zeros(1, dtype=int)
            for ship in range(nShipmentsPerCarrier[car])]
        for car in range(nCarriers)]
    tourSequences = [
        [np.zeros(min(nShipmentsPerCarrier[car], maxNumShips) * 2, dtype=int)
            for ship in range(nShipmentsPerCarrier[car])]
        for car in range(nCarriers)]
    nTours = np.zeros(nCarriers)

    for car in cars:

        print(
            f'\tForming tours for carrier {car+1} of {nCarriers}...',
            end='\r')

        tourCount = 0

        # Universal choice set = all non-allocated shipments per carrier
        universalChoiceSet = (
            shipments[carMarkers[car]:carMarkers[car + 1], :].copy())

        if car < len(dcZones):
            dc = dcZones[car]

            # Sort by shipment distance, this will help in constructing
            # more efficient/realistic tours
            shipmentDistances = skim[
                (universalChoiceSet[:, 1] - 1) * nZones +
                (universalChoiceSet[:, 1] - 1)]
            universalChoiceSet = np.c_[universalChoiceSet, shipmentDistances]
            universalChoiceSet = universalChoiceSet[
                universalChoiceSet[:, -1].argsort()]
            universalChoiceSet = universalChoiceSet[:, :-1]

        else:
            dc = None

        while len(universalChoiceSet) != 0:
            shipmentCount = 0

            tourLocations = np.zeros(
                (min(nShipmentsPerCarrier[car], maxNumShips) * 2, 2),
                dtype=int)

            # Loading and unloading location of this shipment
            tourLocations[shipmentCount, 0] = universalChoiceSet[0, 1].copy()
            tourLocations[shipmentCount, 1] = universalChoiceSet[0, 2].copy()

            # First shipment in the tour is the first listed one
            # in universal choice set
            tours[car][tourCount][shipmentCount] = (
                universalChoiceSet[0, 0].copy())

            # Tour with only 1 shipment:
            # sequence = go from loading to unloading of this shipment
            tourSequences[car][tourCount][shipmentCount] = (
                universalChoiceSet[0, 1].copy())
            tourSequences[car][tourCount][shipmentCount + 1] = (
                universalChoiceSet[0, 2].copy())

            # Remove shipment from universal choice set
            universalChoiceSet = np.delete(universalChoiceSet, 0, 0)

            # If no shipments left for carrier,
            # break out of while loop and go to next carrier
            if len(universalChoiceSet) == 0:
                tourCount += 1
                nTours[car] = tourCount
                break

            else:
                # Current tour, tourlocations and toursequence
                tour = tours[car][tourCount]
                tourLocs = tourLocations[0:shipmentCount + 1]
                tourSeq = [tourSequences[car][tourCount][0]]

                # Duration, proximity value and capacity utilization
                # of the tour
                tourDuration = tourdur(
                    tourSeq,
                    skim,
                    nZones)
                prox = proximity(
                    tourLocs,
                    universalChoiceSet,
                    skim,
                    nZones)
                capUt = cap_utilization(
                    shipments[tour[0], 4],
                    shipments[tour, 6],
                    carryingCapacity)

                # Check for End Tour constraints
                etConstraintCheck = (
                    (shipmentCount < maxNumShips) and
                    (tourDuration < 9) and
                    (capUt < 1) and
                    (np.min(prox) < 100) and
                    ~is_concrete())

                if etConstraintCheck:
                    # End Tour or not
                    etChoice = endtour_first(
                        tourDuration,
                        capUt,
                        tour,
                        logitParams_ETfirst,
                        shipments,
                        nNSTR)

                    while (not etChoice) and len(universalChoiceSet) != 0:
                        # Current tour, tourlocations and toursequence
                        tour = tours[car][tourCount]
                        tourLocs = tourLocations[0:shipmentCount + 1]
                        tourSeq = [tourSequences[car][tourCount][0]]

                        # Duration, proximity and capacity utilization
                        # of the tour
                        tourDuration = tourdur(
                            tourSeq,
                            skim,
                            nZones)
                        prox = proximity(
                            tourLocs,
                            universalChoiceSet,
                            skim,
                            nZones)
                        capUt = cap_utilization(
                            shipments[tour[0], 4],
                            shipments[tour, 6],
                            carryingCapacity)

                        # Check for End Tour constraints
                        etConstraintCheck = (
                            (shipmentCount < maxNumShips) and
                            (tourDuration < 9) and
                            (capUt < 1) and
                            (np.min(prox) < 100) and
                            ~is_concrete())

                        if etConstraintCheck:
                            # Choose which shipment to add
                            chosenShipment = selectshipment(
                                tour, tourLocs, universalChoiceSet, skim,
                                nZones, nTOD,
                                carryingCapacity,
                                shipments)

                            # If no feasible shipments left
                            if np.any(chosenShipment == -2):
                                tourCount += 1
                                break

                            else:
                                shipmentCount += 1

                                # Add the chosen shipment to the tour
                                # and update tour sequence
                                tours[car][tourCount] = np.append(
                                    tours[car][tourCount],
                                    int(chosenShipment[0]))
                                tourLocations[shipmentCount, 0] = (
                                    int(chosenShipment[1]))
                                tourLocations[shipmentCount, 1] = (
                                    int(chosenShipment[2]))
                                
                                tourTODs = shipments[tours[car][tourCount], 13]
                                tourSequences[car][tourCount] = nearest_neighbor(
                                    tourLocations[0:shipmentCount + 1],
                                    tourTODs,
                                    dc,
                                    skim,
                                    nZones, nTOD)

                                # Remove chosen shipment from
                                # universal choice set
                                shipmentToDelete = np.where(
                                    universalChoiceSet[:, 0] == chosenShipment[0])[0][0]
                                universalChoiceSet = np.delete(
                                    universalChoiceSet,
                                    shipmentToDelete,
                                    0)

                                if len(universalChoiceSet) != 0:
                                    # Current tour, tourlocations
                                    # and toursequence
                                    tour = tours[car][tourCount]
                                    tourLocs = tourLocations[0:shipmentCount + 1]
                                    tourSeq = [tourSequences[car][tourCount][0]]

                                    # End tour or not
                                    etChoice = endtour_later(
                                        tour, tourLocs, tourSeq,
                                        universalChoiceSet, skim,
                                        nZones,
                                        carryingCapacity,
                                        logitParams_ETlater,
                                        shipments,
                                        nNSTR)

                                else:
                                    tourCount += 1
                                    nTours[car] = tourCount
                                    break

                        else:
                            tourCount += 1
                            break

                    else:
                        tourCount += 1

                else:
                    tourCount += 1

    return [tours, tourSequences, nTours]


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
    varDict['PARAMS_TOD']      = varDict['PARAMFOLDER'] + 'Params_TOD.csv'
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

