# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 14:20:50 2020

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
        self.root.title("Progress Parcel Demand")
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


#%%

def actually_run_module(args):

    try:
        # -------------------- Define datapaths -------------------------------

        start_time = time.time()

        root = args[0]
        varDict = args[1]

        log_file = open(varDict['OUTPUTFOLDER'] + "Logfile_ParcelDemand.log", "w")
        log_file.write(
            "Start simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")

        if root != '':
            root.update_statusbar("Parcel Demand: Calculating...")
            root.progressBar['value'] = 0.1

        # ------------------------- Import data -------------------------------

        print('Importing data...')
        log_file.write('Importing data...\n')

        zones = read_shape(varDict['ZONES'])
        zones = pd.DataFrame(zones).sort_values('AREANR')
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
        zoneDict = dict(np.transpose(np.vstack((
            np.arange(1, nIntZones + 1),
            zones['AREANR']))))
        zoneDict = {int(a): int(b) for a, b in zoneDict.items()}
        for i in range(nSupZones):
            zoneDict[nIntZones + i + 1] = 99999900 + i + 1
        invZoneDict = dict((v, k) for k, v in zoneDict.items())

        segs = pd.read_csv(varDict['SEGS'])
        segs.index = segs['zone']

        parcelNodes, coords = read_shape(
            varDict['PARCELNODES'],
            returnGeometry=True)
        parcelNodes['X'] = [
            coords[i]['coordinates'][0]
            for i in range(len(coords))]
        parcelNodes['Y'] = [
            coords[i]['coordinates'][1]
            for i in range(len(coords))]
        parcelNodes.index= parcelNodes['id'].astype(int)
        parcelNodes = parcelNodes.sort_index()
        nParcelNodes = len(parcelNodes)

        cepShares = pd.read_csv(varDict['CEP_SHARES'], index_col=0)
        cepList = np.unique(parcelNodes['CEP'])
        cepNodes = [
            np.where(parcelNodes['CEP'] == str(cep))[0]
            for cep in cepList]
        cepNodeDict = {}
        for cepNo in range(len(cepList)):
            cepNodeDict[cepList[cepNo]] = cepNodes[cepNo]

        if root != '':
            root.progressBar['value'] = 1.0

        # ------------- Get skim data and make parcel skim for REF ------------
        skimTravTime = read_mtx(varDict['SKIMTIME'])      # Time in seconds
        skimDistance = read_mtx(varDict['SKIMDISTANCE'])  # Distance in metres
        nZones = int(len(skimTravTime)**0.5)
        parcelSkim = np.zeros((nZones, nParcelNodes))

        # Skim with travel times between parcel nodes and all other zones
        i = 0
        for parcelNodeZone in parcelNodes['AREANR']:
            orig = invZoneDict[parcelNodeZone]
            dest = 1 + np.arange(nZones)

            # Time in hours
            parcelSkim[:, i] = np.round(
                (skimTravTime[(orig - 1) * nZones + (dest - 1)] / 3600), 4)

            i += 1

        if root != '':
            root.progressBar['value'] = 2.0

        # ---------- Import and prepare data for microhub scenario ------------
        if varDict['LABEL'][0:3] == 'MIC':

            mode = varDict['LABEL'][-3:]

            # In case the mode label consists of 2 characters
            mode = mode.replace("_", "")

            # Check if vehicle tag is valid
            if 'collab' in varDict['LABEL']:
                tier = 'Horizontal Collaboration'
            elif 'indiv' in varDict['LABEL']:
                tier = 'Individual CEP'
            else:
                raise Exception(
                    'Invalid scenario input: ' +
                    'consolidation type in LABEL '
                    "'" + varDict['LABEL'] + '".')

            # Read information about vehicle types and scenario configuration
            vehicleTypes = pd.read_csv(varDict['VEHICLETYPES'], index_col=2)
            modeLabelsDict = dict(zip(
                vehicleTypes.index,
                vehicleTypes['Name']))
            modeNumbersDict = dict(zip(
                vehicleTypes.index,
                vehicleTypes['Veh_ID']))

            if mode not in vehicleTypes.index:
                raise Exception(
                    'Invalid scenario input: ' +
                    'vehicle type in LABEL '
                    "'" + varDict['LABEL'] + '"' +
                    ' not found in VEHICLETYPES.')

            else:

                print('Running microhubs scenario with',
                      f'{tier} and {modeLabelsDict[mode]}.')

                # Read csv with microhubs (ID, areanr, CEP)
                microhubs = pd.read_csv(varDict['MICROHUBS'], index_col=0)

                # Find and add coordinates of microhub zones
                microhubs['X'] = [
                    zones.iloc[i]['X'].copy()
                    for i in microhubs['AREANR']]
                microhubs['Y'] = [
                    zones.iloc[i]['Y'].copy()
                    for i in microhubs['AREANR']]

                mh_id_dict = dict(zip(
                    microhubs.index,
                    microhubs['AREANR']))

                # Make skim with travel DISTANCES between
                # parcel nodes and all other zones
                skimTravDist = read_mtx(varDict['SKIMDISTANCE'])
                nZones = int(len(skimTravDist) ** 0.5)
                distSkim = np.zeros((nZones, nParcelNodes))
                i = 0
                for parcelNodeZone in parcelNodes['AREANR']:
                    orig = invZoneDict[parcelNodeZone]
                    dest = 1 + np.arange(nZones)
                    distSkim[:, i] = np.round(
                        skimTravDist[(orig - 1) * nZones + (dest - 1)], 4)
                    i += 1

                if tier == 'Horizontal Collaboration':

                    # Get selected hubs for mode and tier from input data
                    hubsConfig = [
                        int(x) for x in
                        vehicleTypes['collab_microhubs'][mode].split(",")]
                    nMH = len(hubsConfig)
                    hubZones = microhubs['AREANR'][hubsConfig]

                    # Make skim for selected MHs and all zones with chosen mode
                    mh_to_zone_skim = np.zeros((nZones, nMH))
                    i = 0
                    for mh_zone in hubZones:
                        mh_orig = invZoneDict[mh_zone]
                        mh_dest = np.arange(1, nZones + 1)

                        # Time skim in seconds
                        mh_to_zone_skim[:, i] = np.round(
                            (skimTravDist[(mh_orig - 1) * nZones + (mh_dest - 1)] /
                             vehicleTypes['AvgSpeed'][mode] / 3.6), 4)

                        i += 1

                    # For each zone, find the closest microhub
                    # based on travel time in mh_to_zone_skim
                    closest_MH = pd.DataFrame(columns=["MH_ID", "MH_AREA"])
                    closest_MH["MH_ID"] = pd.DataFrame(
                        mh_to_zone_skim).idxmin(axis=1) + 1
                    closest_MH["MH_AREA"] = [
                        mh_id_dict[closest_MH["MH_ID"][i]]
                        for i in closest_MH.index]

                    # Add column to main zones df:
                    # for zones served from microhub, fill in areanr
                    # of their closest hub
                    for i in zones.index:
                        if zones.at[i, "ZEZ"] == 2:
                            zones.at[i, "MH_zone"] = (
                                closest_MH.loc[invZoneDict[i], "MH_AREA"])
                        else:
                            zones.at[zones['ZEZ'] != 2, "MH_zone"] = 0

                # Individual CEP
                else:

                    # Get the hubs that are part of the scenario
                    hubsConfig = list(map(int, vehicleTypes['individual_microhubs'][mode].split(",")))
                    hubsIndex = [x - 1 for x in hubsConfig]
                    microhubsConfig = microhubs.iloc[hubsIndex]
                    cep_hubs = [
                        microhubsConfig.index[microhubsConfig['CEP'] == cep].tolist()
                        for cep in microhubsConfig.CEP.unique()]
                    selectedHubsByCEP = {k: v for k, v in zip(microhubsConfig['CEP'].unique(), cep_hubs)}

                    for courier in cepList:

                        # Number of MH of current cep
                        nMH = len(selectedHubsByCEP[courier])
                        print("Preparing microhub(s) no.",
                              str(selectedHubsByCEP[courier])[1:-1],
                              f"for {courier}")

                        # If only one hub of courier is selected,
                        # that's the one from which the courier will deliver
                        if nMH == 1:
                            current_mh_zone = mh_id_dict[
                                selectedHubsByCEP[courier][0]]
                            zones[f"MH_zone_{courier}"] = 0
                            zones.loc[
                                zones['ZEZ'] == 2,
                                f"MH_zone_{courier}"] = current_mh_zone

                        # If 2+ hubs of the same courier are in the selection,
                        # determine which one serves which area
                        if nMH > 1:
                            # Make skim for selected MHs and all zones
                            mh_to_zone_skim = np.zeros((nZones, nMH))
                            i = 0
                            for mh in selectedHubsByCEP[courier]:
                                mh_orig = invZoneDict[mh_id_dict[mh]]
                                mh_dest = np.arange(1, nZones + 1)

                                # Time skim in seconds
                                mh_to_zone_skim[:, i] = np.round(
                                    (skimTravDist[(mh_orig - 1) * nZones + (mh_dest - 1)] /
                                     (vehicleTypes['AvgSpeed'][mode] / 3.6)), 4)

                                i += 1

                            # For each zone, find the closest microhub based
                            # on travel time in mh_to_zone_skim
                            closest_MH = pd.DataFrame(columns=["MH_ID", "MH_AREA"])

                            # Find for each zone the closest MH with MH_ID
                            closest_MH_pos = pd.DataFrame
                            (mh_to_zone_skim).idxmin(axis=1) + 1
                            closest_MH["MH_ID"] = [
                                selectedHubsByCEP[courier][closest_MH_pos[x] - 1]
                                for x in closest_MH_pos.index]
                            closest_MH["MH_AREA"] = [
                                mh_id_dict[closest_MH["MH_ID"][i]]
                                for i in closest_MH.index]

                            # Add column to main zones df:
                            # for zones served from microhub,
                            # fill in areanr of their closest hub
                            zones[f"MH_zone_{courier}"] = 0
                            zones.loc[zones['ZEZ'] == 2, f"MH_zone_{courier}"] = [
                                closest_MH.loc[invZoneDict[i], "MH_AREA"]
                                for i in zones.index[zones['ZEZ'] == 2]]

        if root != '':
            root.progressBar['value'] = 3.0

        # ------------------ Start parcel generation --------------------------
        # Generate parcels for each zone based on households and employment
        # and select a parcel node for each parcel

        print('Generating parcels...')
        log_file.write('Generating parcels...\n')

        print('\tB2B parcels...')
        log_file.write('\tB2B parcels...\n')

        # Calculate number of parcels per zone
        # based on number of households and
        # total number of parcels on an average day
        zones['parcels'] = (
            segs['9: arbeidspl_totaal'] *
            varDict['PARCELS_PER_EMPL'] / varDict['PARCELS_SUCCESS_B2B'])

        # ------- Calculate parcels per zone with parcel demand model ---------
        print('\tB2C parcels...')
        log_file.write('\tB2C parcels...\n')

        """
        1) make df with all zone/age/income combinations
        2) distribute zonal population over combinations
        3) add up 3 params (sted, inc, age) for each combination
        4) calculate cumprobs and then probs
        5) multiply each prob with corresponding no of parcels and ppl in the row
        6) aggregate to zone level divide by 60 to get daily no of parcels
        """

        demandParams = pd.read_csv(varDict['PARAMS_ECOMMERCE'], sep=',')

        # ---------------------------------------------------------------------
        # 1) make df with all zone/age/income combinations

        print('\t\tEnumerate all zone/age/income combinations...')
        log_file.write('\t\tEnumerate all zone/age/income combinations...\n')

        zoneList = list(zones['AREANR'])

        # Update to grab values from SEGs once they are ready
        ageList = [2, 3, 4, 5, 6, 7, 8, 9, 10]

        # Update to grab values from SEGs once they are ready
        incList = [1, 2, 3, 4, 5, 6]

        demandIndex = pd.MultiIndex.from_product(
            [zoneList, ageList, incList],
            names=['zone', 'agegr', 'incgr'])

        demandDF = pd.DataFrame(
            data=np.zeros(len(demandIndex)),
            index=demandIndex)
        demandDF = demandDF.rename(columns={0: 'pers', 1: 'sted'})
        demandDF['sted'] = 0

        if root != '':
            root.progressBar['value'] = 5.0

        # ---------------------------------------------------------------------
        # 2) distribute zonal population over combinations

        print('\t\tDistribute zonal population over combinations...')
        log_file.write('\t\tDistribute zonal population over combinations...\n')

        segs = segs.fillna(0)

        # Loop over zones, agegr and incgr
        # and add population and urbanisation level to each row of demandDF
        for z in zoneList:
            tmpNumPers = segs.at[z, '2: inwoners']
            tmpSTED = segs.at[z, 'STED']

            for a in ageList:
                tmpKLEEFT = segs.at[z, f'KLEEFT_{a}']
                
                for i in incList:
                    tmpHHINK = segs.at[z, f'HHINK_{i}']

                    # Add population:
                    # (people of age a) / zonal population * (people in income classes i)
                    if tmpNumPers > 0:
                        pers = tmpKLEEFT / tmpNumPers * tmpHHINK
                        demandDF.at[(z, a, i), 'pers'] = pers

                    # Add urbanisation level
                    demandDF.at[(z, a, i), 'sted'] = tmpSTED

        if root != '':
            root.progressBar['value'] = 15.0

        # ---------------------------------------------------------------------
        # 3) add the 3 corresponding parameter values (for sted, inc, age)
        # to each row and calculate sum

        print('\t\tAdd up 3 params (sted, inc, age) for each combination')
        log_file.write('\t\tAdd up 3 params (sted, inc, age) for each combination\n')

        demandDF['param_age'] = 0.00
        demandDF['param_inc'] = 0.00
        demandDF['param_urb'] = 0.00

        # Add age param
        for a in ageList:
            param_age = demandParams['Estimate'][
                demandParams['Parameter'] == f'KLEEFT2_{a}']

            for i in incList:
                for z in zoneList:
                    demandDF.at[(z, a, i), 'param_age'] = param_age

        if root != '':
            root.progressBar['value'] = 30.0

        # Add income param
        for i in incList:
            param_inc = demandParams['Estimate'][
                demandParams['Parameter'] == f'HHBRUTOINK2_w5_{i}']

            for z in zoneList:
                for a in ageList:
                    demandDF.at[(z, a, i), 'param_inc'] = param_inc 

        if root != '':
            root.progressBar['value'] = 45.0

        # Add urbanisation parameter
        # This loop seems to be necessary as we do not have
        # a parameter for sted = 0
        for z in zoneList:
            sted = segs.at[z, 'STED']

            if sted > 0:
                sted_param = demandParams.loc[
                    demandParams['Parameter'] == f'STED_GM_{int(sted)}',
                    'Estimate']

            else:
                sted_param = 0

            for a in ageList:
                for i in incList:
                    demandDF.at[(z, a, i), 'param_urb'] = sted_param

        demandDF['param_sum'] = (
            demandDF['param_age'] +
            demandDF['param_inc'] +
            demandDF['param_urb'])

        if root != '':
            root.progressBar['value'] = 60.0

        # ---------------------------------------------------------------------
        # 4) calculate cumprobs and then probs

        print('\t\tCalculative cumulative probabilities...')
        log_file.write('\t\tCalculative cumulative probabilities...\n')

        # Make dictionary with threshold parameters (mu)
        # and corresponding number of parcels
        mu_dict = {}
        parcel_levels = [0, 1, 2, 3, 4, 5, 10, 15, 20]
        for x in parcel_levels:
            mu_dict[x] = demandParams['Estimate'].loc[
                demandParams['Parameter'] == f'WI_nongroceries_{x}'].iloc[-1]

        # Calculate cumulative probabilities with logit formula
        for p in parcel_levels[:-1]:
            mu = mu_dict[p]
            # print(p, np.round(mu, 3))
            demandDF[f'cprob_{p}p'] = (
                1 + np.exp(demandDF['param_sum'] - mu)) ** (-1)

        # Cum prob for highest category is 1 by definition
        demandDF['cprob_20p'] = 1

        # Calculate probabilities (differences between consecutive cprob)
        for p in parcel_levels[1:]:
            demandDF[f'prob_{p}p'] = (
                demandDF[f'cprob_{p}p'] -
                demandDF[f'cprob_{parcel_levels[parcel_levels.index(p) - 1]}p'])

        # Probability 0 parcels
        demandDF['prob_0p'] = demandDF['cprob_0p']

        # ---------------------------------------------------------------------
        # 5) multiply each prob with corresponding no of
        # parcels and ppl in the row
        demandDF['parcels_pp'] = 0

        for p in parcel_levels:
            s = demandParams['Parcels'].loc[
                demandParams['Parameter'] == f'WI_nongroceries_{p}'].iloc[-1]
            # print(p, s)
            demandDF['parcels_pp'] += demandDF[f'prob_{p}p'] * s

        demandDF['parcels'] = demandDF['parcels_pp'] * demandDF['pers']

        if root != '':
            root.progressBar['value'] = 65.0

        # ---------------------------------------------------------------------
        # 6) aggregate to zone level and divide by 60 to
        # get daily no of parcels

        print('\t\tAggregate to zonal level...')
        log_file.write('\t\tAggregate to zonal level...\n')

        demandDF = demandDF.replace(np.nan, 0)
        demandPerZone = pd.pivot_table(
            demandDF.reset_index(),
            values=['parcels', 'pers'],
            index=['zone'],
            aggfunc=np.sum)

        # Add the B2C parcels to the B2B parcels
        zones['parcels'] += (demandPerZone['parcels'] / 60)

        # Spread over couriers based on market shares
        for cep in cepList:
            zones['parcels_' + str(cep)] = np.array(
                np.round(cepShares['ShareTotal'][cep] * zones['parcels']),
                dtype=int)

        # Total number of parcels per courier
        nParcels = int(zones[
            ["parcels_" + str(cep) for cep in cepList]].sum().sum())

        # Put parcel demand in Numpy array (faster indexing)
        cols = ['Parcel_ID', 'O_zone', 'D_zone', 'DepotNumber']
        parcels = np.zeros((nParcels, len(cols)), dtype=int)
        parcelsCep = np.array(['' for i in range(nParcels)], dtype=object)

        if root != '':
            root.progressBar['value'] = 70.0

        # Now determine for each zone and courier from which depot
        # the parcels are delivered
        count = 0

        # Loop over zones
        for zoneID in zones['AREANR']:

            # If there are parcels for the selected zones
            if zones['parcels'][zoneID] > 0:

                # Loop over all CEPs for that zone
                for cep in cepList:
                    # Select dc of current CEP based on min in parcelSkim
                    parcelNodeIndex = cepNodeDict[cep][parcelSkim[
                        invZoneDict[zoneID] - 1, cepNodeDict[cep]].argmin()]

                    # Fill the df parcels with parcels, zone after zone.
                    # Parcels consist of ID, D and O zone and parcel node
                    # number in ongoing df from index count-1 the next x=no.
                    # of parcels rows, fill the cell in the column Parcel_ID
                    # with a number
                    n = zones.loc[zoneID, 'parcels_' + str(cep)]

                    # Parcel_ID
                    parcels[count:(count + n), 0] = (
                        np.arange(count + 1, count + 1 + n, dtype=int))

                    # O_zone
                    parcels[count:(count + n), 1] = (
                        parcelNodes['AREANR'][parcelNodeIndex + 1])

                    # D_zone, DepotNumber and CEP
                    parcels[count:(count + n), 2] = zoneID
                    parcels[count:(count + n), 3] = parcelNodeIndex + 1
                    parcelsCep[count:(count + n)] = cep

                    count += zones['parcels_' + str(cep)][zoneID]

        # Put the parcel demand data back in a DataFrame
        parcels = pd.DataFrame(parcels, columns=cols)
        parcels['CEP'] = parcelsCep

        # Default vehicle type for parcel deliveries: vans
        parcels['VEHTYPE'] = 7

        if root != '':
            root.progressBar['value'] = 75.0

        # ----------- Extra steps for rerouting through microhubs -------------

        # Rerouting through microhubs
        if varDict['LABEL'][0:3] == 'MIC':
            # Write the REF parcel demand
            print("Writing REF parcels to ParcelDemand_REF.csv")
            log_file.write(
                '[' + datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S") + ']\t'+
                f"Writing REF parcels to ParcelDemand_{tier}_{mode}_.csv\n")
            parcels.to_csv(
                f"{varDict['OUTPUTFOLDER']}ParcelDemand_REF.csv",
                index=False)

            print('Redirecting parcels through microhubs...')
            log_file.write(
                '[' + datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S") + ']\t'+
                'Redirecting parcels through microhubs\n')

            parcels['FROM_MH'] = 0
            parcels['TO_MH'] = 0

            # Store destinations of parcels
            destZones = np.array(parcels['D_zone'].astype(int))

            # Store depot numbers (origins of parcels)
            depotNumbers = np.array(parcels['DepotNumber'].astype(int))

            # Store indices of parcels in destZones where destZone is in ZEZ==2
            mh_parcels = np.where(zones['ZEZ'][destZones] == 2)[0]

            newParcels = np.zeros(
                (len(mh_parcels), parcels.shape[1]),
                dtype=object)

            count = 0
            for parcel_id in mh_parcels: 

                trueDest = destZones[parcel_id]
                cep = parcelsCep[parcel_id]

                if tier =='Horizontal Collaboration':
                    mhzone = zones['MH_zone'][trueDest]
                if tier =='Individual CEP':
                    mhzone = zones[f'MH_zone_{cep}'][trueDest]

                # Leg A: from depots to MH
                # (change existing record of the parcel)
                parcels.at[parcel_id, 'D_zone'] = mhzone.copy()   # MH as destination leg A
                parcels.at[parcel_id, 'TO_MH'] = microhubs.index[
                    microhubs['AREANR'] == mhzone][0]
                parcels.at[parcel_id, 'VEHTYPE'] = modeNumbersDict["TR"]

                # Leg B: microhub to final destination
                # (make new record to add to the end of the parcels-df)
                newParcels[count, 1] = mhzone                         # MH as origin Leg B 
                newParcels[count, 2] = trueDest                       # Destination leg B (zone of HH or business)
                newParcels[count, 3] = depotNumbers[parcel_id]        # Depot ID 
                newParcels[count, 4] = cep                            # Courier name

                if mode == "AR":
                    dist = np.round((skimTravDist[
                        (invZoneDict[mhzone] - 1) * nZones + (invZoneDict[trueDest] - 1)]), 4)

                    # Radius of a microhub for AR operations
                    radius = 500

                    # Vehicle type electric bike
                    if dist > radius:
                        newParcels[count, 5] = modeNumbersDict["EB"]
                    # Vehicle type autonomous robot
                    else:
                        newParcels[count, 5] = modeNumbersDict[mode]

                # Green vehicle type
                else:
                    newParcels[count, 5] = modeNumbersDict[mode]

                #  MH that is origin of this leg
                newParcels[count, 6] = microhubs.index[microhubs['AREANR'] == mhzone][0]

                 # To MH is zero here (leg B)
                newParcels[count, 7] = 0

                count += 1

            newParcels = pd.DataFrame(newParcels)
            newParcels.columns = parcels.columns

            dtypes = {
                'Parcel_ID': int,
                'O_zone': int,
                'D_zone': int,
                'DepotNumber': int,
                'CEP': str,
                'VEHTYPE': int,
                'FROM_MH': int,
                'TO_MH': int}
            for col in dtypes.keys():
                newParcels[col] = newParcels[col].astype(dtypes[col])

            parcels = parcels.append(newParcels)
            parcels.index = np.arange(len(parcels))
            parcels['Parcel_ID'] = np.arange(1, len(parcels) + 1)

            nParcels = len(parcels)

            print(f'{len(newParcels)} out of {nParcels} parcels are redirected through microhubs')
            log_file.write(
                '[' + datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S") + ']\t' +
                f'{len(newParcels)} out of {nParcels} parcels are redirected through microhubs\n')

            if mode == "AR":
                nARparcels = len(newParcels[newParcels['VEHTYPE'] == 13])

                message = (
                    f'{nARparcels} out of {len(newParcels)}' +
                    'microhub parcels are delivered by AR')
                print(message)
                log_file.write(
                    '[' + datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S") + ']\t' +
                    message + '\n')

        # ---------------------------- UCC ------------------------------------
        # Rerouting through UCCs in the UCC-scenario
        if varDict['LABEL'] == 'UCC': 

            vtNamesUCC = [
                'LEVV',
                'Moped',
                'Van',
                'Truck',
                'TractorTrailer',
                'WasteCollection',
                'SpecialConstruction']

            dimLS = pd.read_csv(
                varDict['DIMFOLDER'] + 'logistic_segment.txt',
                sep='\t')
            nLS = len(dimLS) - 1

            # Logistic segment for determining UCC vehicle types is 6: parcels
            ls = 6

            # Write the REF parcel demand
            print(f"Writing parcels to {varDict['OUTPUTFOLDER']}ParcelDemand_REF.csv")
            log_file.write(f"Writing parcels to {varDict['OUTPUTFOLDER']}ParcelDemand_REF.csv\n")
            parcels.to_csv(f"{varDict['OUTPUTFOLDER']}ParcelDemand_REF.csv", index=False)  

            # Consolidation potential per logistic segment (for UCC scenario)
            probConsolidation = np.array(pd.read_csv(
                varDict['ZEZ_CONSOLIDATION'],
                index_col='Segment'))

            # Vehicle/combustion shares (for UCC scenario)
            sharesUCC = pd.read_csv(
                varDict['ZEZ_SCENARIO'],
                index_col='Segment')

            # Assume no consolidation potential and vehicle type
            # switch for dangerous goods
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
                sharesVehUCC[ls, :] = np.cumsum(
                    sharesVehUCC[ls, :]) / np.sum(sharesVehUCC[ls, :])

            # Couple these vehicle types to Harmony vehicle types
            vehUccToVeh = {
                0: 8,
                1: 9,
                2: 7,
                3: 1,
                4: 5,
                5: 6,
                6: 6}

            print('Redirecting parcels via UCC...')
            log_file.write('Redirecting parcels via UCC...\n')

            parcels['FROM_UCC'] = 0
            parcels['TO_UCC'] = 0

            origZones = np.array(parcels['O_zone'].astype(int))
            destZones = np.array(parcels['D_zone'].astype(int))
            depotNumbers = np.array(parcels['DepotNumber'].astype(int))
            whereDestZEZ = np.where(
                (zones['ZEZ'][destZones] >= 1) &
                (probConsolidation[ls][0] > np.random.rand(len(parcels))))[0]

            newParcels = np.zeros(parcels.shape, dtype=object)

            uccZones = np.unique(zones.loc[zones['UCC_zone'] != 0, 'UCC_zone'])
            uccZonesGemeente = np.array(zones.loc[uccZones, 'GEMEENTEN'])
            nUccZones = len(uccZones)

            count = 0

            for i in whereDestZEZ:

                trueOrig = origZones[i]
                trueDest = destZones[i]
                trueDestGemeente = zones.at[trueDest, 'GEMEENTEN']
                #newDest = zones['UCC_zone'][trueDest]

                distsFirstLeg = [
                    skimDistance[(invZoneDict[trueOrig] - 1) * nZones + (invZoneDict[uccZones[j]] - 1)]
                    for j in range(nUccZones)]
                distsSecondLeg = [
                    skimDistance[(invZoneDict[uccZones[j]] - 1) * nZones + (invZoneDict[trueDest] - 1)]
                    for j in range(nUccZones)]
                dists = np.array(distsFirstLeg) + np.array(distsSecondLeg)
                dists[np.where(uccZonesGemeente != trueDestGemeente)[0]] = 1000000
                newDest = uccZones[np.argmin(dists)]

                # Redirect to UCC
                parcels.at[i, 'D_zone'] = newDest
                parcels.at[i, 'TO_UCC'] = 1

                # Add parcel set to ZEZ from UCC
                newParcels[count, 1] = newDest          # Origin
                newParcels[count, 2] = trueDest         # Destination
                newParcels[count, 3] = depotNumbers[i]  # Depot ID
                newParcels[count, 4] = parcelsCep[i]    # Courier name
                newParcels[count, 6] = 1                # From UCC
                newParcels[count, 7] = 0                # To UCC

                # Vehicle type
                newParcels[count, 5] = vehUccToVeh[np.where(
                    sharesVehUCC[ls, :] > np.random.rand())[0][0]]

                count += 1

            newParcels = pd.DataFrame(newParcels)
            newParcels.columns = parcels.columns
            newParcels = newParcels.iloc[np.arange(count), :]

            dtypes = {
                'Parcel_ID': int,
                'O_zone': int,
                'D_zone': int,
                'DepotNumber': int,
                'CEP': str,
                'VEHTYPE': int,
                'FROM_UCC': int,
                'TO_UCC': int}
            for col in dtypes.keys():
                newParcels[col] = newParcels[col].astype(dtypes[col])

            parcels = parcels.append(newParcels)
            parcels.index = np.arange(len(parcels))
            parcels['Parcel_ID'] = np.arange(1, len(parcels) + 1)

            nParcels = len(parcels)

        if root != '':
            root.progressBar['value'] = 90.0

        # ------------------------- Prepare output ----------------------------

        # Write the parcels to CSV (each row is a parcel)
        message = (
            "Writing parcels CSV to " +
            varDict['OUTPUTFOLDER'] + "ParcelDemand_" + varDict['LABEL'] + ".csv")
        print(message)
        log_file.write(message + "\n")

        parcels.to_csv(
            varDict['OUTPUTFOLDER'] + "ParcelDemand_" + varDict['LABEL'] + ".csv",
            index=False)

        if root != '':
            root.progressBar['value'] = 95.0

        # Aggregate to number of parcels per zone and export to geojson
        message = (
            "Writing parcels GeoJSON to " +
            varDict['OUTPUTFOLDER'] + "ParcelDemand_" + varDict['LABEL'] + ".geojson")
        print(message)
        log_file.write(message + "\n")

        if varDict['LABEL'] == 'UCC':
            parcelsShape = pd.pivot_table(
                parcels,
                values=['Parcel_ID'],
                index=[
                    "DepotNumber",
                    'CEP',
                    'D_zone', 'O_zone',
                    'VEHTYPE',
                    'FROM_UCC', 'TO_UCC'],
                aggfunc={
                    'DepotNumber': np.mean,
                    'CEP': 'first',
                    'O_zone': np.mean,
                    'D_zone': np.mean,
                    'Parcel_ID': 'count',
                    'VEHTYPE': np.mean,
                    'FROM_UCC': np.mean,
                    'TO_UCC': np.mean})
            parcelsShape = parcelsShape.rename(columns={'Parcel_ID':'Parcels'})
            parcelsShape = parcelsShape.set_index(np.arange(len(parcelsShape)))
            parcelsShape = parcelsShape.reindex(
                columns=[
                    'O_zone', 'D_zone',
                    'Parcels',
                    'DepotNumber',
                    'CEP',
                    'VEHTYPE',
                    'FROM_UCC', 'TO_UCC'])
            parcelsShape = parcelsShape.astype({
                'DepotNumber': int,
                'O_zone': int,
                'D_zone': int,
                'Parcels': int,
                'VEHTYPE': int,
                'FROM_UCC': int,
                'TO_UCC': int})

        elif varDict['LABEL'][0:3] == 'MIC':
            parcelsShape = pd.pivot_table(
                parcels,
                values=['Parcel_ID'],
                index=[
                    "DepotNumber",
                    'CEP',
                    'D_zone', 'O_zone',
                    'VEHTYPE',
                    'FROM_MH', 'TO_MH'],
                aggfunc={
                    'DepotNumber': np.mean,
                    'CEP': 'first',
                    'O_zone': np.mean,
                    'D_zone': np.mean,
                    'Parcel_ID': 'count',
                    'VEHTYPE': np.mean,
                    'FROM_MH': np.mean,
                    'TO_MH': np.mean})
            parcelsShape = parcelsShape.rename(
                columns={'Parcel_ID': 'Parcels'})
            parcelsShape = parcelsShape.set_index(np.arange(len(parcelsShape)))
            parcelsShape = parcelsShape.reindex(
                columns=[
                    'O_zone', 'D_zone',
                    'Parcels',
                    'DepotNumber',
                    'CEP',
                    'VEHTYPE',
                    'FROM_MH', 'TO_MH'])
            parcelsShape = parcelsShape.astype({
                'DepotNumber': int,
                'O_zone': int,
                'D_zone': int,
                'Parcels': int,
                'VEHTYPE': int,
                'FROM_MH': int,
                'TO_MH': int})

            parcelsPerCEP = pd.pivot_table(
                parcels[parcels['FROM_MH'] > 0],
                values=['Parcel_ID'],
                index=['CEP', 'FROM_MH', 'O_zone'],
                aggfunc={'Parcel_ID': 'count'})
            parcelsPerCEP.columns = ['ParcelCount']

            parcelsPerCEP.to_csv(
                varDict['OUTPUTFOLDER'] + "ParcelsPerMicrohubCEP_MIC.csv",
                index=True)

        else:
            parcelsShape = pd.pivot_table(
                parcels,
                values=['Parcel_ID'],
                index=[
                    "DepotNumber",
                    'CEP',
                    'D_zone', 'O_zone'],
                aggfunc={
                    'DepotNumber': np.mean,
                    'CEP': 'first',
                    'O_zone': np.mean,
                    'D_zone': np.mean,
                    'Parcel_ID': 'count'})
            parcelsShape = parcelsShape.rename(
                columns={'Parcel_ID': 'Parcels'})
            parcelsShape = parcelsShape.set_index(np.arange(len(parcelsShape)))
            parcelsShape = parcelsShape.reindex(
                columns=[
                    'O_zone', 'D_zone',
                    'Parcels',
                    'DepotNumber',
                    'CEP'])
            parcelsShape = parcelsShape.astype({
                'DepotNumber': int,
                'O_zone': int,
                'D_zone': int,
                'Parcels': int})

        # Initialize arrays with coordinates
        Ax = np.zeros(len(parcelsShape), dtype=int)
        Ay = np.zeros(len(parcelsShape), dtype=int)
        Bx = np.zeros(len(parcelsShape), dtype=int)
        By = np.zeros(len(parcelsShape), dtype=int)

        # Determine coordinates of LineString for each trip
        depotIDs = np.array(parcelsShape['DepotNumber'])
        for i in parcelsShape.index:
            if varDict['LABEL'] == 'UCC':
                if parcelsShape.at[i, 'FROM_UCC'] == 1:
                    Ax[i] = zonesX[parcelsShape['O_zone'][i]]
                    Ay[i] = zonesY[parcelsShape['O_zone'][i]]
                    Bx[i] = zonesX[parcelsShape['D_zone'][i]]
                    By[i] = zonesY[parcelsShape['D_zone'][i]]
                else:
                    Ax[i] = parcelNodes['X'][depotIDs[i]]
                    Ay[i] = parcelNodes['Y'][depotIDs[i]]
                    Bx[i] = zonesX[parcelsShape['D_zone'][i]]
                    By[i] = zonesY[parcelsShape['D_zone'][i]]
            elif varDict['LABEL'][:3] == 'MIC':
                Ax[i] = zonesX[parcelsShape['O_zone'][i]]
                Ay[i] = zonesY[parcelsShape['O_zone'][i]]
                Bx[i] = zonesX[parcelsShape['D_zone'][i]]
                By[i] = zonesY[parcelsShape['D_zone'][i]]
            else:
                Ax[i] = parcelNodes['X'][depotIDs[i]]
                Ay[i] = parcelNodes['Y'][depotIDs[i]]
                Bx[i] = zonesX[parcelsShape['D_zone'][i]]
                By[i] = zonesY[parcelsShape['D_zone'][i]]

        Ax = np.array(Ax, dtype=str)
        Ay = np.array(Ay, dtype=str)
        Bx = np.array(Bx, dtype=str)
        By = np.array(By, dtype=str)
        nRecords = len(parcelsShape)

        filename = (
            varDict['OUTPUTFOLDER'] +
            "ParcelDemand_" + varDict['LABEL'] + ".geojson")

        with open(filename, 'w') as geoFile:
            geoFile.write('{\n' + '"type": "FeatureCollection",\n' + '"features": [\n')
            for i in range(nRecords - 1):
                outputStr = ""
                outputStr = outputStr + '{ "type": "Feature", "properties": '
                outputStr = outputStr + str(parcelsShape.loc[i,:].to_dict()).replace("'",'"')
                outputStr = outputStr + ', "geometry": { "type": "LineString", "coordinates": [ [ '
                outputStr = outputStr + Ax[i] + ', ' + Ay[i] + ' ], [ '
                outputStr = outputStr + Bx[i] + ', ' + By[i] + ' ] ] } },\n'
                geoFile.write(outputStr)

                if i % int(nRecords / 10) == 0:
                    print('\t' + str(round(i / nRecords * 100, 1)) + '%',
                          end='\r')

            # Bij de laatste feature moet er geen komma aan het einde
            i += 1
            outputStr = ""
            outputStr = outputStr + '{ "type": "Feature", "properties": '
            outputStr = outputStr + str(parcelsShape.loc[i,:].to_dict()).replace("'",'"')
            outputStr = outputStr + ', "geometry": { "type": "LineString", "coordinates": [ [ '
            outputStr = outputStr + Ax[i] + ', ' + Ay[i] + ' ], [ '
            outputStr = outputStr + Bx[i] + ', ' + By[i] + ' ] ] } }\n'
            geoFile.write(outputStr)
            geoFile.write(']\n')
            geoFile.write('}')

        totaltime = round(time.time() - start_time, 2)
        print('Finished. Run time: ' + str(totaltime) + ' seconds')
        log_file.write("Total runtime: %s seconds\n" % (totaltime))  
        log_file.write("End simulation at: "+datetime.datetime.now().strftime("%y-%m-%d %H:%M")+"\n")
        log_file.close()    

        if root != '':
            root.update_statusbar("Parcel Demand: Done")
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
                root.update_statusbar("Parcel Demand: Execution failed!")
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

    varDict['INPUTFOLDER']   = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/data/2016/'
    varDict['OUTPUTFOLDER']  = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/output/RunREF2016/'
    varDict['PARAMFOLDER']   = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/parameters/'
    varDict['DIMFOLDER']	 = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/dimensions/'

    varDict['SKIMTIME']     = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/data/LOS/2016/skimTijd_REF.mtx'
    varDict['SKIMDISTANCE'] = 'P:/Projects_Active/18007 EC HARMONY/Work/WP6/MassGT_v12/data/LOS/2016/skimAfstand_REF.mtx'
    varDict['LINKS']              = varDict['INPUTFOLDER'] + 'links_v5.shp'
    varDict['NODES']              = varDict['INPUTFOLDER'] + 'nodes_v5.shp'
    varDict['ZONES']              = varDict['INPUTFOLDER'] + 'Zones_v5.shp'
    varDict['SEGS']               = varDict['INPUTFOLDER'] + 'SEGS2016_verrijkt.csv'
    varDict['COMMODITYMATRIX']    = varDict['INPUTFOLDER'] + 'CommodityMatrixNUTS3_2016.csv'
    varDict['PARCELNODES']        = varDict['INPUTFOLDER'] + 'parcelNodes_v2.shp'
    varDict['CEP_SHARES']         = varDict['INPUTFOLDER'] + 'CEPshares.csv'
    varDict['DISTRIBUTIECENTRA']  = varDict['INPUTFOLDER'] + 'distributieCentra.csv'
    varDict['NSTR_TO_LS']         = varDict['INPUTFOLDER'] + 'nstrToLogisticSegment.csv'
    varDict['MAKE_DISTRIBUTION']  = varDict['INPUTFOLDER'] + 'MakeDistribution.csv'
    varDict['USE_DISTRIBUTION']   = varDict['INPUTFOLDER'] + 'UseDistribution.csv'
    varDict['SUP_COORDINATES_ID'] = varDict['INPUTFOLDER'] + 'SupCoordinatesID.csv'
    varDict['CORRECTIONS_TONNES'] = varDict['INPUTFOLDER'] + 'CorrectionsTonnes2016.csv'
    varDict['DEPTIME_FREIGHT']    = varDict['INPUTFOLDER'] + 'departureTimePDF.csv'
    varDict['DEPTIME_PARCELS']    = varDict['INPUTFOLDER'] + 'departureTimeParcelsCDF.csv'

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
    main(varDict)


