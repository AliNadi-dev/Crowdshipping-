import numpy as np
import pandas as pd
import time
import datetime
import os.path
from __functions__ import read_mtx, read_shape

# Modules nodig voor de user interface
import tkinter as tk
from tkinter.ttk import Progressbar
import zlib
import base64
import tempfile
from threading import Thread


#%% Main

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
        self.root.title("Progress Output Indicators")
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

        # ------------------- Open output files -------------------------------

        print("Importing data...")

        start_time = time.time()

        root = args[0]
        varDict = args[1]

        if root != '':
            root.progressBar['value'] = 0

        # Define folders relative to current datapath
        datapathI = varDict['INPUTFOLDER']
        datapathO = varDict['OUTPUTFOLDER']
        datapathP = varDict['PARAMFOLDER']
        zonesPath = varDict['ZONES']
        skimTravTimePath = varDict['SKIMTIME']
        skimDistancePath = varDict['SKIMDISTANCE']  
        label = varDict['LABEL']

        datapathOI = datapathO + 'Output indicators/'

        log_file = open(f"{datapathO}Logfile_OutputIndicator.log", "w")
        log_file.write(
            "Start simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")
        log_file.write("Importing data...\n")

        if not os.path.isdir(datapathOI) and os.path.isdir(datapathO):
            os.mkdir(datapathOI)

        outfile = open(f"{datapathOI}Output_OutputIndicator_{label}.csv", "w")
        sep = ','

        # ---------------------- Import data ----------------------------------

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
        dimShipSize = pd.read_csv(
            varDict['DIMFOLDER'] + 'shipment_size.txt',
            sep='\t')
        dimET = pd.read_csv(
            varDict['DIMFOLDER'] + 'emission_type.txt',
            sep='\t')
        dimMunicipality = pd.read_csv(
            varDict['DIMFOLDER'] + 'municipality.txt',
            sep='\t')

        vtNums = np.array(dimVT['ID'], dtype=int)
        vtNames = np.array(dimVT['Comment'], dtype=str)
        lsNames = np.array(dimLS['Comment'], dtype=str)
        etNames = np.array(dimET['Comment'], dtype=str)

        nVT = len(vtNames)
        nLS = len(lsNames)
        nNSTR = len(dimNSTR) - 1
        nCombType = len(dimCombType)
        nShipSize = len(dimShipSize)

        if root != '':
            root.progressBar['value'] = 0.1

        print('\tImporting shipments...')
        log_file.write('\tImporting shipments...\n')

        shipments = pd.read_csv(
            f"{datapathO}Shipments_{label}.csv",
            index_col=None)

        if root != '':
            root.progressBar['value'] = 5.0

        print('\tImporting tours...')
        log_file.write('\tImporting tours...\n')

        trips = pd.read_csv(f'{datapathO}Tours_{label}.csv')
        trips['TOUR_ID'] = [
            str(trips.at[i, 'CARRIER_ID']) + '_' + str(trips.at[i, 'TOUR_ID'])
            for i in trips.index]

        if root != '':
            root.progressBar['value'] = 10.0

        print('\tImporting parcels...')
        log_file.write('\tImporting parcels...\n')

        parcels = pd.read_csv(f"{datapathO}ParcelDemand_{label}.csv")
        parcelTrips = pd.read_csv(f"{datapathO}ParcelSchedule_{label}.csv")
        parcels = parcels.rename(
            columns={
                'O_zone': 'ORIG',
                'D_zone': 'DEST'})
        parcelTrips = parcelTrips.rename(
            columns={
                'O_zone': 'ORIG',
                'D_zone': 'DEST',
                'Trip_ID': 'TRIP_ID',
                'Tour_ID': 'TOUR_ID'})  

        if root != '':
            root.progressBar['value'] = 13.0

        print('\tPreparing tours/parcels...')
        log_file.write('\tPreparing tours/parcels...\n')

        temp = pd.pivot_table(
            parcelTrips,
            values='TRIP_ID',
            index='TOUR_ID',
            aggfunc=len)
        nTripsParcelTour = {}
        for i in temp.index:
            nTripsParcelTour[i] = temp.at[i, 'TRIP_ID']
        parcelTrips['N_trips_tour'] = [
            nTripsParcelTour[tourID] for tourID in parcelTrips['TOUR_ID']]

        tours = trips[trips['TRIP_ID'] == 0]
        parcelTours = parcelTrips[
            [parcelTrips['TRIP_ID'][i][-2:] == '_0'
             for i in parcelTrips.index]]

        if root != '':
            root.progressBar['value'] = 20.0

        print('\tImporting van trips...')
        log_file.write('\tImporting van trips...\n')

        vanTripsFound = (
            os.path.isfile(datapathO + 'TripsVanService.mtx') and
            os.path.isfile(datapathO + 'TripsVanConstruction.mtx'))

        if vanTripsFound:
            vanTripsService = read_mtx(
                datapathO + 'TripsVanService.mtx')
            vanTripsConstruction = read_mtx(
                datapathO + 'TripsVanConstruction.mtx')
        else:
            print('\tVan trips not found in outputfolder...')
            log_file.write('\tVan trips not found in outputfolder...\n')

        if root != '':
            root.progressBar['value'] = 30.0

        # Skims with travel times and distances
        print('\tImporting skims...')
        log_file.write('\tImporting skims...\n')

        skimTravTime = read_mtx(skimTravTimePath)
        skimDistance = read_mtx(skimDistancePath)
        nZones = int(len(skimTravTime)**0.5)

        if root != '':
            root.progressBar['value'] = 40.0

        # Import external zones demand and coordinates
        superCoordinates = pd.read_csv(f'{datapathI}SupCoordinatesID.csv')
        nSuperZones = len(superCoordinates)

        # Import zonal data
        print('\tImporting zonal data...')
        log_file.write('\tImporting zonal data...\n')

        zonesShape = read_shape(zonesPath)
        zonesShape.sort_values('AREANR')
        zonesShape.index = zonesShape['AREANR']
        zoneID = np.array(zonesShape['AREANR'])
        nInternalZones = len(zonesShape)
        zoneDict = dict(np.transpose(np.vstack((
            np.arange(nInternalZones),
            zoneID))))
        for i in range(nSuperZones):
            zoneDict[nInternalZones + i] = superCoordinates['AREANR'][i]
        invZoneDict = dict((v, k) for k, v in zoneDict.items())
        zoneID = np.arange(nInternalZones)

        if root != '':
            root.progressBar['value'] = 42.0

        # The distance of each shipment and trip in kilometers
        print('\tCalculating distance of each trip...')
        log_file.write('\tCalculating distance of each trip...\n')

        trips['DIST'] = skimDistance[np.array([
            invZoneDict[trips['ORIG'][i]] * nZones +
            invZoneDict[trips['DEST'][i]]
            for i in trips.index], dtype=int)] / 1000

        parcelTrips['DIST'] = skimDistance[np.array([
            invZoneDict[parcelTrips['ORIG'][i]] * nZones +
            invZoneDict[parcelTrips['DEST'][i]]
            for i in parcelTrips.index], dtype=int)] / 1000

        shipments['DIST'] = skimDistance[np.array([
            invZoneDict[shipments['ORIG'][i]] * nZones +
            invZoneDict[shipments['DEST'][i]]
            for i in shipments.index], dtype=int)] / 1000

        if root != '':
            root.progressBar['value'] = 50.0

        # Import the loaded network
        print('\tImporting loaded network...')
        log_file.write('\tImporting loaded network...\n')

        linksLoaded = pd.read_csv(
            datapathO + 'links_loaded_' + str(label) + '_intensities.csv')

        intCols = [
            'LINKNR', 'A', 'B', 'ZEZ',
            'N_LS0', 'N_LS1', 'N_LS2',
            'N_LS3', 'N_LS4', 'N_LS5',
            'N_LS6', 'N_LS7',
            'N_VEH0', 'N_VEH1', 'N_VEH2', 'N_VEH3',
            'N_VEH4', 'N_VEH5', 'N_VEH6', 'N_VEH7',
            'N_VEH8', 'N_VEH9',
            'N_TOT']
        linksLoaded[intCols] = linksLoaded[intCols].astype(int)
        linksLoaded['Gemeentena'] = linksLoaded['Gemeentena'].astype(str)

        linksLoadedRdam = linksLoaded.loc[linksLoaded['Gemeentena'] == 'Rotterdam', :]
        linksLoadedDH = linksLoaded.loc[linksLoaded['Gemeentena'] == "'s-Gravenhage", :]
        linksLoadedZH = linksLoaded.loc[linksLoaded['Gemeentena'] != "nan", :]
        linksLoadedZEZ = linksLoaded.loc[linksLoaded['ZEZ'] == 1, :]

        if root != '':
            root.progressBar['value'] = 60.0

        # ---------------------- Shipment sizes -------------------------------

        print("Calculating and exporting output indicators...")
        log_file.write("Calculating and exporting output indicators...\n")

        print("\tShipments")
        log_file.write("\tShipments\n")

        # Actual shipment sizes
        shipments['WEIGHT_LEVELS'] = 0
        for i in range(nShipSize):
            lowerSize, upperSize = dimShipSize.loc[i, ['Lower', 'Upper']]
            shipments.loc[
                (shipments['WEIGHT'] >= lowerSize) & (shipments['WEIGHT'] < upperSize),
                'WEIGHT_LEVELS'] = i
        shipmentSizeHist = np.unique(
            shipments['WEIGHT_LEVELS'],
            return_counts=True)
        shipmentSizeLabels = np.array(dimShipSize['Comment'], dtype=str)

        outfile.write('Shipment size; actual weight (freight)' + sep + '\n')
        outfile.write(sep + 'Weight (tonnes)' + sep + 'Number of shipments\n')

        for i in range(nShipSize):
            outfile.write(
                sep + shipmentSizeLabels[i] +
                sep + str(shipmentSizeHist[1][i]) + '\n')

        # Chosen shipment size category
        shipmentSizeHist = np.unique(
            shipments['WEIGHT_CAT'],
            return_counts=True)
        outfile.write(
            '\nShipment size; chosen weight class (freight)' + sep + '\n')
        outfile.write(sep + 'Weight (tonnes)' + sep + 'Number of shipments\n')

        for i in range(nShipSize):
            outfile.write(
                sep + shipmentSizeLabels[i] +
                sep + str(shipmentSizeHist[1][i]) + '\n')

        # Chosen vehicle type per shipment
        nShipsVeh = np.zeros(nVT)
        outfile.write(
            '\nNumber of shipments (freight; by vehicle type)' + sep + '\n')
        outfile.write(sep + 'Vehicle type' + sep + 'Number of shipments\n')

        for veh in range(nVT):
            nShipsVeh[veh] = len(shipments[shipments['VEHTYPE'] == veh])
            outfile.write(
                sep + vtNames[veh] +
                sep + str(nShipsVeh[veh]) + '\n')

        # Number of shipments by logistic segment
        nShipsLS = np.zeros(nLS)
        outfile.write('\nNumber of shipments (Total) ')
        outfile.write('(freight/parcels; by logistic segment)' + sep + '\n')
        outfile.write(sep + 'LS' + sep + 'Number of shipments\n')

        for ls in range(nLS - 1):
            nShipsLS[ls] = len(shipments[shipments['LS'] == ls])
            outfile.write(sep + lsNames[ls] + sep + str(nShipsLS[ls]) + '\n')
        outfile.write(sep + lsNames[nLS - 1] + sep + str(len(parcels)) + '\n')

        # Number of shipments by logistic segment
        ZEZshipments = shipments[shipments['DEST'] < 99999900]
        ZEZshipments = ZEZshipments[
            np.array(zonesShape.loc[np.array(ZEZshipments['DEST'], dtype=int), 'ZEZ'] == 1)]
        ZEZparcels = parcels[parcels['DEST'] < 99999900]
        ZEZparcels = ZEZparcels[
            np.array(zonesShape.loc[np.array(ZEZparcels['DEST'], dtype=int), 'ZEZ'] == 1)]
        nShipsLS = np.zeros(nLS)

        outfile.write('\nNumber of shipments (to ZEZ) ')
        outfile.write('(freight/parcels; by logistic segment)' + sep + '\n')
        outfile.write(sep + 'LS' + sep + 'Number of shipments\n')

        for ls in range(nLS - 1):
            nShipsLS[ls] = len(ZEZshipments[ZEZshipments['LS'] == ls])
            outfile.write(sep + lsNames[ls] + sep + str(nShipsLS[ls]) + '\n')
        outfile.write(sep + lsNames[nLS - 1] + sep + str(len(ZEZparcels)) + '\n')
        
        if root != '':
            root.progressBar['value'] = 65.0

        # ------------------------- Number of trips ---------------------------

        print("\tTrips"),
        log_file.write("\tTrips\n")

        # Number of trips by direction
        nTripsTotal = trips.shape[0]
        nTripsLeaving = trips[trips['DEST'] > 99999900].shape[0]
        nTripsEntering = trips[trips['ORIG'] > 99999900].shape[0]
        nTripsIntra = nTripsTotal - nTripsLeaving - nTripsEntering

        outfile.write('\nNumber of trips (freight; by direction)' + sep + '\n')
        outfile.write(sep + 'Direction'             + sep + 'Number of trips'   + '\n')
        outfile.write(sep + 'Inside study area'     + sep + str(nTripsIntra)    + '\n')
        outfile.write(sep + 'Leaving study area'    + sep + str(nTripsLeaving)  + '\n')
        outfile.write(sep + 'Entering study area'   + sep + str(nTripsEntering) + '\n')
        outfile.write(sep + 'Total'                 + sep + str(nTripsTotal)    + '\n')

        # Number of parcel trips by direction
        nParcelTripsTotal = parcelTrips.shape[0]
        nParcelTripsLeaving = parcelTrips[parcelTrips['DEST'] > 99999900].shape[0]
        nParcelTripsEntering = parcelTrips[parcelTrips['ORIG'] > 99999900].shape[0]
        nParcelTripsIntra = (
            nParcelTripsTotal -
            nParcelTripsLeaving -
            nParcelTripsEntering)

        outfile.write('\nNumber of trips (parcel; by direction)' + sep + '\n')
        outfile.write(sep + 'Direction'             + sep + 'Number of trips'         + '\n')
        outfile.write(sep + 'Inside study area'     + sep + str(nParcelTripsIntra)    + '\n')
        outfile.write(sep + 'Leaving study area'    + sep + str(nParcelTripsLeaving)  + '\n')
        outfile.write(sep + 'Entering study area'   + sep + str(nParcelTripsEntering) + '\n')
        outfile.write(sep + 'Total'                 + sep + str(nParcelTripsTotal)    + '\n')

        # Number of trips by logistic segment and NSTR
        outfile.write('\nNumber of trips ')
        outfile.write('(freight/parcel; by logistic segment and NSTR)' + sep + '\n')
        outfile.write(sep + 'LS' + sep)
        for nstr in range(-1, nNSTR):
            outfile.write(str(nstr) + sep)
        outfile.write('\n')

        for ls in range(nLS - 1):
            outfile.write(sep + lsNames[ls])
            for nstr in range(-1, nNSTR):
                value = np.sum(
                    (trips['LS'] == ls) &
                    (trips['NSTR'] == nstr))
                outfile.write(sep + str(value))
            outfile.write('\n')

        # Number of trips by logistic segment and NSTR
        # (in/out/inside ZEZ Rotterdam)
        tripOrigs = np.array(trips['ORIG'])
        tripDests = np.array(trips['DEST'])
        zezZones = np.array(
            zonesShape.loc[
                (zonesShape['ZEZ'] == 1) & (zonesShape['Gemeentena'] == 'Rotterdam'),
                'AREANR'])
        tripsZEZ = trips.iloc[
            [i for i in range(len(trips))
             if tripOrigs[i] in zezZones or tripDests[i] in zezZones], :]

        outfile.write('\nNumber of trips ')
        outfile.write('(freight/parcel; by logistic segment and NSTR)' + sep + '\n')
        outfile.write('Only trips entering/leaving/inside ZEZ Rotterdam' + '\n')

        outfile.write(sep + 'LS' + sep)
        for nstr in range(-1, nNSTR):
            outfile.write(str(nstr) + sep)
        outfile.write('\n')

        for ls in range(nLS - 1):
            outfile.write(sep + lsNames[ls])
            for nstr in range(-1, nNSTR):
                value = np.sum(
                    (tripsZEZ['LS'] == ls) &
                    (tripsZEZ['NSTR'] == nstr))
                outfile.write(sep + str(value))
            outfile.write('\n')
            
        # Number of trips by vehicle type and combustion type
        nTripsVeh = [None for veh in range(nVT)]
        outfile.write('\nNumber of trips ')
        outfile.write('(freight; by vehicle type and combustion type)' + sep + '\n')
        outfile.write(sep + 'Vehicle type')

        for comb in range(nCombType):
            outfile.write(sep + str(dimCombType.at[comb, 'Comment']))
        outfile.write('\n')

        for veh in range(nVT):
            nTripsVeh[veh] = len(trips[trips['VEHTYPE'] == veh])
            nTripsVehComb = [None for comb in range(nCombType)]
            for comb in range(nCombType):
                nTripsVehComb[comb] = np.sum(
                    (trips['VEHTYPE'] == veh) &
                    (trips['COMBTYPE'] == comb))
            outfile.write(sep + vtNames[veh])
            for comb in range(nCombType):
                outfile.write(sep + str(nTripsVehComb[comb]))
            outfile.write('\n')

        # Number of trips by logistic segment and vehicle type
        outfile.write('\nNumber of trips ')
        outfile.write('(freight/parcel; by logistic segment and vehicle type)' + sep + '\n')
        outfile.write(sep + 'LS' + sep)
        for vt in range(nVT):
            outfile.write(vtNames[vt] + sep)
        outfile.write('\n')

        for ls in range(nLS - 1):
            outfile.write(sep + lsNames[ls])
            for vt in range(nVT):
                value = np.sum(
                    (trips['LS'] == ls) &
                    (trips['VEHTYPE'] == vt))
                outfile.write(sep + str(value))
            outfile.write('\n')

        nParcelTripsVan  = np.sum(parcelTrips['VehType'] == 'Van')
        nParcelTripsLEVV = np.sum(parcelTrips['VehType'] == 'LEVV')
        outfile.write(
            sep + lsNames[nLS - 1] +
            sep + '0' + sep + '0' + sep + '0' + sep + '0' +
            sep + '0' + sep + '0' + sep + '0' + sep)
        outfile.write(str(nParcelTripsVan) + sep + str(nParcelTripsLEVV) + '\n')

        # Number of trips by van traffic segment
        outfile.write('\nNumber of trips (service vans; by logistic segment)' + sep + '\n')
        if vanTripsFound:
            outfile.write(
                sep + 'Segment' +
                sep + 'Number of trips\n')
            outfile.write(
                sep + 'Service' +
                sep + str(np.sum(vanTripsService)) + '\n')
            outfile.write(
                sep + 'Construction' +
                sep + str(np.sum(vanTripsConstruction)) + '\n')
        else:
            outfile.write(sep + 'Van trips not found in outputfolder.' + '\n')
            outfile.write('\n\n')

        if root != '':
            root.progressBar['value'] = 75.0

        # ----------------------- Transported weight --------------------------

        print("\tTransported weight")
        log_file.write("\tTransported weight\n")

        # Transport weight by direction
        weightTotal = round(sum(tours['TOUR_WEIGHT']), 2)
        weightLeaving = round(sum(tours[tours['DEST'] > 99999900]['TOUR_WEIGHT']), 2)
        weightEntering = round(sum(tours[tours['ORIG'] > 99999900]['TOUR_WEIGHT']), 2)
        weightIntra = weightTotal - weightLeaving - weightEntering

        outfile.write('\nTransported tonnes (freight; by direction)' + sep + '\n')
        outfile.write(sep + 'Direction'             + sep + 'Tonnes'            + '\n')
        outfile.write(sep + 'Inside study area'     + sep + str(weightIntra)    + '\n')
        outfile.write(sep + 'Leaving study area'    + sep + str(weightLeaving)  + '\n')
        outfile.write(sep + 'Entering study area'   + sep + str(weightEntering) + '\n')
        outfile.write(sep + 'Total'                 + sep + str(weightTotal)    + '\n')

        # Transported weight by NSTR
        weightNSTR = np.zeros(nNSTR)
        outfile.write('\nTransported tonnes (freight; by NSTR goods type)' + sep + '\n')
        outfile.write(sep + 'NSTR' + sep + 'Tonnes\n')

        for nstr in range(nNSTR):
            weightNSTR[nstr] = round(sum(tours[tours['NSTR'] == nstr]['TOUR_WEIGHT']), 2)
            outfile.write(sep + str(nstr) + sep + str(weightNSTR[nstr]) + '\n')

        # Transported weight by Vehicle type
        weightVeh = [None for veh in range(nVT)]
        outfile.write('\nTransported tonnes (freight; by vehicle type)' + sep + '\n')
        outfile.write(sep + 'Vehicle type')
        for comb in range(nCombType):
            outfile.write(sep + str(dimCombType.at[comb, 'Comment']))
        outfile.write('\n')

        for veh in range(nVT):
            weightVeh[veh] = np.round(np.sum(tours[tours['VEHTYPE'] == veh]['TOUR_WEIGHT']),2)
            weightVehComb = [None for comb in range(nCombType)]
            for comb in range(nCombType):
                weightVehComb[comb] = np.round(np.sum(
                    tours[(tours['VEHTYPE'] == veh) & (tours['COMBTYPE'] == comb)]['TOUR_WEIGHT']), 2)
            outfile.write(sep + vtNames[veh])
            for comb in range(nCombType):
                outfile.write(sep + str(weightVehComb[comb]))
            outfile.write('\n')

        # Transported weight by logistic segment
        weightLS = np.zeros(nLS)
        outfile.write('\nTransported tonnes (freight; by logistic segment)' + sep + '\n')
        outfile.write(sep + 'LS' + sep + 'Tonnes\n')
        for ls in range(nLS - 1):
            weightLS[ls] = round(sum(tours[tours['LS'] == ls]['TOUR_WEIGHT']), 2)
            outfile.write(sep + lsNames[ls] + sep + str(weightLS[ls]) + '\n')
        outfile.write(sep + lsNames[nLS - 1] + sep + 'n.a.' + '\n')

        if root != '':
            root.progressBar['value'] = 78.0

        # ------------------------ Loading rate -------------------------------

        print("\tAverage trip loads")
        log_file.write("\tAverage trip loads\n")

        # Average trip load by direction
        loadedTrips = trips[trips['NSTR'] != -1]
        loadedTripsIntra = loadedTrips[
            [(
                loadedTrips['DEST'][i] <= 99999900 and
                loadedTrips['ORIG'][i] <= 99999900)
             for i in loadedTrips.index]]
        avgLoadIntra = round(loadedTripsIntra['TRIP_WEIGHT'].mean(), 2)
        avgLoadLeaving = round(loadedTrips[loadedTrips['DEST'] > 99999900]['TRIP_WEIGHT'].mean(),2)
        avgLoadEntering = round(loadedTrips[loadedTrips['ORIG'] > 99999900]['TRIP_WEIGHT'].mean(),2)
        avgLoad = round(loadedTrips['TRIP_WEIGHT'].mean(), 2)

        outfile.write(f"\nAverage load carried in trip (tonnes) (freight; by direction)*{sep}\n")
        outfile.write(f"{sep}Direction{sep}Average trip load (tonnes)\n")

        outfile.write(f"{sep}Inside study area{sep}{avgLoadIntra}\n")
        outfile.write(f"{sep}Leaving study area{sep}{avgLoadLeaving}\n")
        outfile.write(f"{sep}Entering study area{sep}{avgLoadEntering}\n")
        outfile.write(f"{sep}All loaded trips{sep}{avgLoad}\n")
        outfile.write(f"{sep}*Excluding empty trips{sep}\n")
        
        # Average load per NSTR
        avgLoadNSTR = np.zeros(nNSTR)
        outfile.write(f"\nAverage load carried in trip (tonnes) (freight; by NSTR goods type)*{sep}\n")
        outfile.write(f"{sep}NSTR{sep}Average trip load (tonnes)\n")

        for nstr in range(nNSTR):
            avgLoadNSTR[nstr] = round(loadedTrips[
                loadedTrips['NSTR'] == nstr]['TRIP_WEIGHT'].mean(), 2)
            outfile.write(f"{sep}{nstr}{sep}{avgLoadNSTR[nstr]}\n")
        outfile.write(f"{sep}*Excluding empty trips{sep}\n")
        
        # Average load per vehicle type
        avgLoadVeh = np.zeros(nVT)
        outfile.write(f"\nAverage load carried in trip (tonnes) (freight; by vehicle type)*{sep}\n")
        outfile.write(f"{sep}Vehicle type{sep}Average trip load (tonnes)\n")
        for veh in range(nVT):
            avgLoadVeh[veh] = round(loadedTrips[
                loadedTrips['VEHTYPE'] == veh]['TRIP_WEIGHT'].mean(),2)
            outfile.write(f"{sep}{vtNames[veh]}{sep}{avgLoadVeh[veh]}\n")

        outfile.write(f"{sep}*Excluding empty trips{sep}\n")

        # Average load per logistic segment
        avgLoadLS = np.zeros(nLS)
        outfile.write(f"\nAverage load carried in trip (tonnes) (freight; by logistic segment)*{sep}\n")
        outfile.write(f"{sep}LS{sep}Average trip load (tonnes)\n")

        for ls in range(nLS - 1):
            avgLoadLS[ls] = round(loadedTrips[
                loadedTrips['LS'] == ls]['TRIP_WEIGHT'].mean(), 2)
            outfile.write(sep + lsNames[ls] + sep + str(avgLoadLS[ls]) + '\n')
        outfile.write(sep + lsNames[nLS - 1] + sep + 'n.a.' + '\n')

        outfile.write(f"{sep}*Excluding empty trips{sep}\n")
        
        if root != '':
            root.progressBar['value'] = 80.0 

        # --------------- Number of shipments per tour ------------------------

        print("\tNumber of shipments")
        log_file.write("\tNumber of shipments\n")

        nShipsTotal = pd.value_counts(tours['N_SHIP'], sort=False)
        nShipsNSTR = pd.crosstab(tours['N_SHIP'], tours['NSTR'])
        nShipsLS = pd.crosstab(tours['N_SHIP'], tours['LS'])

        toursInternal = tours[
            [tours['ORIG'][i] <= 99999900 and tours['DEST'][i] <= 99999900
             for i in tours.index]]
        nShipsTotalInternal = pd.value_counts(
            toursInternal['N_SHIP'],
            sort=False)
        nShipsNSTRInternal = pd.crosstab(
            toursInternal['N_SHIP'],
            toursInternal['NSTR'])
        nShipsLSInternal = pd.crosstab(
            toursInternal['N_SHIP'],
            toursInternal['LS'])
        
        outfile.write("\nNumber of shipments per tour (freight; by NSTR)\n")
        outfile.write(f"{sep}{sep}NSTR\n")
        outfile.write(f"{sep}Number of shipments{sep}{str(list(nShipsNSTR.columns))[1:-1]}{sep}Total\n")

        for ships in nShipsNSTR.index:
            totalShips = sum(nShipsNSTR.loc[ships,:])
            outfile.write(f"{sep}{ships}{sep}{str(list(nShipsNSTR.loc[ships, :]))[1:-1]}{sep}{totalShips}\n")
        
        outfile.write("\nNumber of shipments per tour within study area (freight; by NSTR)\n")
        outfile.write(f"{sep}{sep}NSTR\n")
        outfile.write(f"{sep}Number of shipments{sep}{str(list(nShipsNSTRInternal.columns))[1:-1]}{sep}Total\n")

        for ships in nShipsNSTR.index:
            totalShips = sum(nShipsNSTRInternal.loc[ships,:])
            outfile.write(f"{sep}{ships}{sep}{str(list(nShipsNSTRInternal.loc[ships, :]))[1:-1]}{sep}{totalShips}\n")

        outfile.write("\nNumber of shipments per tour (freight; by logistic segment)\n")
        outfile.write(f"{sep}{sep}Logistic segment\n")
        outfile.write(f"{sep}Number of shipments{sep}{str(list(nShipsLS.columns))[1:-1]}{sep}Total\n")

        for ships in nShipsLS.index:
            totalShips = sum(nShipsLS.loc[ships,:])
            outfile.write(f"{sep}{ships}{sep}{str(list(nShipsLS.loc[ships, :]))[1:-1]}{sep}{totalShips}\n")
        
        outfile.write("\nNumber of shipments per tour within study area (freight; by logistic segment)\n")
        outfile.write(f"{sep}{sep}Logistic segment\n")
        outfile.write(f"{sep}Number of shipments{sep}{str(list(nShipsLSInternal.columns))[1:-1]}{sep}Total\n")

        for ships in nShipsLS.index:
            totalShips = sum(nShipsLSInternal.loc[ships,:])
            outfile.write(f"{sep}{ships}{sep}{str(list(nShipsLSInternal.loc[ships, :]))[1:-1]}{sep}{totalShips}\n")   

        outfile.write("\nAverage number of trips per tour (freight/parcel; by logistic segment)\n")
        outfile.write('LS' + sep + 'Number of trips\n')

        for ls in range(nLS - 1):
            nToursLS = len(np.unique(trips.loc[trips['LS'] == ls,'TOUR_ID']))
            if nToursLS > 0:
                outfile.write(
                    lsNames[ls] + sep +
                    str(len(trips[trips['LS'] == ls]) / nToursLS) + '\n')
            else:
                outfile.write(lsNames[ls] + sep + 'n.a.' + '\n')
        outfile.write(
            lsNames[nLS - 1] + sep +
            str(np.mean(parcelTours['N_trips_tour'])) + '\n')
        outfile.write(
            'Total (freight)' + sep
            + str(len(trips) / len(np.unique(trips['TOUR_ID']))) + '\n')
        
        if root != '':
            root.progressBar['value'] = 82.0

        # ------------------- Tonkilometers -----------------------------------

        # Trips tonkilometers
        trips['TONKM'] = trips['DIST'] * trips['TRIP_WEIGHT']
        tonKilometersTotal = round(sum(trips['TONKM']), 2)
        tonKilometersLeaving = round(sum(trips[trips['DEST'] > 99999900]['TONKM']), 2)
        tonKilometersEntering = round(sum(trips[trips['ORIG'] > 99999900]['TONKM']), 2)
        tonKilometersIntra = tonKilometersTotal - tonKilometersLeaving - tonKilometersEntering

        outfile.write('\nTonkilometers trips (freight; by direction)' + sep + '\n')
        outfile.write(sep + 'Direction'             + sep + 'TonKM'   + '\n')
        outfile.write(sep + 'Inside study area'     + sep + str(tonKilometersIntra)    + '\n')
        outfile.write(sep + 'Leaving study area'    + sep + str(tonKilometersLeaving)  + '\n')
        outfile.write(sep + 'Entering study area'   + sep + str(tonKilometersEntering) + '\n')
        outfile.write(sep + 'Total'                 + sep + str(tonKilometersTotal)    + '\n')
       
        # Shipments tonkilometers
        shipments['TONKM'] = shipments['DIST'] * shipments['WEIGHT']
        tonKilometersTotal = round(sum(shipments['TONKM']), 2)
        tonKilometersLeaving = round(sum(shipments[shipments['DEST'] > 99999900]['TONKM']), 2)
        tonKilometersEntering = round(sum(shipments[shipments['ORIG'] > 99999900]['TONKM']), 2)
        tonKilometersIntra  = tonKilometersTotal -  tonKilometersLeaving -  tonKilometersEntering

        outfile.write('\nTonkilometers shipments (freight; by direction)' + sep + '\n')
        outfile.write(sep + 'Direction'             + sep + 'TonKM'   + '\n')
        outfile.write(sep + 'Inside study area'     + sep + str(tonKilometersIntra)    + '\n')
        outfile.write(sep + 'Leaving study area'    + sep + str(tonKilometersLeaving)  + '\n')
        outfile.write(sep + 'Entering study area'   + sep + str(tonKilometersEntering) + '\n')
        outfile.write(sep + 'Total'                 + sep + str(tonKilometersTotal)    + '\n')
        
        if root != '':
            root.progressBar['value'] = 85.0 

        # --------------- Vehicle Kilometers Travelled (Total) ------------------------
        
        print("\tVehicle Kilometers Travelled")
        log_file.write("\tVehicle Kilometers Travelled\n")

        # VKM (Total, skim-based) by logistic segment and vehicle type
        outfile.write('\nVehicle kilometers (Total; based on skim)')
        outfile.write('(freight/parcel; by logistic segment and vehicle type)' + sep + '\n')
        outfile.write(sep + 'LS' + sep)
        for vt in range(nVT):
            outfile.write(vtNames[vt] + sep)
        outfile.write('\n')

        for ls in range(nLS - 1):
            outfile.write(sep + lsNames[ls])
            for vt in range(nVT):
                value = np.sum(trips.loc[
                    (trips['LS']==ls) &
                    (trips['VEHTYPE']==vt), 'DIST'])
                outfile.write(sep + str(value))
            outfile.write('\n')
        nParcelTripsVan  = np.sum(parcelTrips.loc[parcelTrips['VehType'] == 'Van', 'DIST'])
        nParcelTripsLEVV = np.sum(parcelTrips.loc[parcelTrips['VehType'] == 'LEVV','DIST'])
        outfile.write(
            sep + lsNames[nLS - 1] +
            sep + '0' + sep + '0' + sep + '0' + sep +'0' +
            sep + '0' + sep + '0' + sep + '0' + sep)
        outfile.write(str(nParcelTripsVan) + sep + str(nParcelTripsLEVV) + '\n')

        # VKMs van (Total, skim-based) by van traffic segment
        outfile.write('\nVehicle kilometers (Total; based on skim)')
        outfile.write('(service vans; by logistic segment)' + sep + '\n')
        if vanTripsFound:
            outfile.write(sep + 'Segment' + sep + 'Number of trips\n')
            outfile.write(sep + 'Service'      + sep + str(np.sum(vanTripsService      * skimDistance / 1000)) + '\n')
            outfile.write(sep + 'Construction' + sep + str(np.sum(vanTripsConstruction * skimDistance / 1000)) + '\n')
        else:
            outfile.write(sep + 'Van trips not found in outputfolder.' + '\n')
            
        # VKMs (Total) by logistic segment
        VKT_LS = np.zeros(nLS)
        outfile.write("\nVehicle Kilometers Travelled (Total) (freight/parcel; by logistic segment)\n")
        outfile.write(f"{sep}LS{sep}VKT\n")
        for ls in range(nLS):
            temp = linksLoaded['LENGTH'] * linksLoaded[f'N_LS{ls}']
            VKT_LS[ls] = np.round(np.sum(temp), 2)
            outfile.write(f"{sep}{lsNames[ls]}{sep}{VKT_LS[ls]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_LS)}\n")
        
        # VKMs (Total) by vehicle type
        VKT_VEH = np.zeros(nVT)
        outfile.write("\nVehicle Kilometers Travelled (Total) (freight/parcel; by vehicle Type)\n")
        outfile.write(f"{sep}Vehicle type{sep}VKT\n")
        for veh in vtNums:
            i = veh
            temp = linksLoaded['LENGTH'] * linksLoaded[f'N_VEH{i}']
            VKT_VEH[i] = np.round(np.sum(temp), 2)
            outfile.write(f"{sep}{vtNames[i]}{sep}{VKT_VEH[i]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_VEH)}\n")       
        
        # VKMs van (Total=NL) by van traffic segment
        outfile.write("\nVehicle Kilometers Travelled (NL) (service vans; by segment)\n")
        outfile.write(f"{sep}Segment{sep}VKT\n")
        outfile.write(sep + 'Service'      + sep + str(np.sum(linksLoaded['LENGTH'] * linksLoaded['N_VAN_S'])) + '\n')
        outfile.write(sep + 'Construction' + sep + str(np.sum(linksLoaded['LENGTH'] * linksLoaded['N_VAN_C'])) + '\n')
            
        if root != '':
            root.progressBar['value'] = 90.0 

        # --------------- Vehicle Kilometers Travelled (Zuid-Holland) ------------------------

        # VKMs (ZH) by logistic segment
        VKT_LS = np.zeros((nLS))
        outfile.write("\nVehicle Kilometers Travelled (in Zuid-Holland) (freight/parcel; by logistic segment)\n")
        outfile.write(f"{sep}LS{sep}VKT\n")
        for ls in range(nLS):
            temp = linksLoadedZH['LENGTH'] * linksLoadedZH[f'N_LS{ls}']
            VKT_LS[ls] = np.round(np.sum(temp), 2)
            outfile.write(f"{sep}{lsNames[ls]}{sep}{VKT_LS[ls]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_LS)}\n")

        # VKMs (ZH) by vehicle type
        VKT_VEH = np.zeros(nVT)
        outfile.write("\nVehicle Kilometers Travelled (in Zuid-Holland) (freight/parcel; by vehicle Type)\n")
        outfile.write(f"{sep}Vehicle type{sep}VKT\n")
        for veh in vtNums:
            i = veh
            temp = linksLoadedZH['LENGTH'] * linksLoadedZH[f'N_VEH{i}']
            VKT_VEH[i] = np.round(np.sum(temp), 2)
            outfile.write(f"{sep}{vtNames[i]}{sep}{VKT_VEH[i]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_VEH)}\n")    

        # VKMs parcel (ZH) by vehicle type
        VKT_VEH = np.zeros(nVT)
        outfile.write("\nVehicle Kilometers Travelled (in Zuid-Holland) (parcel; by vehicle Type)\n")
        outfile.write(f"{sep}Vehicle type{sep}VKT\n")
        for veh in vtNums:
            i = veh
            if f'N_LS8_VEH{i}' in linksLoaded.columns:
                temp = linksLoadedZH['LENGTH'] * linksLoadedZH[f'N_LS8_VEH{i}']
                VKT_VEH[i] = np.round(np.sum(temp), 2)
                outfile.write(f"{sep}{vtNames[i]}{sep}{VKT_VEH[i]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_VEH)}\n")    

        # VKMs van (ZH) by van traffic segment
        outfile.write("\nVehicle Kilometers Travelled (in Zuid-Holland) (service vans; by segment)\n")
        outfile.write(f"{sep}Segment{sep}VKT\n")
        outfile.write(sep + 'Service'      + sep + str(np.sum(linksLoadedZH['LENGTH'] * linksLoadedZH['N_VAN_S'])) + '\n')
        outfile.write(sep + 'Construction' + sep + str(np.sum(linksLoadedZH['LENGTH'] * linksLoadedZH['N_VAN_C'])) + '\n')
         
        if root != '':
            root.progressBar['value'] = 93.0

        # --------------- Vehicle Kilometers Travelled (Rotterdam) ------------------------

        # VKMs (Rdam) by logistic segment
        VKT_LS = np.zeros((nLS))
        outfile.write("\nVehicle Kilometers Travelled (in Rotterdam) (freight/parcel; by logistic segment)\n")
        outfile.write(f"{sep}LS{sep}VKT\n")
        for ls in range(nLS):
            temp = linksLoadedRdam['LENGTH'] * linksLoadedRdam[f'N_LS{ls}']
            VKT_LS[ls] = np.round(np.sum(temp), 2)
            outfile.write(f"{sep}{lsNames[ls]}{sep}{VKT_LS[ls]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_LS)}\n")
        
        # VKMs (Rdam) by vehicle type
        VKT_VEH = np.zeros((nVT))
        outfile.write("\nVehicle Kilometers Travelled (in Rotterdam) (freight/parcel; by vehicle Type)\n")
        outfile.write(f"{sep}Vehicle type{sep}VKT\n")
        for veh in vtNums:
            temp = linksLoadedRdam['LENGTH'] * linksLoadedRdam[f'N_VEH{veh}']
            VKT_VEH[veh] = np.round(np.sum(temp), 2)
            outfile.write(f"{sep}{vtNames[veh]}{sep}{VKT_VEH[veh]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_VEH)}\n")               

        # VKMs parcel (Rdam) by vehicle type
        VKT_VEH = np.zeros(nVT)
        outfile.write("\nVehicle Kilometers Travelled (in Rotterdam) (parcel; by vehicle Type)\n")
        outfile.write(f"{sep}Vehicle type{sep}VKT\n")
        for veh in vtNums:
            if f'N_LS8_VEH{veh}' in linksLoaded.columns:
                temp = linksLoadedRdam['LENGTH'] * linksLoadedRdam[f'N_LS8_VEH{veh}']
                VKT_VEH[veh] = np.round(np.sum(temp),2)
                outfile.write(f"{sep}{vtNames[veh]}{sep}{VKT_VEH[veh]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_VEH)}\n") 

        # VKMs van (Rdam) by van traffic segment
        outfile.write("\nVehicle Kilometers Travelled (in Rotterdam) (service vans; by segment)\n")
        outfile.write(f"{sep}Segment{sep}VKT\n")
        outfile.write(
            sep + 'Service' +
            sep + str(np.sum(
                linksLoadedRdam['LENGTH'] * linksLoadedRdam['N_VAN_S'])) +
            '\n')
        outfile.write(
            sep + 'Construction' +
            sep + str(np.sum(
                linksLoadedRdam['LENGTH'] * linksLoadedRdam['N_VAN_C'])) +
            '\n')

        if root != '':
            root.progressBar['value'] = 95.0

        # --------------- Vehicle Kilometers Travelled (ZEZ) ------------------------

        # VKMs (ZEZ) by logistic segment
        VKT_LS = np.zeros((nLS))
        outfile.write("\nVehicle Kilometers Travelled (in ZEZ) (freight/parcel; by logistic segment)\n")
        outfile.write(f"{sep}LS{sep}VKT\n")
        for ls in range(nLS):
            temp = linksLoadedZEZ['LENGTH'] * linksLoadedZEZ[f'N_LS{ls}']
            VKT_LS[ls] = np.round(np.sum(temp), 2)
            outfile.write(f"{sep}{lsNames[ls]}{sep}{VKT_LS[ls]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_LS)}\n")

        # VKMs (ZEZ) by vehicle type
        VKT_VEH = np.zeros((nVT))
        outfile.write("\nVehicle Kilometers Travelled (in ZEZ) (freight/parcel; by vehicle Type)\n")
        outfile.write(f"{sep}Vehicle type{sep}VKT\n")
        for veh in vtNums:
            temp = linksLoadedZEZ['LENGTH'] * linksLoadedZEZ[f'N_VEH{veh}']
            VKT_VEH[veh] = np.round(np.sum(temp), 2)
            outfile.write(f"{sep}{vtNames[veh]}{sep}{VKT_VEH[veh]}\n")
        outfile.write(f"{sep}Total{sep}{sum(VKT_VEH)}\n")            

        if root != '':
            root.progressBar['value'] = 97.0

        # ----------------------- Emissions -----------------------------------

        print('\tEmissions')
        log_file.write("\tEmissions\n")

        outfile.write('\nEmissions from network (freight/parcel/vans; Total)\n')
        outfile.write('Type' + sep + 'kg\n')
        for emission in etNames:
            total = np.sum(linksLoaded[emission])
            outfile.write(emission + sep + str(total) + '\n')

        outfile.write('\nEmissions from network (freight/parcel/vans; in Zuid-Holland)\n')
        outfile.write('Type' + sep + 'kg\n')
        for emission in etNames:
            total = np.sum(linksLoadedZH[emission])
            outfile.write(emission + sep + str(total) + '\n')

        outfile.write('\nEmissions from network (freight/parcel/vans; in Rotterdam)\n')
        outfile.write('Type' + sep + 'kg\n')
        for emission in etNames:
            total = np.sum(linksLoadedRdam[emission])
            outfile.write(emission + sep + str(total) + '\n')

        outfile.write('\nEmissions from network (freight/parcel/vans; in The Hague)\n')
        outfile.write('Type' + sep + 'kg\n')
        for emission in etNames:
            total = np.sum(linksLoadedDH[emission])
            outfile.write(emission + sep + str(total) + '\n')

        outfile.write('\nEmissions from network (freight/parcel/vans; in ZEZ)\n')
        outfile.write('Type' + sep + 'kg\n')
        for emission in etNames:
            total = np.sum(linksLoadedZEZ[emission])
            outfile.write(emission + sep + str(total) + '\n')

        outfile.write('\nEmissions from network (Total) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in etNames:
                total = np.sum(linksLoaded[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')                     
        for ls in ['VAN_S','VAN_C']:
            for emission in etNames:
                total = np.sum(linksLoaded[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')   

        if root != '':
            root.progressBar['value'] = 98.0

        outfile.write('\nEmissions from network (in Zuid-Holland) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in etNames:
                total = np.sum(linksLoadedZH[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')   
        for ls in ['VAN_S','VAN_C']:
            for emission in etNames:
                total = np.sum(linksLoadedZH[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')  

        outfile.write('\nEmissions from network (in Rotterdam) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in etNames:
                total = np.sum(linksLoadedRdam[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')   
        for ls in ['VAN_S','VAN_C']:
            for emission in etNames:
                total = np.sum(linksLoadedRdam[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')  

        outfile.write('\nEmissions from network (in The Hague) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in etNames:
                total = np.sum(linksLoadedDH[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')   
        for ls in ['VAN_S','VAN_C']:
            for emission in etNames:
                total = np.sum(linksLoadedDH[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')  

        outfile.write('\nEmissions from network (in ZEZ) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in etNames:
                total = np.sum(linksLoadedZEZ[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')   
        for ls in ['VAN_S','VAN_C']:
            for emission in etNames:
                total = np.sum(linksLoadedZEZ[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')  

        outfile.write('\nEmissions from network (freight/parcel/vans; by municipality)\n')
        outfile.write('Municipality' + sep + 'Type' + sep + 'kg (all)' + sep + 'kg (parcel)' + '\n')
        for gem in dimMunicipality['Comment'].values:
            currentLinks = linksLoaded[linksLoaded['Gemeentena'] == str(gem)]
            for emission in etNames:
                total = np.sum(currentLinks[emission])
                totalParcel = np.sum(currentLinks[emission + '_LS8'])
                outfile.write(str(gem) + sep + emission + sep + str(total) + sep + str(totalParcel) + '\n')                   

        if root != '':
            root.progressBar['value'] = 99.0

        outfile.write('\nCO2 Emissions from network (in Zuid-Holland) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in ['CO2']:
                total = np.sum(linksLoadedZH[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')   
        for ls in ['VAN_S','VAN_C']:
            for emission in ['CO2']:
                total = np.sum(linksLoadedZH[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')  

        outfile.write('\nCO2 Emissions from network (in Rotterdam) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in ['CO2']:
                total = np.sum(linksLoadedRdam[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')   
        for ls in ['VAN_S','VAN_C']:
            for emission in ['CO2']:
                total = np.sum(linksLoadedRdam[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')  

        outfile.write('\nCO2 Emissions from network (in The Hague) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in ['CO2']:
                total = np.sum(linksLoadedDH[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')   
        for ls in ['VAN_S','VAN_C']:
            for emission in ['CO2']:
                total = np.sum(linksLoadedDH[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')  

        outfile.write('\nCO2 Emissions from network (in ZEZ) (freight/parcel/vans; by logistic segment)\n')
        outfile.write('Logistic segment' + sep + 'Type' + sep + 'kg\n')        
        for ls in range(nLS):
            for emission in ['CO2']:
                total = np.sum(linksLoadedZEZ[emission + '_LS' + str(ls)])
                outfile.write(lsNames[ls] + sep + emission + sep + str(total) + '\n')   
        for ls in ['VAN_S','VAN_C']:
            for emission in ['CO2']:
                total = np.sum(linksLoadedZEZ[emission + '_' + str(ls)])
                outfile.write(ls + sep + emission + sep + str(total) + '\n')  

        outfile.write('\nCO2 Emissions from network (freight/parcel/vans; by municipality)\n')
        outfile.write('Municipality' + sep + 'Type' + sep + 'kg (all)' + sep + 'kg (parcel)' + '\n')
        for gem in dimMunicipality['Comment'].values:
            currentLinks = linksLoaded[linksLoaded['Gemeentena'] == str(gem)]

            for emission in ['CO2']:
                total = np.sum(currentLinks[emission])
                totalParcel = np.sum(currentLinks[emission + '_LS8'])
                outfile.write(str(gem) + sep + emission + sep + str(total) + sep + str(totalParcel) + '\n')     
  
        print(f"Tables written to {datapathOI}Output_Outputindicator_{label}.csv")
        log_file.write(f"Tables written to {datapathOI}Output_Outputindicator_{label}.csv\n")

        if root != '':
            root.progressBar['value'] = 100.0

        # ----------------------- End of script -------------------------------

        totaltime = round(time.time() - start_time, 2)
        print('Finished. Run time: ' + str(totaltime) + ' seconds')
        log_file.write("Total runtime: %s seconds\n" % (totaltime))  
        log_file.write(
            "End simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")
        log_file.close()    

        if root != '':
            root.update_statusbar("Output Indicators: Done")
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
                root.update_statusbar("Output Indicators: Execution failed!")
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
 
    
    
#%% For if you want to run the module from this script itself (instead of calling it from the GUI module)
        
if __name__ == '__main__':
    varDict = {}

    varDict['INPUTFOLDER']	 = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/data/2016/'
    varDict['OUTPUTFOLDER'] = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/output/tmpREF2016/'
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
    # labels = [ 'MIC_individual_EB', 'MIC_individual_AR', 'MIC_individual_ET', 'MIC_individual_EQ', 'MIC_individual_EM', 
    #               'MIC_individual_EDV', 'MIC_individual_LEV', 
    #               'MIC_collab_EB', 'MIC_collab_AR', 'MIC_collab_ET', 'MIC_collab_EQ', 'MIC_collab_EM',
    #               'MIC_collab_EDV', 'MIC_collab_LEV']

    # Run the module
    root = ''
    main(varDict)


    
    
    
    
    
    