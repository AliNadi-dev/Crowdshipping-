# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 14:21:12 2020

@author: modelpc
"""
import numpy as np
import pandas as pd
import time
import datetime
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


#%% Class: Root

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
        self.root.title("Progress Parcel Scheduling")
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


#%% Function: actually_run_module

def actually_run_module(args):


    try:

        start_time = time.time()

        root = args[0]
        varDict = args[1]

        if root != '':
            root.progressBar['value'] = 0

        maxVehicleLoad = int(varDict['PARCELS_MAXLOAD'])
        doCrowdShipping = (str(varDict['CROWDSHIPPING']).upper() == 'TRUE')

        exportTripMatrix = True

        log_file = open(
            varDict['OUTPUTFOLDER'] + "Logfile_ParcelScheduling.log", "w")
        log_file.write(
            "Start simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")

        if root != '':
            root.update_statusbar("Parcel Scheduling: Calculating...")
            root.progressBar['value'] = 0.1

        # ------------------------- Import data--------------------------------

        print('Importing data...')
        log_file.write('Importing data...\n')

        parcels = pd.read_csv(
            varDict['OUTPUTFOLDER'] +
            'ParcelDemand_' + varDict['LABEL'] + '.csv')

        parcelNodes, coords = read_shape(
            varDict['PARCELNODES'],
            returnGeometry=True)
        parcelNodes['X'] = [
            coords[i]['coordinates'][0] for i in range(len(coords))]
        parcelNodes['Y'] = [
            coords[i]['coordinates'][1] for i in range(len(coords))]
        parcelNodes['id'] = parcelNodes['id'].astype(int)
        parcelNodes.index = parcelNodes['id']
        parcelNodes = parcelNodes.sort_index()
        parcelNodesCEP = {}
        for i in parcelNodes.index:
            parcelNodesCEP[parcelNodes.at[i, 'id']] = parcelNodes.at[i, 'CEP']

        zones = read_shape(varDict['ZONES'])
        zones = zones.sort_values('AREANR')
        zones.index = zones['AREANR']
        supCoordinates = pd.read_csv(varDict['SUP_COORDINATES_ID'], sep=',')
        supCoordinates.index = supCoordinates['AREANR']

        zonesX = {}
        zonesY = {}
        for areanr in zones.index:
            zonesX[areanr] = zones.at[areanr, 'X']
            zonesY[areanr] = zones.at[areanr, 'Y']
        for areanr in supCoordinates.index:
            zonesX[areanr] = supCoordinates.at[areanr, 'Xcoor']
            zonesY[areanr] = supCoordinates.at[areanr, 'Ycoor']

        nIntZones = len(zones)
        nSupZones = 43
        zoneDict = dict(np.transpose(np.vstack(
            (np.arange(1, nIntZones + 1),
             zones['AREANR']))))
        zoneDict = {int(a): int(b) for a, b in zoneDict.items()}
        for i in range(nSupZones):
            zoneDict[nIntZones + i + 1] = 99999900 + i + 1
        invZoneDict = dict((v, k) for k, v in zoneDict.items())

        # Change zoning to skim zones which run continuously from 0
        parcels['X'] = [zonesX[x] for x in parcels['D_zone'].values]
        parcels['Y'] = [zonesY[x] for x in parcels['D_zone'].values]
        parcels['D_zone'] = [invZoneDict[x] for x in parcels['D_zone']]
        parcels['O_zone'] = [invZoneDict[x] for x in parcels['O_zone']]
        parcelNodes['skim_zone'] = [invZoneDict[x] for x in parcelNodes['AREANR']]

        if root != '':
            root.progressBar['value'] = 0.3

        # System input for scheduling
        parcelDepTime = np.array(pd.read_csv(
            varDict['DEPTIME_PARCELS']).iloc[:, 1])
        dropOffTime = varDict['PARCELS_DROPTIME'] / 3600
        skimTravTime = read_mtx(varDict['SKIMTIME'])
        skimDistance = read_mtx(varDict['SKIMDISTANCE'])
        nZones = int(len(skimTravTime)**0.5)

        if root != '':
            root.progressBar['value'] = 0.9

        # Intrazonal impedances
        skimTravTime = skimTravTime.reshape(nZones,nZones)
        for i in range(nZones):
            skimTravTime[i, i] = (
                0.7 * np.min(skimTravTime[i, skimTravTime[i, :] > 0]))
        skimTravTime = skimTravTime.flatten()
        skimDistance = skimDistance.reshape(nZones,nZones)
        for i in range(nZones):
            skimDistance[i, i] = (
                0.7 * np.min(skimDistance[i, skimDistance[i, :]>0]))
        skimDistance = skimDistance.flatten()

        depotIDs = list(parcelNodes['id'])

        if root != '':
            root.progressBar['value'] = 1.0

        # ---------------- Crowdshipping use case -----------------------------
        if doCrowdShipping:

            # The first N zones for which to consider
            # crowdshipping for parcel deliveries
            nFirstZonesCS = 5925

            # Percentage of parcels eligible for crowdshipping
            parcelShareCRW = varDict['CRW_PARCELSHARE']

            # Input data and parameters for the crowdshipping use case
            modeParamsCRW = pd.read_csv(
                varDict['CRW_MODEPARAMS'],
                index_col=0,
                sep=',')

            modes = {'fiets': {}, 'auto': {}, }

            modes['fiets']['willingness'] = (
                modeParamsCRW.at['BIKE', 'WILLINGNESS'])
            modes['fiets']['dropoff_time'] = (
                modeParamsCRW.at['BIKE', 'DROPOFFTIME'])
            modes['fiets']['VoT'] = (
                modeParamsCRW.at['BIKE', 'VOT'])

            modes['auto']['willingness'] = (
                modeParamsCRW.at['CAR', 'WILLINGNESS'])
            modes['auto']['dropoff_time'] = (
                modeParamsCRW.at['CAR', 'DROPOFFTIME'])
            modes['auto']['VoT'] = (
                modeParamsCRW.at['CAR', 'VOT'])

            modes['fiets']['relative_extra_parcel_dist_threshold'] = (
                modeParamsCRW.at[
                    'BIKE',
                    'RELATIVE_EXTRA_PARCEL_DIST_THRESHOLD'])
            modes['auto']['relative_extra_parcel_dist_threshold'] = (
                modeParamsCRW.at[
                    'CAR',
                    'RELATIVE_EXTRA_PARCEL_DIST_THRESHOLD'])

            modes['fiets']['OD_path'] = varDict['CRW_PDEMAND_BIKE']
            modes['fiets']['skim_time'] = skimDistance / 1000 / 12 * 3600
            modes['fiets']['n_trav'] = 0
            modes['auto']['OD_path'] = varDict['CRW_PDEMAND_CAR']
            modes['auto']['skim_time'] = skimTravTime
            modes['auto']['n_trav'] = 0

            for mode in modes:
                modes[mode]['OD_array'] = read_mtx(
                    modes[mode]['OD_path']).reshape(nIntZones, nIntZones)
                modes[mode]['OD_array'] *= modes[mode]['willingness']
                modes[mode]['OD_array'] = np.array(
                    np.round(modes[mode]['OD_array']),
                    dtype=int)
                modes[mode]['OD_array'] = modes[mode]['OD_array'][
                    :nFirstZonesCS, :]
                modes[mode]['OD_array'] = modes[mode]['OD_array'][
                    :, :nFirstZonesCS]

            # Which zones are located in which municipality
            zone_gemeente_dict = dict(np.transpose(np.vstack((
                np.arange(1, nIntZones + 1),
                zones['Gemeentena']))))

            # Get retail jobs per zone from socio-economic data
            segs = pd.read_csv(varDict['SEGS'])
            segs.index = segs['zone']
            segsDetail = np.array(segs['6: detail'])

            # Perform the crowdshipping calculations
            do_crowdshipping(
                parcels, zones, nIntZones, nZones, zoneDict,
                zonesX, zonesY,
                skimDistance, skimTravTime,
                nFirstZonesCS, parcelShareCRW, modes,
                zone_gemeente_dict, segsDetail,
                varDict['OUTPUTFOLDER'], varDict['LABEL'],
                log_file,
                root)

        # -------------------- Forming spatial clusters of parcels ------------

        print('Forming spatial clusters of parcels...')
        log_file.write('Forming spatial clusters of parcels...\n')

        # A measure of euclidean distance based on the coordinates
        skimEuclidean = (
            np.array(list(zonesX.values())).repeat(nZones).reshape(nZones, nZones) -
            np.array(list(zonesX.values())).repeat(nZones).reshape(nZones, nZones).transpose())**2
        skimEuclidean += (
            np.array(list(zonesY.values())).repeat(nZones).reshape(nZones, nZones) -
            np.array(list(zonesY.values())).repeat(nZones).reshape(nZones, nZones).transpose())**2
        skimEuclidean = skimEuclidean**0.5
        skimEuclidean = skimEuclidean.flatten()
        skimEuclidean /= np.sum(skimEuclidean)

        # To prevent instability related to possible mistakes in skim,
        # use average of skim and euclidean distance
        # (both normalized to a sum of 1)
        skimClustering = skimDistance.copy()
        skimClustering /= np.sum(skimClustering)
        skimClustering += skimEuclidean

        del skimEuclidean

        if varDict['LABEL'] == 'UCC':

            # Divide parcels into the 4 tour types, namely:
            # 0: Depots to households
            # 1: Depots to UCCs
            # 2: From UCCs, by van
            # 3: From UCCs, by LEVV
            parcelsUCC = {}
            parcelsUCC[0] = pd.DataFrame(
                parcels[(parcels['FROM_UCC'] == 0) & (parcels['TO_UCC'] == 0)])
            parcelsUCC[1] = pd.DataFrame(
                parcels[(parcels['FROM_UCC'] == 0) & (parcels['TO_UCC'] == 1)])
            parcelsUCC[2] = pd.DataFrame(
                parcels[(parcels['FROM_UCC'] == 1) & (parcels['VEHTYPE'] == 7)])
            parcelsUCC[3] = pd.DataFrame(
                parcels[(parcels['FROM_UCC'] == 1) & (parcels['VEHTYPE'] == 8)])

            # Cluster parcels based on proximity and constrained
            # by vehicle capacity
            for i in range(3):
                if doCrowdShipping:
                    startValueProgress = 56.0 +       i / 3 * (70.0 - 56.0)
                    endValueProgress   = 56.0 + (i + 1) / 3 * (70.0 - 56.0)
                else:
                    startValueProgress = 2.0 +       i / 3 * (55.0 - 2.0)
                    endValueProgress   = 2.0 + (i + 1) / 3 * (55.0 - 2.0)

                print('\tTour type ' + str(i + 1) + '...')
                log_file.write('\tTour type ' + str(i + 1) + '...\n')

                parcelsUCC[i].index = np.arange(len(parcelsUCC[i]))
                parcelsUCC[i] = cluster_parcels(
                    parcelsUCC[i],
                    maxVehicleLoad, skimClustering,
                    root, startValueProgress, endValueProgress)

            # LEVV have smaller capacity
            startValueProgress = 70.0 if doCrowdShipping else 55.0
            startValueProgress = 75.0 if doCrowdShipping else 60.0

            print('\tTour type 4...')
            log_file.write('\tTour type 4...\n')

            parcelsUCC[3] = cluster_parcels(
                parcelsUCC[3],
                int(round(maxVehicleLoad / 5)), skimClustering,
                root, startValueProgress, endValueProgress)

            # Aggregate parcels based on depot, cluster and destination
            for i in range(4):

                if i <= 1:
                    parcelsUCC[i] = pd.pivot_table(
                        parcelsUCC[i],
                        values=['Parcel_ID'],
                        index=['DepotNumber', 'Cluster', 'O_zone', 'D_zone'],
                        aggfunc={'Parcel_ID': 'count'})
                    parcelsUCC[i] = parcelsUCC[i].rename(
                        columns={'Parcel_ID': 'Parcels'})

                    parcelsUCC[i]['Depot'] = [
                        x[0] for x in parcelsUCC[i].index]
                    parcelsUCC[i]['Cluster'] = [
                        x[1] for x in parcelsUCC[i].index]
                    parcelsUCC[i]['Orig'] = [
                        x[2] for x in parcelsUCC[i].index]
                    parcelsUCC[i]['Dest'] = [
                        x[3] for x in parcelsUCC[i].index]

                else:
                    parcelsUCC[i] = pd.pivot_table(
                        parcelsUCC[i],
                        values=['Parcel_ID'],
                        index=['O_zone', 'Cluster', 'D_zone'],
                        aggfunc={'Parcel_ID': 'count'})
                    parcelsUCC[i] = parcelsUCC[i].rename(
                        columns={'Parcel_ID': 'Parcels'})

                    parcelsUCC[i]['Depot'] = [
                        x[0] for x in parcelsUCC[i].index]
                    parcelsUCC[i]['Cluster'] = [
                        x[1] for x in parcelsUCC[i].index]
                    parcelsUCC[i]['Orig'] = [
                        x[0] for x in parcelsUCC[i].index]
                    parcelsUCC[i]['Dest'] = [
                        x[2] for x in parcelsUCC[i].index]

                parcelsUCC[i].index = np.arange(len(parcelsUCC[i]))

        if varDict['LABEL'] != 'UCC':
            # Cluster parcels based on proximity and constrained
            # by vehicle capacity
            startValueProgress = 56.0 if doCrowdShipping else 2.0
            endValueProgress = 75.0 if doCrowdShipping else 60.0
            parcels = cluster_parcels(
                parcels,
                maxVehicleLoad, skimClustering,
                root, startValueProgress, endValueProgress)

            # Aggregate parcels based on depot, cluster and destination
            parcels = pd.pivot_table(
                parcels,
                values=['Parcel_ID'],
                index=['DepotNumber', 'Cluster', 'O_zone', 'D_zone'],
                aggfunc={'Parcel_ID': 'count'})
            parcels = parcels.rename(columns={'Parcel_ID': 'Parcels'})

            parcels['Depot'] = [
                x[0] for x in parcels.index]
            parcels['Cluster'] = [
                x[1] for x in parcels.index]
            parcels['Orig'] = [
                x[2] for x in parcels.index]
            parcels['Dest'] = [
                x[3] for x in parcels.index]

            parcels.index = np.arange(len(parcels))

        del skimClustering

        # ----------- Scheduling of trips (UCC scenario) ----------------------

        if varDict['LABEL'] == 'UCC':

            # Depots to households
            message = (
                'Starting scheduling procedure for ' +
                'parcels from depots to households...')
            print(message)
            log_file.write(message + '\n')

            startValueProgress = 75.0 if doCrowdShipping else 60.0
            endValueProgress = 80.0
            tourType = 0
            deliveries = create_schedules(
                parcelsUCC[0],
                dropOffTime,
                skimTravTime, skimDistance,
                parcelNodesCEP,
                parcelDepTime,
                tourType,
                varDict['LABEL'],
                root, startValueProgress, endValueProgress)

            # Depots to UCCs
            message = (
                'Starting scheduling procedure for ' +
                'parcels from depots to UCC...')
            print(message)
            log_file.write(message + '\n')

            startValueProgress = 80.0
            endValueProgress = 83.0
            tourType = 1
            deliveries1 = create_schedules(
                parcelsUCC[1],
                dropOffTime,
                skimTravTime, skimDistance,
                parcelNodesCEP,
                parcelDepTime,
                tourType,
                varDict['LABEL'],
                root, startValueProgress, endValueProgress)

            # Depots to UCCs (van)
            message = (
                'Starting scheduling procedure for ' +
                'parcels from UCCs (by van)...')
            print(message)
            log_file.write(message + '\n')

            startValueProgress = 83.0
            endValueProgress = 86.0
            tourType = 2
            deliveries2 = create_schedules(
                parcelsUCC[2],
                dropOffTime,
                skimTravTime, skimDistance,
                parcelNodesCEP,
                parcelDepTime,
                tourType,
                varDict['LABEL'],
                root, startValueProgress, endValueProgress)

            # Depots to UCCs (LEVV)
            message = (
                'Starting scheduling procedure for ' +
                'parcels from UCCs (by LEVV)...')
            print(message)
            log_file.write(message + '\n')

            startValueProgress = 86.0
            endValueProgress = 89.0
            tourType = 3
            deliveries3 = create_schedules(
                parcelsUCC[3],
                dropOffTime,
                skimTravTime, skimDistance,
                parcelNodesCEP,
                parcelDepTime,
                tourType,
                varDict['LABEL'],
                root, startValueProgress, endValueProgress)

            # Combine deliveries of all tour types
            deliveries = pd.concat([
                deliveries, deliveries1, deliveries2, deliveries3])
            deliveries.index = np.arange(len(deliveries))

        # ----------- Scheduling of trips (REF scenario) ---------------------

        if varDict['LABEL'] != 'UCC':

            print('Starting scheduling procedure for parcels...')
            log_file.write('Starting scheduling procedure for parcels...\n')

            startValueProgress = 75.0 if doCrowdShipping else 60.0
            endValueProgress = 90.0
            tourType = 0

            deliveries = create_schedules(
                parcels,
                dropOffTime,
                skimTravTime, skimDistance,
                parcelNodesCEP,
                parcelDepTime,
                tourType,
                varDict['LABEL'],
                root, startValueProgress, endValueProgress)

        # ---------------- Export output table to CSV and SHP -----------------

        # Transform to MRDH zone numbers and export
        deliveries['O_zone'] = [zoneDict[x] for x in deliveries['O_zone']]
        deliveries['D_zone'] = [zoneDict[x] for x in deliveries['D_zone']]
        deliveries['TripDepTime'] = [
            round(deliveries['TripDepTime'][i], 3)
            for i in deliveries.index]
        deliveries['TripEndTime'] = [
            round(deliveries['TripEndTime'][i], 3)
            for i in deliveries.index]

        message = (
            "Writing scheduled trips to " +
            varDict['OUTPUTFOLDER'] + f"ParcelSchedule_{varDict['LABEL']}.csv")
        print(message)
        log_file.write(message + "\n")

        deliveries.to_csv(
            varDict['OUTPUTFOLDER'] + f"ParcelSchedule_{varDict['LABEL']}.csv",
            index=False)

        if root != '':
            root.progressBar['value'] = 91.0

        print('Writing GeoJSON...')
        log_file.write('Writing GeoJSON...\n')

        # Initialize arrays with coordinates
        Ax = np.zeros(len(deliveries), dtype=int)
        Ay = np.zeros(len(deliveries), dtype=int)
        Bx = np.zeros(len(deliveries), dtype=int)
        By = np.zeros(len(deliveries), dtype=int)

        # Determine coordinates of LineString for each trip
        tripIDs = [x.split('_')[-1] for x in deliveries['Trip_ID']]
        tourTypes = np.array(deliveries['TourType'], dtype=int)
        depotIDs = np.array(deliveries['Depot_ID'])

        for i in deliveries.index[:-1]:

            # First trip of tour
            if tripIDs[i] == '0' and tourTypes[i] <= 1:
                Ax[i] = parcelNodes['X'][depotIDs[i]]
                Ay[i] = parcelNodes['Y'][depotIDs[i]]
                Bx[i] = zonesX[deliveries['D_zone'][i]]
                By[i] = zonesY[deliveries['D_zone'][i]]

            # Last trip of tour
            elif tripIDs[i + 1] == '0' and tourTypes[i] <= 1:
                Ax[i] = zonesX[deliveries['O_zone'][i]]
                Ay[i] = zonesY[deliveries['O_zone'][i]]
                Bx[i] = parcelNodes['X'][depotIDs[i]]
                By[i] = parcelNodes['Y'][depotIDs[i]]

            # Intermediate trips of tour
            else:
                Ax[i] = zonesX[deliveries['O_zone'][i]]
                Ay[i] = zonesY[deliveries['O_zone'][i]]
                Bx[i] = zonesX[deliveries['D_zone'][i]]
                By[i] = zonesY[deliveries['D_zone'][i]]

        # Last trip of last tour
        i += 1
        if tourTypes[i] <= 1:
            Ax[i] = zonesX[deliveries['O_zone'][i]]
            Ay[i] = zonesY[deliveries['O_zone'][i]]
            Bx[i] = parcelNodes['X'][depotIDs[i]]
            By[i] = parcelNodes['Y'][depotIDs[i]]
        else:
            Ax[i] = zonesX[deliveries['O_zone'][i]]
            Ay[i] = zonesY[deliveries['O_zone'][i]]
            Bx[i] = zonesX[deliveries['D_zone'][i]]
            By[i] = zonesY[deliveries['D_zone'][i]]

        Ax = np.array(Ax, dtype=str)
        Ay = np.array(Ay, dtype=str)
        Bx = np.array(Bx, dtype=str)
        By = np.array(By, dtype=str)
        nTrips = len(deliveries)

        filename = (
            varDict['OUTPUTFOLDER'] +
            f"ParcelSchedule_{varDict['LABEL']}.geojson")
        with open(filename, 'w') as geoFile:
            geoFile.write(
                '{\n' + '"type": "FeatureCollection",\n' +
                '"features": [\n')

            for i in range(nTrips - 1):
                outputStr = (
                    '{ "type": "Feature", "properties": ' +
                    str(deliveries.loc[i, :].to_dict()).replace("'", '"') +
                    ', "geometry": ' +
                    '{ "type": "LineString", "coordinates": [ [ ' +
                    Ax[i] + ', ' + Ay[i] + ' ], [ ' +
                    Bx[i] + ', ' + By[i] + ' ] ] } },\n')
                geoFile.write(outputStr)

                if i % int(nTrips / 20) == 0:
                    print(
                        '\t' + str(round(i / nTrips * 100, 1)) + '%',
                        end='\r')

                    if root != '':
                        root.progressBar['value'] = (
                            91.0 +
                            (98.0 - 91.0) * (i / nTrips))

            # Bij de laatste feature moet er geen komma aan het einde
            i += 1
            outputStr = (
                '{ "type": "Feature", "properties": ' +
                str(deliveries.loc[i, :].to_dict()).replace("'", '"') +
                ', "geometry": ' +
                '{ "type": "LineString", "coordinates": [ [ ' +
                Ax[i] + ', ' + Ay[i] + ' ], [ ' +
                Bx[i] + ', ' + By[i] + ' ] ] } }\n')
            geoFile.write(outputStr)
            geoFile.write(']\n')
            geoFile.write('}')

        message = (
            "Parcel schedules written to " +
            varDict['OUTPUTFOLDER'] +
            f"ParcelSchedule_{varDict['LABEL']}.geojson")
        print(message)
        log_file.write(message + "\n")

        # ---------------------- Create and export trip matrices --------------

        if exportTripMatrix:

            print('Generating trip matrix...')
            log_file.write('Generating trip matrix...\n')

            cols = ['ORIG', 'DEST', 'N_TOT']
            deliveries['N_TOT'] = 1

            # Gebruik N_TOT om het aantal ritten per HB te bepalen,
            # voor elk logistiek segment, voertuigtype en totaal
            pivotTable = pd.pivot_table(
                deliveries,
                values=['N_TOT'],
                index=['O_zone', 'D_zone'],
                aggfunc=np.sum)
            pivotTable['ORIG'] = [x[0] for x in pivotTable.index]
            pivotTable['DEST'] = [x[1] for x in pivotTable.index]
            pivotTable = pivotTable[cols]

            # Assume one intrazonal trip for each zone with
            # multiple deliveries visited in a tour
            intrazonalTrips = {}

            for i in deliveries[deliveries['N_parcels'] > 1].index:
                zone = deliveries.at[i, 'D_zone']
                if zone in intrazonalTrips.keys():
                    intrazonalTrips[zone] += 1
                else:
                    intrazonalTrips[zone] = 1

            intrazonalKeys = list(intrazonalTrips.keys())

            for zone in intrazonalKeys:

                if (zone, zone) in pivotTable.index:
                    pivotTable.at[(zone, zone), 'N_TOT'] += (
                        intrazonalTrips[zone])

                    del intrazonalTrips[zone]

            intrazonalTripsDF = pd.DataFrame(
                np.zeros((len(intrazonalTrips), 3)),
                columns=cols)
            intrazonalTripsDF['ORIG'] = intrazonalTrips.keys()
            intrazonalTripsDF['DEST'] = intrazonalTrips.keys()
            intrazonalTripsDF['N_TOT'] = intrazonalTrips.values()
            pivotTable = pivotTable.append(intrazonalTripsDF)
            pivotTable = pivotTable.sort_values(['ORIG', 'DEST'])

            pivotTable.to_csv(
                (
                    varDict['OUTPUTFOLDER'] +
                    f"tripmatrix_parcels_{varDict['LABEL']}.txt"
                ),
                index=False,
                sep='\t')

            message = (
                "Trip matrix written to " +
                (
                    varDict['OUTPUTFOLDER'] +
                    f"tripmatrix_parcels_{varDict['LABEL']}.txt"
                ))
            print(message)
            log_file.write(message + "\n")

            # Departure time after 24:00 get 24 subtracted
            deliveries.loc[
                deliveries['TripDepTime'] >= 24, 'TripDepTime'] -= 24
            deliveries.loc[
                deliveries['TripDepTime'] >= 24, 'TripDepTime'] -= 24

            for tod in range(24):

                message = (
                    '\t Also generating trip matrix for ' +
                    f'TOD {tod}...')
                print(message)
                log_file.write(message + '\n')

                output = deliveries[
                    (deliveries['TripDepTime'] >= tod) &
                    (deliveries['TripDepTime'] < (tod + 1))].copy()
                output['N_TOT'] = 1

                if len(output) > 0:
                    # Gebruik deze dummies om het aantal ritten
                    # per HB te bepalen, voor elk logistiek segment,
                    # voertuigtype en totaal
                    pivotTable = pd.pivot_table(
                        output,
                        values=['N_TOT'],
                        index=['O_zone', 'D_zone'],
                        aggfunc=np.sum)
                    pivotTable['ORIG'] = [x[0] for x in pivotTable.index]
                    pivotTable['DEST'] = [x[1] for x in pivotTable.index]
                    pivotTable = pivotTable[cols]

                    # Assume one intrazonal trip for each zone with
                    # multiple deliveries visited in a tour
                    intrazonalTrips = {}

                    for i in output[output['N_parcels'] > 1].index:
                        zone = output.at[i, 'D_zone']
                        if zone in intrazonalTrips.keys():
                            intrazonalTrips[zone] += 1
                        else:
                            intrazonalTrips[zone] = 1

                    intrazonalKeys = list(intrazonalTrips.keys())

                    for zone in intrazonalKeys:

                        if (zone, zone) in pivotTable.index:
                            pivotTable.at[(zone, zone), 'N_TOT'] += (
                                intrazonalTrips[zone])

                            del intrazonalTrips[zone]

                    intrazonalTripsDF = pd.DataFrame(
                        np.zeros((len(intrazonalTrips), 3)),
                        columns=cols)
                    intrazonalTripsDF['ORIG'] = intrazonalTrips.keys()
                    intrazonalTripsDF['DEST'] = intrazonalTrips.keys()
                    intrazonalTripsDF['N_TOT'] = intrazonalTrips.values()
                    pivotTable = pivotTable.append(intrazonalTripsDF)
                    pivotTable = pivotTable.sort_values(['ORIG', 'DEST'])

                else:
                    pivotTable = pd.DataFrame(columns=cols)

                pivotTable.to_csv(
                    (
                        varDict['OUTPUTFOLDER'] +
                        "tripmatrix_parcels_" +
                        varDict['LABEL'] +
                        f"_TOD{tod}.txt"
                    ),
                    index=False,
                    sep='\t')

        # ------------------------- End of module -----------------------------
        totaltime = round(time.time() - start_time, 2)
        print('Finished. Run time: ' + str(totaltime) + ' seconds')
        log_file.write("Total runtime: %s seconds\n" % (totaltime))
        log_file.write(
            "End simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")
        log_file.close()

        if root != '':
            root.update_statusbar("Parcel Scheduling: Done")
            root.progressBar['value'] = 100

            # 0 means no errors in execution
            root.returnInfo = [0, [0, 0]]

            return root.returnInfo

        else:
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
                root.update_statusbar("Parcel Scheduling: Execution failed!")
                errorMessage = (
                    'Execution failed!\n\n' +
                    str(root.returnInfo[1][0]) +
                    '\n\n' +
                    str(root.returnInfo[1][1]))
                root.error_screen(text=errorMessage, size=[900, 350])

            else:
                return root.returnInfo
        else:
            return [1, [sys.exc_info()[0], traceback.format_exc()]]


#%% Function: create_schedules

def create_schedules(parcelsAgg, dropOffTime, skimTravTime, skimDistance,
                     parcelNodesCEP, parcelDepTime,
                     tourType, label,
                     root, startValueProgress, endValueProgress):
    '''
    Create the parcel schedules and store them in a DataFrame
    '''
    nZones = int(len(skimTravTime)**0.5)
    depots = np.unique(parcelsAgg['Depot'])
    nDepots = len(depots)

    print('\t0%', end='\r')

    tours = {}
    parcelsDelivered = {}
    departureTimes = {}
    depotCount = 0
    nTrips = 0

    for depot in np.unique(parcelsAgg['Depot']):
        depotParcels = parcelsAgg[parcelsAgg['Depot'] == depot]

        tours[depot] = {}
        parcelsDelivered[depot] = {}
        departureTimes[depot] = {}

        for cluster in np.unique(depotParcels['Cluster']):
            tour = []

            clusterParcels = depotParcels[depotParcels['Cluster'] == cluster]
            depotZone = list(clusterParcels['Orig'])[0]
            destZones = list(clusterParcels['Dest'])
            nParcelsPerZone = dict(zip(destZones, clusterParcels['Parcels']))

            # Nearest neighbor
            tour.append(depotZone)
            for i in range(len(destZones)):
                distances = [skimDistance[
                    tour[i] * nZones + dest] for dest in destZones]
                nextIndex = np.argmin(distances)
                tour.append(destZones[nextIndex])
                destZones.pop(nextIndex)
            tour.append(depotZone)

            # Shuffle the order of tour locations and accept
            # the shuffle if it reduces the tour distance
            nStops = len(tour)
            tour = np.array(tour, dtype=int)
            tourDist = np.sum(skimDistance[tour[:-1] * nZones + tour[1:]])

            if nStops > 4:
                for shiftLocA in range(1, nStops - 1):
                    for shiftLocB in range(1, nStops - 1):
                        if shiftLocA != shiftLocB:
                            swappedTour = tour.copy()
                            swappedTour[shiftLocA] = tour[shiftLocB]
                            swappedTour[shiftLocB] = tour[shiftLocA]
                            swappedTourDist = np.sum(skimDistance[
                                swappedTour[:-1] * nZones + swappedTour[1:]])

                            if swappedTourDist < tourDist:
                                tour = swappedTour.copy()
                                tourDist = swappedTourDist

            # Add current tour to dictionary with all formed tours
            tours[depot][cluster] = list(tour.copy())

            # Store the number of parcels delivered at each
            # location in the tour
            nParcelsPerStop = []
            for i in range(1, nStops - 1):
                nParcelsPerStop.append(nParcelsPerZone[tour[i]])
            nParcelsPerStop.append(0)
            parcelsDelivered[depot][cluster] = list(nParcelsPerStop.copy())

            # Determine the departure time of each trip in the tour
            departureTimesTour = [
                np.where(parcelDepTime > np.random.rand())[0][0] +
                np.random.rand()]

            for i in range(1, nStops - 1):
                orig = tour[i - 1]
                dest = tour[i]
                travTime = skimTravTime[orig * nZones + dest] / 3600
                departureTimesTour.append(
                    departureTimesTour[i - 1] +
                    dropOffTime * nParcelsPerStop[i - 1] +
                    travTime)
            departureTimes[depot][cluster] = list(departureTimesTour.copy())

            nTrips += (nStops - 1)

        print(
            '\t' + str(round((depotCount + 1) / nDepots * 100, 1)) + '%',
            end='\r')

        if root != '':
            root.progressBar['value'] = (
                startValueProgress +
                (endValueProgress - startValueProgress - 1) * (depotCount + 1) / nDepots)

        depotCount += 1

    # --------------------------- Create return table -------------------------
    deliveriesCols = [
        'TourType',
        'CEP',
        'Depot_ID', 'Tour_ID', 'Trip_ID', 'Unique_ID',
        'O_zone', 'D_zone',
        'N_parcels',
        'Traveltime',
        'TourDepTime', 'TripDepTime', 'TripEndTime']
    deliveries = np.zeros((nTrips, len(deliveriesCols)), dtype=object)

    tripcount = 0
    for depot in tours.keys():
        for tour in tours[depot].keys():
            for trip in range(len(tours[depot][tour]) - 1):

                orig = tours[depot][tour][trip]
                dest = tours[depot][tour][trip + 1]

                # Depot to HH (0) or UCC (1), UCC to HH by van (2)/LEVV (3)
                deliveries[tripcount, 0] = tourType

                # Name of the couriers
                if tourType <= 1:
                    deliveries[tripcount, 1] = parcelNodesCEP[depot]
                else:
                    deliveries[tripcount, 1] = 'ConsolidatedUCC'

                # Depot_ID, Tour_ID, Trip_ID,
                # Unique ID under consideration of tour type
                deliveries[tripcount, 2] = depot
                deliveries[tripcount, 3] = f'{depot}_{tour}'
                deliveries[tripcount, 4] = f'{depot}_{tour}_{trip}'
                deliveries[tripcount, 5] = f'{depot}_{tour}_{trip}_{tourType}'

                # Origin and destination
                deliveries[tripcount, 6] = orig
                deliveries[tripcount, 7] = dest

                # Number of parcels
                deliveries[tripcount, 8] = parcelsDelivered[depot][tour][trip]

                # Travel time in hrs
                deliveries[tripcount, 9] = skimTravTime[
                    orig * nZones + dest] / 3600

                # Departure of tour from depot
                deliveries[tripcount, 10] = departureTimes[depot][tour][0]

                # Departure time of trip
                deliveries[tripcount, 11] = departureTimes[depot][tour][trip]

                # End of trip/start of next trip if there is another one
                deliveries[tripcount, 12] = 0.0

                tripcount += 1

    # Place in DataFrame with the right data type per column
    deliveries = pd.DataFrame(deliveries, columns=deliveriesCols)
    dtypes = {
        'TourType': int,
        'CEP': str,
        'Depot_ID': int,
        'Tour_ID': str,
        'Trip_ID': str,
        'Unique_ID': str,
        'O_zone': int,
        'D_zone': int,
        'N_parcels': int,
        'Traveltime': float,
        'TourDepTime': float,
        'TripDepTime': float,
        'TripEndTime': float}
    for col in range(len(deliveriesCols)):
        deliveries[deliveriesCols[col]] = (
            deliveries[deliveriesCols[col]].astype(
                dtypes[deliveriesCols[col]]))

    vehTypes = [
        'Van',
        'Van',
        'Van',
        'LEVV']
    origTypes = [
        'Depot',
        'Depot',
        'UCC',
        'UCC']
    destTypes = [
        'HH',
        'UCC',
        'HH',
        'HH']

    deliveries['VehType'] = vehTypes[tourType]
    deliveries['OrigType'] = origTypes[tourType]
    deliveries['DestType'] = destTypes[tourType]

    if root != '':
        root.progressBar['value'] = endValueProgress

    return deliveries


#%% Function: cluster_parcels

def cluster_parcels(parcels, maxVehicleLoad, skimDistance,
                    root, startValueProgress, endValueProgress):
    '''
    Assign parcels to clusters based on spatial proximity with
    cluster size constraints.
    The cluster variable is added as extra column to the DataFrame.
    '''
    parcels.index = np.arange(len(parcels))

    depotNumbers = np.unique(parcels['DepotNumber'])
    nParcels = len(parcels)
    nParcelsAssigned = 0
    firstClusterID = 0
    nZones = int(len(skimDistance)**0.5)

    parcels['Cluster'] = -1

    print('\t0%', end='\r')

    # First check for depot/destination combination with more than
    # {maxVehicleLoad} parcels.
    # These we don't need to use the clustering algorithm for
    counts = pd.pivot_table(
        parcels,
        values=['VEHTYPE'],
        index=['DepotNumber', 'D_zone'],
        aggfunc=len)

    whereLargeCluster = list(counts.index[
        np.where(counts >= maxVehicleLoad)[0]])

    for x in whereLargeCluster:
        depotNumber = x[0]
        destZone = x[1]

        indices = np.where(
            (parcels['DepotNumber'] == depotNumber) &
            (parcels['D_zone'] == destZone))[0]

        for i in range(int(np.floor(len(indices) / maxVehicleLoad))):
            parcels.loc[indices[:maxVehicleLoad], 'Cluster'] = firstClusterID
            indices = indices[maxVehicleLoad:]

            firstClusterID += 1
            nParcelsAssigned += maxVehicleLoad

            print('\t' + str(round(nParcelsAssigned / nParcels * 100, 1)) + '%',
                  end='\r')

            if root != '':
                root.progressBar['value'] = (
                    startValueProgress +
                    (endValueProgress - startValueProgress - 1) * nParcelsAssigned / nParcels)

    # For each depot, cluster remaining parcels into batches of
    # {maxVehicleLoad} parcels
    for depotNumber in depotNumbers:

        # Select parcels of the depot that are not assigned a cluster yet
        parcelsToFit = parcels[
            (
                (parcels['DepotNumber'] == depotNumber) &
                (parcels['Cluster'] == -1)
            )].copy()

        # Sort parcels descending based on distance to depot
        # so that at the end of the loop the remaining parcels
        # are all nearby the depot and form a somewhat reasonable
        # parcels cluster
        parcelsToFit['Distance'] = skimDistance[
            (parcelsToFit['O_zone'] - 1) * nZones +
            (parcelsToFit['D_zone'] - 1)]
        parcelsToFit = parcelsToFit.sort_values('Distance', ascending=False)
        parcelsToFitIndex = list(parcelsToFit.index)
        parcelsToFit.index = np.arange(len(parcelsToFit))
        dests = np.array(parcelsToFit['D_zone'])

        # How many tours are needed to deliver these parcels
        nTours = int(np.ceil(len(parcelsToFit) / maxVehicleLoad))

        # In the case of 1 tour it's simple,
        # all parcels belong to the same cluster
        if nTours == 1:
            parcels.loc[parcelsToFitIndex, 'Cluster'] = firstClusterID
            firstClusterID += 1
            nParcelsAssigned += len(parcelsToFit)

        # When there are multiple tours needed, the heuristic is a
        # little bit more complex
        else:
            clusters = np.ones(len(parcelsToFit), dtype=int) * -1

            for tour in range(nTours):
                # Select the first parcel for the new cluster
                # that is now initialized
                yetAssigned = (clusters != -1)
                notYetAssigned = np.where(~yetAssigned)[0]
                firstParcelIndex = notYetAssigned[0]
                clusters[firstParcelIndex] = firstClusterID

                # Find the nearest {maxVehicleLoad-1} parcels
                # to this first parcel that are not in a cluster yet
                distances = skimDistance[
                    (dests[firstParcelIndex] - 1) * nZones + (dests - 1)]
                distances[notYetAssigned[0]] = 99999
                distances[yetAssigned] = 99999
                clusters[np.argsort(distances)[
                    :(maxVehicleLoad - 1)]] = firstClusterID

                firstClusterID += 1

            # Group together remaining parcels, these are all nearby the depot
            yetAssigned = (clusters != -1)
            notYetAssigned = np.where(~yetAssigned)[0]
            clusters[notYetAssigned] = firstClusterID
            firstClusterID += 1

            parcels.loc[parcelsToFitIndex, 'Cluster'] = clusters
            nParcelsAssigned += len(parcelsToFit)

            print('\t' + str(round(nParcelsAssigned / nParcels * 100, 1)) + '%',
                  end='\r')

            if root != '':
                root.progressBar['value'] = (
                    startValueProgress +
                    (endValueProgress - startValueProgress - 1) * nParcelsAssigned / nParcels)

    parcels['Cluster'] = parcels['Cluster'].astype(int)

    return parcels


#%% Function: do_crowdshipping

def do_crowdshipping(parcels, zones, nIntZones, nZones, zoneDict,
                     zonesX, zonesY,
                     skimDistance, skimTravTime,
                     nFirstZonesCS, parcelShareCRW, modes,
                     zone_gemeente_dict, segsDetail,
                     datapathO, label, log_file,
                     root):
    '''
    Do all crowdshipping calculations and export files for
    the crowdshipping use case.
    '''
    start_time_cs = time.time()

    print('Crowdshipping use case...')
    log_file.write('Crowdshipping use case...\n')

    print('\tGet parcel demand...')
    log_file.write('\tGet parcel demand...\n')

    nParcels = len(parcels)

    randSelectionCRW = (
        (np.random.rand(nParcels) < parcelShareCRW) &
        (parcels['D_zone'] < nFirstZonesCS))
    indicesCRW = np.where(randSelectionCRW)[0]
    indicesREF = np.where(~randSelectionCRW)[0]

    # The parcels to use for crowdshipping
    parcelsCRW = parcels.loc[indicesCRW, :]
    parcelsCRW.index = parcelsCRW['Parcel_ID']

    # The parcels to ship regularly by parcel couriers
    parcels = parcels.loc[indicesREF, :]
    parcels.index = parcels['Parcel_ID']

    # Add number of parcels to zonal data
    zones['parcels'] = [
        np.sum(parcels['D_zone'] == (i + 1))
        for i in range(nIntZones)]
    zones['parcelsCS'] = [
        np.sum(parcelsCRW['D_zone'] == (i + 1))
        for i in range(nIntZones)]
    nParcels = int(zones[:nFirstZonesCS]["parcels"].sum())
    nParcelsCS = int(zones[:nFirstZonesCS]["parcelsCS"].sum())

    # Dictionary of all zones per municipality
    gemeente_zone_dict = {}
    gemeente_id_dict = {}
    id_gemeente_dict = {}
    count = 0

    for gemeente in np.unique(zones[:nFirstZonesCS]['Gemeentena']):
        gemeente_zone_dict[gemeente] = np.where(
            zones['Gemeentena'] == gemeente)[0]
        gemeente_id_dict[gemeente] = count
        id_gemeente_dict[count] = gemeente
        count += 1

    # Initialize an array for the crowdshipping parcels
    parcelsCS_cols = {
        'id': 0,
        'orig': 1,
        'dest': 2,
        'orig_skim': 3,
        'dest_skim': 4,
        'gemeente': 5,
        'X_ORIG': 6,
        'Y_ORIG': 7,
        'X_DEST': 8,
        'Y_DEST': 9,
        'TravelTime_car': 10,
        'TravelDistance': 11,
        'vector': 12,
        'status': 13,
        'traveller': 14,
        'modal choice': 15,
        'detour_time': 16,
        'detour_dist': 17,
        'compensation': 18}

    parcelsCS_array = np.zeros(
        (nParcelsCS, len(parcelsCS_cols)),
        dtype=object)

    # Dictionary from (key) parcel ID as used in loop below
    # to (value) parcel ID as used in input parcel demand file
    parc_id_dict = {}

    # Create object for crowdshipping parcels
    count = 0
    for i in range(nFirstZonesCS):
        nParcelsZone = int(zones.at[zoneDict[i + 1], 'parcelsCS'])
        parc_ids = np.array(parcelsCRW.loc[
            parcelsCRW['D_zone'] == (i + 1), 'Parcel_ID'])

        if nParcelsZone > 0:
            dest_skim = i + 1
            dest = zoneDict[dest_skim]
            gemeente = zones.at[dest, 'Gemeentena']
            x_dest = zonesX[dest]
            y_dest = zonesY[dest]
            status = "ordered"
            possible_origins = gemeente_zone_dict[gemeente]

            ratio_origins = np.zeros(nIntZones)
            ratio_origins[possible_origins] = segsDetail[possible_origins]
            ratio_origins = np.cumsum(ratio_origins)
            ratio_origins /= ratio_origins[-1]

            for n in range(nParcelsZone):
                parc_id = n + count
                orig_skim = np.where(
                    ratio_origins >= np.random.rand())[0][0] + 1
                orig = zoneDict[orig_skim]
                x_orig = zonesX[orig]
                y_orig = zonesY[orig]
                trav_time = skimTravTime[
                    (orig_skim - 1) * nZones + (dest_skim - 1)] / 3600
                trav_dist = skimDistance[
                    (orig_skim - 1) * nZones + (dest_skim - 1)] / 1000
                vector = [
                    x_dest - x_orig,
                    y_dest - y_orig]
                parcelsCS_array[n + count] = [
                    parc_id,
                    orig, dest,
                    orig_skim, dest_skim,
                    gemeente,
                    x_orig, y_orig, x_dest, y_dest,
                    trav_time, trav_dist,
                    vector, status,
                    0, 0, 0, 0, 0]
                parc_id_dict[parc_id] = parc_ids[n]

        count += nParcelsZone

    # Recode municipalities to numberic IDs for faster checking
    # in parcel assignment loop
    parcelsCS_array[:, 5] = np.array(
        [gemeente_id_dict[x] for x in parcelsCS_array[:, 5]],
        dtype=int)

    # Place crowdshipping parcel in DataFrame with headers
    parcelsCS_df = pd.DataFrame(parcelsCS_array, columns=parcelsCS_cols)

    if root != '':
        root.progressBar['value'] = 2.0

    print('\tGet potential crowdshippers...')
    log_file.write('\tGet potential crowdshippers...\n')

    # Editing OD-matrices of passenger travellers that are willing to crowdship
    trav_array_cols = {
        'id': 0,
        'orig': 1,
        'dest': 2,
        'orig_skim': 3,
        'dest_skim': 4,
        'vector': 5,
        'gemeenten': 6,
        'parcel': 7,
        'status': 8}

    for mode in modes:
        OD_array = modes[mode]['OD_array']
        trav_array = np.zeros(
            (OD_array.sum().sum(), len(trav_array_cols)),
            dtype=object)

        start_id = sum(d['n_trav'] for d in modes.values() if d)
        count = 0

        for i, row in enumerate(OD_array):
            for j in np.where(row > 0)[0]:

                if i != j:
                    n = row[j]

                    orig_skim = i + 1
                    dest_skim = j + 1
                    orig = int(zoneDict[orig_skim])
                    dest = int(zoneDict[dest_skim])

                    vector = [
                        zonesX[dest] - zonesX[orig],
                        zonesY[dest] - zonesY[orig]]

                    gemeente = [
                        zone_gemeente_dict[orig_skim],
                        zone_gemeente_dict[dest_skim]]

                    for N in range(n):
                        trav_id = N + count + start_id
                        trav_array[N + count] = [
                            trav_id,
                            orig, dest,
                            orig_skim, dest_skim,
                            vector, gemeente,
                            0, 0]

                    count += n

        trav_array = trav_array[~np.all(trav_array == 0, axis=1)]

        # Recode municipalities to numberic IDs for
        # faster checking in parcel assignment loop
        trav_array[:, 6] = [
            [gemeente_id_dict[x[0]], gemeente_id_dict[x[1]]]
            for x in trav_array[:, 6]]

        modes[mode]['n_trav'] = int(len(trav_array))
        modes[mode]['trav_array'] = trav_array

    if root != '':
        root.progressBar['value'] = 4.0

    # Assign parcels to crowdshippers
    parcelsToBeAssigned = np.array([True for i in range(nParcelsCS)])
    nParcelsAssigned = 0

    # Variables to keep track of progress
    nTravellersTotal = sum([len(modes[mode]['trav_array']) for mode in modes])
    travellerCount = 0

    for mode in modes:

        message = (
            "\tAssigning " +
            str(mode) +
            " travellers to parcels...")
        print(message)
        log_file.write(message + "\n")

        skimTravTime = modes[mode]['skim_time']
        dropoff_time = modes[mode]['dropoff_time']
        VoT = modes[mode]['VoT']

        nTravellers = len(modes[mode]['trav_array'])

        # Initialize variable with orig/dest municipality of
        # previously checked traveller
        prevMunicipality = [-1, -1]

        for i, traveller in enumerate(modes[mode]['trav_array']):

            # Stop in the case all crowdshipping-eligible parcels
            # are assigned to a bringer
            if nParcelsAssigned == nParcelsCS:
                break

            offers_dict = {}
            offers2_dict = {}

            trav_orig = traveller[3]
            trav_dest = traveller[4]
            trip_dist = skimDistance[
                (trav_orig - 1) * nZones + (trav_dest - 1)] / 1000
            trip_time = skimTravTime[
                (trav_orig - 1) * nZones + (trav_dest - 1)] / 3600

            # Boolean: Parcels for which no carrier has been found yet
            checkUnassigned = parcelsToBeAssigned

            # Boolean: Parcels with a reasonable distance in relation
            # to the traveller's trip distance
            checkDistance = (
                (trip_dist / parcelsCS_array[:, 11] < 4) &
                (trip_dist / parcelsCS_array[:, 11] > 0.5))

            # Boolean: Parcels within the municipality of traveller's
            # origin / destination
            # (Only needs to be recalculated if the traveller has
            # different orig/dest from previous traveller)
            if prevMunicipality != traveller[6]:
                checkMunicipality = (
                    (parcelsCS_array[:, 5] == traveller[6][0]) |
                    (parcelsCS_array[:, 5] == traveller[6][1]))

            # Now select the parcels that comply to the above
            # three boolean checks
            parcelsToConsider = parcelsCS_array[
                (checkUnassigned & checkMunicipality & checkDistance)]

            # Determine detour due to delivering parcel
            parc_orig = np.array(parcelsToConsider[:, 3], dtype=int)
            parc_dest = np.array(parcelsToConsider[:, 4], dtype=int)
            dist_traveller_parcel = skimDistance[
                (trav_orig - 1) * nZones + (parc_orig - 1)] / 1000
            dist_parcel_trip = skimDistance[
                (parc_orig - 1) * nZones + (parc_dest - 1)] / 1000
            dist_customer_end = skimDistance[
                (parc_dest - 1) * nZones + (trav_dest - 1)] / 1000
            CS_trip_dist = (
                dist_traveller_parcel +
                dist_parcel_trip +
                dist_customer_end)
            traveller_detour = CS_trip_dist - trip_dist
            extra_parcel_dist = traveller_detour - dist_parcel_trip
            relative_extra_parcel_dist = extra_parcel_dist / dist_parcel_trip

            # Determine compensation offered to traveller
            whereTripsWithinThreshold = np.where(
                relative_extra_parcel_dist <
                modes[mode]['relative_extra_parcel_dist_threshold'])[0]

            for trip in whereTripsWithinThreshold:
                CS_compensation = np.log((dist_parcel_trip[trip]) + 5)
                offers_dict[parcelsToConsider[trip, 0]] = {
                    'distance': dist_parcel_trip[trip],
                    'rel_detour': relative_extra_parcel_dist[trip],
                    'compensation': CS_compensation}

            # Traveller chooses the parcel to ship
            if offers_dict:
                offered_parcels = sorted(
                    offers_dict,
                    key=lambda x: (offers_dict[x]['rel_detour']))[:3]

                # Search for best parcel
                for parcel in offered_parcels:
                    parc_orig = parcelsCS_array[parcel, 3]
                    parc_dest = parcelsCS_array[parcel, 4]
                    traveller_detour_time = (
                        skimTravTime[
                            (trav_orig - 1) * nZones + (parc_orig - 1)] +
                        skimTravTime[
                            (parc_orig - 1) * nZones + (parc_dest - 1)] +
                        skimTravTime[
                            (parc_dest - 1) * nZones + (trav_dest - 1)])
                    traveller_detour_time /= 3600
                    traveller_detour_time -= trip_time
                    CS_utility = (
                        offers_dict[parcel]['compensation'] /
                        (traveller_detour_time + 2 * dropoff_time))
                    offers2_dict[parcel] = {'utility': CS_utility}

                best_parcel = offered_parcels[0]

                # Traveller chooses whether to ship this 'best' parcel
                # based on value of time
                if offers2_dict[best_parcel]['utility'] > VoT:
                    modes[mode]['trav_array'][i, 7] = int(best_parcel)
                    modes[mode]['trav_array'][i, 8] = str('shipping')
                    parcelsToBeAssigned[best_parcel] = False
                    nParcelsAssigned += 1

                    parcelsCS_array[best_parcel, 13] = 'carrier found'
                    parc_orig = parcelsCS_array[best_parcel, 3]
                    parc_dest = parcelsCS_array[best_parcel, 4]
                    traveller_detour_time = (
                        skimTravTime[
                            (trav_orig - 1) * nZones + (parc_orig - 1)] +
                        skimTravTime[
                            (parc_orig - 1) * nZones + (parc_dest - 1)] +
                        skimTravTime[
                            (parc_dest - 1) * nZones + (trav_dest - 1)] -
                        skimTravTime[
                            (trav_orig - 1) * nZones + (trav_dest - 1)]) / 3600
                    traveller_detour_distance = (
                        skimDistance[
                            (trav_orig - 1) * nZones + (parc_orig - 1)] +
                        skimDistance[
                            (parc_orig - 1) * nZones + (parc_dest - 1)] +
                        skimDistance[
                            (parc_dest - 1) * nZones + (trav_dest - 1)] -
                        skimDistance[
                            (trav_orig - 1) * nZones + (trav_dest - 1)]) / 1000
                    parcelsCS_array[best_parcel, 14] = traveller[0]
                    parcelsCS_array[best_parcel, 15] = mode
                    parcelsCS_array[best_parcel, 16] = traveller_detour_time
                    parcelsCS_array[best_parcel, 17] = traveller_detour_distance
                    parcelsCS_array[best_parcel, 18] = offers_dict[best_parcel]['compensation']

            travellerCount += 1
            prevMunicipality = traveller[6]

            if i % int(nTravellers / 100) == 0:
                print('\t\t' + str(round(i / nTravellers * 100, 1)) + "% ", end='\r')
                if root != '':
                    root.progressBar['value'] = (
                        4.0 +
                        (52.0 - 4.0) * (travellerCount / nTravellersTotal))

    # Recode municipalities back to string
    parcelsCS_array[:, 5] = [
        id_gemeente_dict[x] for x in parcelsCS_array[:, 5]]

    # Put parcels back in DataFrame again
    parcelsCS_df = pd.DataFrame(parcelsCS_array, columns=parcelsCS_cols)

    # Parcels that are not assigned to an occassional carrier
    # will need to be scheduled in the regular scheduling procedure
    unassignedParcelIDs = np.array(parcelsCS_df.loc[
        parcelsCS_df['status'] != 'carrier found', 'id'])
    unassignedParcelIDs = [parc_id_dict[x] for x in unassignedParcelIDs]
    parcels = parcels.append(parcelsCRW.loc[unassignedParcelIDs, :])

    print("\tWriting crowdshipping output to CSV and GeoJSON...")
    log_file.write("\tWriting crowdshipping output to CSV and GeoJSON...\n")

    # Write CSV
    parcelsCS_df.to_csv(
        datapathO + f'ParcelDemand_{label}_Crowdshipping.csv',
        index=False)

    # Write GeoJSON
    for mode in modes:
        trav_array = modes[mode]['trav_array']
        tours = pd.DataFrame()

        for i, traveller in enumerate(trav_array[trav_array[:, 8] == 'shipping']):
            trav_ORIG = traveller[1]
            trav_DEST = traveller[2]
            parc_ORIG = parcelsCS_array[int(traveller[7]), 1]
            parc_DEST = parcelsCS_array[int(traveller[7]), 2]
            trav_orig = traveller[3]
            trav_dest = traveller[4]
            parc_orig = parcelsCS_array[int(traveller[7]), 3]
            parc_dest = parcelsCS_array[int(traveller[7]), 4]

            for j in range(3):
                tours.at[i * 3 + j, 'TOUR_ID'] = i
                tours.at[i * 3 + j, 'TRIP_ID'] = str(i) + "_" + str(j)
                tours.at[i * 3 + j, 'traveller_ID'] = traveller[0]
                tours.at[i * 3 + j, 'parcel_ID'] = traveller[7]
                tours.at[i * 3 + j, 'mode'] = mode
                if j == 0:
                    tours.at[i * 3 + j, 'skim_dist'] = skimDistance[
                        (trav_orig - 1) * nZones + (parc_orig - 1)] / 1000
                    tours.at[i * 3 + j, 'ORIG'] = trav_ORIG
                    tours.at[i * 3 + j, 'DEST'] = parc_ORIG
                if j == 1:
                    tours.at[i * 3 + j, 'skim_dist'] = skimDistance[
                        (parc_orig - 1) * nZones + (parc_dest - 1)] / 1000
                    tours.at[i * 3 + j, 'ORIG'] = parc_ORIG
                    tours.at[i * 3 + j, 'DEST'] = parc_DEST
                if j == 2:
                    tours.at[i * 3 + j, 'skim_dist'] = skimDistance[
                        (parc_dest - 1) * nZones + (trav_dest - 1)] / 1000
                    tours.at[i * 3 + j, 'ORIG'] = parc_DEST
                    tours.at[i * 3 + j, 'DEST'] = trav_DEST

        if not tours.empty:
            for i, ORIG in enumerate(tours['ORIG']):
                tours.at[i, 'X_ORIG'] = zones.loc[ORIG]['X']
                tours.at[i, 'Y_ORIG'] = zones.loc[ORIG]['Y']
            for i, DEST in enumerate(tours['DEST']):
                tours.at[i, 'X_DEST'] = zones.loc[DEST]['X']
                tours.at[i, 'Y_DEST'] = zones.loc[DEST]['Y']

            # ----- GeoJSON ---
            Ax = np.array(tours['X_ORIG'], dtype=str)
            Ay = np.array(tours['Y_ORIG'], dtype=str)
            Bx = np.array(tours['X_DEST'], dtype=str)
            By = np.array(tours['Y_DEST'], dtype=str)
            nTrips = len(tours)

            filename = (
                datapathO +
                f'ParcelSchedule_{label}_Crowdshipping_{mode}.geojson')

            with open(filename, 'w') as geoFile:
                geoFile.write(
                    '{\n' +
                    '"type": "FeatureCollection",\n' +
                    '"features": [\n')

                for i in range(nTrips - 1):
                    outputStr = (
                        '{ "type": "Feature", "properties": ' +
                        str(tours.loc[i, :].to_dict()).replace("'", '"') +
                        ', "geometry": ' +
                        '{ "type": "LineString", "coordinates": [ [ ' +
                        Ax[i] + ', ' + Ay[i] + ' ], [ ' +
                        Bx[i] + ', ' + By[i] + ' ] ] } },\n')
                    geoFile.write(outputStr)

                # Bij de laatste feature moet er geen komma aan het einde
                i += 1
                outputStr = (
                    '{ "type": "Feature", "properties": ' +
                    str(tours.loc[i, :].to_dict()).replace("'", '"') +
                    ', "geometry": ' +
                    '{ "type": "LineString", "coordinates": [ [ ' +
                    Ax[i] + ', ' + Ay[i] + ' ], [ ' +
                    Bx[i] + ', ' + By[i] + ' ] ] } }\n')
                geoFile.write(outputStr)
                geoFile.write(']\n')
                geoFile.write('}')

    # Print summary of crowdshipping results
    n_parcels_total = nParcels
    n_parcels_CS = len(parcelsCS_array)
    n_parcels_CS_delivered = (parcelsCS_array[:, 13] == 'carrier found').sum()
    delivered_percentage = round(
        n_parcels_CS_delivered / n_parcels_CS * 100, 2)

    avg_dist = round(
        parcelsCS_array[:, 11].mean(), 2)
    avg_detour = round(
        parcelsCS_array[:, 17].sum() / n_parcels_CS_delivered, 2)
    total_detour = int(round(
        parcelsCS_array[:, 17].sum(), -1))

    bike_parcels = len(
        parcelsCS_array[parcelsCS_array[:, 15] == 'fiets'][:, 17])
    bike_km = int(round(
        parcelsCS_array[parcelsCS_array[:, 15] == 'fiets'][:, 17].sum(), -1))
    bike_km_avg = round(
        parcelsCS_array[parcelsCS_array[:, 15] == 'fiets'][:, 17].mean(), 2)

    car_parcels = len(
        parcelsCS_array[parcelsCS_array[:, 15] == 'auto'][:, 17])
    car_km = int(round(
        parcelsCS_array[parcelsCS_array[:, 15] == 'auto'][:, 17].sum(), -1))
    car_km_avg = round(
        parcelsCS_array[parcelsCS_array[:, 15] == 'auto'][:, 17].mean(), 2)

    avg_compensation = round(
        parcelsCS_array[
            parcelsCS_array[:, 13] == 'carrier found'][:, 18].mean(), 2)

    message = '\tSummary of outcomes:\n' + (
        (
            "\t\tA total of " +
            str(n_parcels_total) +
            " parcels is ordered in the system. " +
            str(n_parcels_CS) +
            " are eligible for CS of which " +
            str(n_parcels_CS_delivered) +
            " have been delivered through CS (=" +
            str(delivered_percentage) + "%)." + "\n") +
        (
            "\t\tThe average distance of CS parcel trips is " +
            str(avg_dist) +
            "km. For the delivered parcels, the average detour is " +
            str(avg_detour) +
            "km." + "\n") +
        (
            "\t\tFor the CS deliveries, " +
            str(total_detour) +
            " extra kilometers are driven." +
            " The detours are distributed to modes as follows:" + "\n") +
        (
            "\t\t\tBike: " +
            str(bike_parcels) +
            " parcels, total of " +
            str(bike_km) +
            "km (" +
            str(bike_km_avg) +
            "km average) \n") +
        (
            "\t\t\tCar:  " +
            str(car_parcels) +
            " parcels, total of " +
            str(car_km) +
            "km (" +
            str(car_km_avg) +
            "km average) \n") +
        (
            "\t\tThe average provided compensation for the occasional" +
            " carriers is " + str(avg_compensation) + " euro."))
    print(message)
    log_file.write(message + '\n')

    totaltime_cs = round(time.time() - start_time_cs, 2)
    print("\tCrowdshipping calculations took: %s seconds." % (totaltime_cs))
    log_file.write(
        "\tCrowdshipping calculations took: %s seconds.\n" % (totaltime_cs))

    if root != '':
        root.progressBar['value'] = 55.0


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
    varDict['SEGS']  = varDict['INPUTFOLDER'] + 'SEGS2016.csv'
    varDict['COMMODITYMATRIX']    = varDict['INPUTFOLDER'] + 'CommodityMatrixNUTS3_2016.csv'
    varDict['PARCELNODES']        = varDict['INPUTFOLDER'] + 'parcelNodes_v2.shp'
    varDict['DISTRIBUTIECENTRA']  = varDict['INPUTFOLDER'] + 'distributieCentra.csv'
    varDict['NSTR_TO_LS']         = varDict['INPUTFOLDER'] + 'nstrToLogisticSegment.csv'
    varDict['MAKE_DISTRIBUTION']  = varDict['INPUTFOLDER'] + 'MakeDistribution.csv'
    varDict['USE_DISTRIBUTION']   = varDict['INPUTFOLDER'] + 'UseDistribution.csv'
    varDict['SUP_COORDINATES_ID'] = varDict['INPUTFOLDER'] + 'SupCoordinatesID.csv'
    varDict['CORRECTIONS_TONNES'] = varDict['INPUTFOLDER'] + 'CorrectionsTonnes2016.csv'
    varDict['DEPTIME_FREIGHT'] = varDict['INPUTFOLDER'] + 'departureTimePDF.csv'
    varDict['DEPTIME_PARCELS'] = varDict['INPUTFOLDER'] + 'departureTimeParcelsCDF.csv'

    varDict['COST_VEHTYPE']        = varDict['PARAMFOLDER'] + 'Cost_VehType_2016.csv'
    varDict['COST_SOURCING']       = varDict['PARAMFOLDER'] + 'Cost_Sourcing_2016.csv'
    varDict['MRDH_TO_NUTS3']       = varDict['PARAMFOLDER'] + 'MRDHtoNUTS32013.csv'
    varDict['NUTS3_TO_MRDH']       = varDict['PARAMFOLDER'] + 'NUTS32013toMRDH.csv'
    varDict['VEHICLE_CAPACITY']    = varDict['PARAMFOLDER'] + 'CarryingCapacity.csv'
    varDict['LOGISTIC_FLOWTYPES']  = varDict['PARAMFOLDER'] + 'LogFlowtype_Shares.csv'
    varDict['PARAMS_TOD']          = varDict['PARAMFOLDER'] + 'Params_TOD.csv'
    varDict['PARAMS_SSVT']         = varDict['PARAMFOLDER'] + 'Params_ShipSize_VehType.csv'
    varDict['PARAMS_ET_FIRST']     = varDict['PARAMFOLDER'] + 'Params_EndTourFirst.csv'
    varDict['PARAMS_ET_LATER']     = varDict['PARAMFOLDER'] + 'Params_EndTourLater.csv'
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

    varDict['PARCELS_PER_HH'] = 0.112
    varDict['PARCELS_PER_EMPL'] = 0.041
    varDict['PARCELS_MAXLOAD'] = 180
    varDict['PARCELS_DROPTIME'] = 120
    varDict['PARCELS_SUCCESS_B2C'] = 0.75
    varDict['PARCELS_SUCCESS_B2B'] = 0.95
    varDict['PARCELS_GROWTHFREIGHT'] = 1.0

    varDict['MICROHUBS']    = varDict['INPUTFOLDER'] + 'Microhubs.csv'
    varDict['VEHICLETYPES'] = varDict['INPUTFOLDER'] + 'Microhubs_vehicleTypes.csv'

    varDict['SHIPMENTS_REF'] = ""
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
    varDict['CRW_PARCELSHARE']  = 0.03
    varDict['CRW_MODEPARAMS']   = varDict['PARAMFOLDER'] + 'Params_UseCase_CrowdShipping.csv'
    varDict['CRW_PDEMAND_CAR']  = varDict['INPUTFOLDER'] + 'MRDH_2016_Auto_Etmaal.mtx'
    varDict['CRW_PDEMAND_BIKE'] = varDict['INPUTFOLDER'] + 'MRDH_2016_Fiets_Etmaal.mtx'

    varDict['SHIFT_FREIGHT_TO_COMB1'] = ""

    varDict['IMPEDANCE_SPEED'] = 'V_FR_OS'

    varDict['LABEL'] = 'REF'
#    labelsMIC = [
#        'MIC_individual_EB' 'MIC_individual_AR',
#        'MIC_individual_ET', 'MIC_individual_EQ',
#        'MIC_individual_EM', 'MIC_individual_EDV',
#        'MIC_individual_LEV', 
#        'MIC_collab_EB', 'MIC_collab_AR',
#        'MIC_collab_ET', 'MIC_collab_EQ',
#        'MIC_collab_EM', 'MIC_collab_EDV',
#        'MIC_collab_LEV']

    # Run the module
    main(varDict)
    
