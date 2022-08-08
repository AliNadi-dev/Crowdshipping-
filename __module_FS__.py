# -*- coding: utf-8 -*-
"""
Created on Wed Oct 21 17:07:15 2020

@author: LEG
"""

import pandas as pd
import numpy as np
from scipy import stats
import time
import datetime
from shapely.geometry import Point, Polygon, MultiPolygon
from __functions__ import read_shape

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
        self.root.title("Progress Firm Synthesis")
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

        log_file = open(
            varDict['OUTPUTFOLDER'] + "Logfile_FirmSynthesis.log", "w")
        log_file.write(
            "Start simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")

        start_time = time.time()

        doValidationChecks = False

        maxZoneNumberZH = 7400
        minEmplLevelOutput = 3

        # ------------------------- Import data -------------------------------

        print('Importing data...')
        log_file.write('Importing data...\n')

        if root != '':
            root.update_statusbar('Importing data...')

        dimSector = pd.read_csv(
            varDict['DIMFOLDER'] + 'employment_sector.txt',
            sep='\t')
        sectorNames = [str(x) for x in dimSector['Comment'].values]

        # Shapefile of study area
        zones, zonesGeometry = read_shape(
            varDict['ZONES'],
            returnGeometry=True)
        zones = zones.sort_values('AREANR')
        zonesGeometry = [zonesGeometry[i] for i in zones.index]
        zones.index = zones['AREANR']
        nInternalZones = len(zones)

        if root != '':
            root.progressBar['value'] = 1

        # Get zones as shapely MultiPolygon/Polygon objects
        shapelyZones = []
        for x in zonesGeometry:
            if x['type'] == 'MultiPolygon':
                tmp = []

                for i in range(len(x['coordinates'])):
                    if len(x['coordinates'][i]) > 1:
                        tmp.append(Polygon(
                            x['coordinates'][i][0],
                            [x['coordinates'][i][j]
                             for j in range(1, len(x['coordinates'][i]))]))

                    else:
                        tmp.append(Polygon(x['coordinates'][i][0]))

                shapelyZones.append(MultiPolygon(tmp))

            elif x['type'] == 'Polygon':
                if len(x['coordinates']) > 1:
                    shapelyZones.append(Polygon(
                        x['coordinates'][0],
                        [x['coordinates'][i]
                         for i in range(1, len(x['coordinates']))]))

                else:
                    shapelyZones.append(Polygon(x['coordinates'][0]))

            else:
                message = (
                    'Warning! ' +
                    'Object types other than Polygon or MultiPolygon' +
                    ' found in zones shape!')
                print(message)
                log_file.write(message + '\n')

        if root != '':
            root.progressBar['value'] = 2

        # Zonal / Socioeconomic data
        segs = pd.read_csv(varDict['SEGS'])
        segs.index = segs['zone']
        segsEmpl = segs[sectorNames].copy().round()

        # Adjust zonal employment data for distribution centres
        # and transshipment terminals in zones with DC,
        # the jobs in DC are known and subtracted from industry jobs
        dcs = pd.read_csv(varDict['DISTRIBUTIECENTRA'])

        # Aggregate jobs (WP) per zone
        dcs_wp = dcs.pivot_table(
            index='AREANR',
            values='WP',
            aggfunc='sum')

        # Add jobs in DC to segsEmpl df
        segsEmpl['WP'] = np.zeros(len(segsEmpl))
        for x in dcs_wp.index:
            segsEmpl['WP'][x] = dcs_wp['WP'][x]

        # Update number of industrie jobs and set to 0
        # in case it got smaller than 0
        segsEmpl['INDUSTRIE_voorCorr'] = segsEmpl['INDUSTRIE'].copy()
        segsEmpl['INDUSTRIE'] = segsEmpl['INDUSTRIE_voorCorr'] - segsEmpl['WP']
        segsEmpl['INDUSTRIE'][segsEmpl['INDUSTRIE'] < 0] = 0

        jobs_init = segsEmpl['INDUSTRIE_voorCorr'].sum()
        jobs_zonderDC = segsEmpl['INDUSTRIE'].sum()

        # In zones with transshipment terminals (lognode=1),
        # remaining industry jobs are set to zero
        segsEmpl['LOGNODE'] = zones['LOGNODE'].copy()
        segsEmpl['INDUSTRIE'][segsEmpl['LOGNODE'] == 1] = 0

        jobs_final = segsEmpl['INDUSTRIE'].sum()

        message = (
            '\tINDUSTRIE jobs in SEGs:' + '\t\t' +
            str(jobs_init) + '\n' +
            '\tINDUSTRIE jobs w/o DC:' + '\t\t' +
            str(jobs_zonderDC) + '\n' +
            '\tINDUSTRIE jobs in DC: ' + '\t\t' +
            str(dcs_wp['WP'].sum()) + '\n' +
            '\tINDUSTRIE jobs w/o DC and TT:' + '\t' +
            str(jobs_final))
        print(message)
        log_file.write(message + '\n')

        message = ('' +
            (
                '\tAdjusting zonal data for jobs in DCs and ' +
                'transshipment terminals to avoid double counting...\n') +
            (
                '\t\tINDUSTRIE jobs before adjustment: ' +
                str(jobs_init) + '\n') +
            (
                '\t\tINDUSTRIE jobs in DCs (input):    ' +
                str(dcs_wp['WP'].sum()) + '\n') +
            (
                '\t\tINDUSTRIE jobs removed for DC:    ' +
                str(jobs_init - jobs_zonderDC) + '\n') +
            (
                '\t\tINDUSTRIE jobs removed for TT:    ' +
                str(jobs_zonderDC - jobs_final) +  '\n') +
            (
                '\t\tINDUSTRIE jobs w/o DC and TT:     ' +
                str(jobs_final))
        )
        print(message)
        log_file.write(message + '\n')

        # Remove columns that are not needed for synthesis
        segsEmpl = segsEmpl.drop(['INDUSTRIE_voorCorr', 'WP', 'LOGNODE'], 1)

        if root != '':
            root.progressBar['value'] = 3

        # Koppeltabel sectoren inlezen
        koppel_sectors = pd.read_csv(varDict['SBI_TO_SEGS'])
        sectors_dict = dict(zip(
            koppel_sectors['Sector_SBI'],
            koppel_sectors['Sector_SEGs']))

        # Read firm input data
        firmSizePerSector = pd.read_csv(varDict['FIRMSIZE'])
        firmSizePerSector.index = firmSizePerSector['Sector']
        firmSizePerSector.drop('Sector', inplace=True, axis=1)

        firmSize_labels = firmSizePerSector.columns[1:].to_list()
        firmSize_dict = dict(zip(
            firmSizePerSector.columns[1:],
            [
                (1, 5),
                (5, 10),
                (10, 20),
                (20, 50),
                (50, 100),
                (100, 150, 1000)
            ]))

        if root != '':
            root.progressBar['value'] = 4

        # ----- Create random distribution from firm size x sector table ------

        # First create random distribution for all sectors combined;
        # starting point: firmSizePerSector - joint distribution table.
        # Drop column with SEGs-sectors which is not needed here
        firmSizeALL = firmSizePerSector.drop(['Sector_SEGs'], axis=1)

        # Create probability density function
        firmsXsectorALL_pdf = (firmSizeALL / 1.0) / sum(sum(firmSizeALL.values))

        # Convert 2d shape to 1d
        firmsXsectorALL_pdf = firmsXsectorALL_pdf.values.ravel()

        # Create random distributions for all SEG-sectors
        SEGs_sectors = list(firmSizePerSector['Sector_SEGs'].unique())

        firmSize = {}
        firmsXsector = {}
        firmsXsector_pdf = {}
        indices = {}
        distr = {}
        for sect in SEGs_sectors:
            firmSize[sect] = firmSizePerSector[
                firmSizePerSector['Sector_SEGs'] == sect].drop(
                    ['Sector_SEGs'],
                    axis=1)

            firmsXsector[sect] = firmSize[sect].apply(
                lambda x: x.index + '::' + x.name).values.ravel()
            indices[sect] = range(len(firmsXsector[sect]))
            firmsXsector_pdf[sect] = (
                (firmSize[sect] / 1.0) /
                sum(sum(firmSize[sect].values)))
            firmsXsector_pdf[sect] = firmsXsector_pdf[sect].values.ravel()

            distr[sect] = stats.rv_discrete(
                name=f'distr_{sect}',
                values=(indices[sect], firmsXsector_pdf[sect]))

        if root != '':
            root.progressBar['value'] = 5

        # ------------------------ Synthesize firms ---------------------------
        # Turn number of employees per zone into firms
        # (drawn randomly from sectorXsize table)

        print('Synthesizing firms...')
        log_file.write('Synthesizing firms...\n')

        if root != '':
            root.update_statusbar('Synthesizing firms...')

        firmZones = []
        firmSectors = []
        firmSizes = []
        firmEmpl = []
        zoneEmpl = []  # Number of employees in current zone and sector

        # Select zone
        for zone in segsEmpl[:maxZoneNumberZH].index:
            assigned_jobs = 0

            # Select industry sector I
            for sect in segsEmpl.columns:
                jobs_to_assign = segsEmpl.loc[zone][sect].copy()

                while jobs_to_assign > 0:
                    # Draw a firm for current sector
                    firm = np.array([
                        x.split('::')
                        for x in firmsXsector[sect][distr[sect].rvs(size=1)]])

                    # Determine size of the firm.
                    # Ff we draw a firm from the largest category,
                    # draw from triangular distribution
                    if firm[0][1] == firmSize_labels[-1]:
                        left = 100
                        mode = max(100, 0.5 * jobs_to_assign)
                        right = max(150, 1.5 * jobs_to_assign)
                        size = int(
                            np.random.triangular(left, mode, right, size=1))

                    # If the firm is from a closed size category,
                    # draw size from uniform distribution
                    else:
                        low = firmSize_dict[firm[0][1]][0]
                        high = firmSize_dict[firm[0][1]][1]
                        size = np.random.randint(
                            low=low, high=high, size=1, dtype=int)

                    # Check if size fits in zone.
                    # If firm is not way too large, accept it and
                    # add it to list of firms
                    if size <= 1.3 * jobs_to_assign:

                        assigned_jobs += size

                        firmZones.append(zone)
                        firmSectors.append(sectors_dict[str(firm[0][0])])
                        firmSizes.append(str(firm[0][1]))
                        firmEmpl.append(size)

                        zoneEmpl.append(assigned_jobs)

                        jobs_to_assign -= size

                    else:
                        # Determine firm size based on remaining jobs to assign
                        # size = np.random.randint(8,12)/10*jobs_to_assign
                        size = jobs_to_assign
                        assigned_jobs += int(size)

                        if size >= 100:
                            sizeClass = 'Groot'
                        elif size >= 50:
                            sizeClass = 'Middelgroot'
                        elif size >= 20:
                            sizeClass = 'Middel'
                        elif size >= 10:
                            sizeClass = 'Middelklein'
                        elif size >= 5:
                            sizeClass = 'Klein'
                        else:
                            sizeClass = 'Micro'

                        firmZones.append(zone)
                        firmSectors.append(sectors_dict[str(firm[0][0])])
                        firmSizes.append(sizeClass)
                        firmEmpl.append(size)
                        zoneEmpl.append(assigned_jobs)

                        jobs_to_assign -= size

            if (zone - 1) % int((maxZoneNumberZH - 1) / 100) == 0:
                print('\t' + str(round((zone - 1) / (maxZoneNumberZH - 1) * 100, 1)) + '%',
                      end='\r')

                if root != '':
                    root.progressBar['value'] = (
                        5 +
                        (60 - 5) * (zone - 1) / (maxZoneNumberZH - 1))

        # Put firms in Numpy Array
        sizeX = len(firmZones)
        sizeY = 5
        allFirms = np.empty((sizeX, sizeY), dtype=object)
        allFirms[:, 0] = np.arange(sizeX)
        allFirms[:, 1] = firmZones
        allFirms[:, 2] = firmSectors
        allFirms[:, 3] = firmSizes
        allFirms[:, 4] = firmEmpl
        allFirms[:, 4] = allFirms[:, 4].astype('int64')

        # Put results in a dataframe
        firms_df = pd.DataFrame(
            allFirms,
            columns=[
                'FIRM_ID',
                'MRDH_ZONE',
                'SECTOR',
                'SIZE',
                'EMPL'])

        if root != '':
            root.progressBar['value'] = 65

        # ------------------- Optional validation checks ----------------------

        if doValidationChecks:
            unique_emplSize, counts_emplSize = np.unique(
                allFirms[:, 1],
                return_counts=True)
            emplSize_counts = np.asarray(
                (
                    unique_emplSize,
                    counts_emplSize,
                    np.round(counts_emplSize / np.sum(counts_emplSize), 5)
                )).T
            print(np.sum(counts_emplSize))
            print(emplSize_counts)

            unique_sector, counts_sector = np.unique(
                allFirms[:, 2],
                return_counts=True)
            sector_counts = np.asarray(
                (
                    unique_sector,
                    counts_sector,
                    np.round(counts_sector / np.sum(counts_sector), 5)
                )).T
            print(sector_counts)

            zones_jobs = firms_df.pivot_table(
                index='MRDH_ZONE',
                columns='SECTOR',
                values='EMPL',
                aggfunc='sum')
            zones_jobs['TOTAAL'] = zones_jobs.sum(axis=1, skipna=True)
            zones_jobs = zones_jobs.fillna(0)

            # Eerge with input segs to better enable comparison
            emplIn = segsEmpl.copy()
            emplIn ['TOTAAL'] = emplIn.sum(axis=1, skipna=True)
            emplIn = emplIn[emplIn.index <= maxZoneNumberZH].copy()

            emplAbsDiff = zones_jobs - emplIn
            emplAbsDiff.columns = [
                'DETAIL_absDiff',
                'DIENSTEN_absDiff',
                'INDUSTRIE_absDiff',
                'LANDBOUW_absDiff',
                'OVERHEID_absDiff',
                'OVERIG_absDiff',
                'TOTAAL_absDiff']

            emplRelDiff = (zones_jobs - emplIn) / emplIn
            emplRelDiff.columns = [
                'DETAIL_relDiff',
                'DIENSTEN_relDiff',
                'INDUSTRIE_relDiff',
                'LANDBOUW_relDiff',
                'OVERHEID_relDiff',
                'OVERIG_relDiff',
                'TOTAAL_relDiff']

            df_out = emplIn.merge(
                zones_jobs.iloc[:, -7:],
                how='left',
                left_on=emplIn.index,
                right_index=True,
                suffixes=('_in', '_out'))
            df_out = df_out.merge(
                emplAbsDiff,
                how='left',
                left_on=emplIn.index,
                right_index=True,
                suffixes=('', '_absDiff'))
            df_out = df_out.merge(
                emplRelDiff,
                how='left',
                left_on=emplIn.index,
                right_index=True,
                suffixes=('', '_relDiff'))

            df_out = df_out.fillna(0)

            synthFirmsLabel = 'run_14'
            filename = (
                varDict['OUTPUTFOLDER'] +
                f'SynthJobsPerZone_{synthFirmsLabel}.csv')
            df_out.to_csv(filename)

            # Make crosstab sector X firm size for comparison with input
            sectorsXsize_out = firms_df.pivot_table(
                index='SECTOR',
                columns='SIZE',
                values='MRDH_ZONE',
                aggfunc='count')
            sectorsXsize_out = sectorsXsize_out.fillna(0)
            filename = (
                varDict['OUTPUTFOLDER'] +
                f'SynthFirms_{synthFirmsLabel}_sectorsXsize.csv')
            sectorsXsize_out.to_csv(filename)

        # ----------------------- Draw coordinates  ---------------------------

        # Remove small firms
        firms_df = firms_df[firms_df['EMPL'] > minEmplLevelOutput]

        # New firm IDs after filtering
        firms_df['FIRM_ID'] = np.arange(len(firms_df))
        firms_df.index = np.arange(len(firms_df))
        nFirms = len(firms_df)

        message = 'Generating coordinates for ' + str(nFirms) + ' firms...'
        print(message)
        log_file.write(message + '\n')

        if root != '':
            root.update_statusbar('Generating coordinates...')

        # Dictionary with zone number (1-6625) to corresponding
        # zone number (1-7400)
        zoneDict = dict(np.transpose(np.vstack((
            np.arange(nInternalZones),
            zones['AREANR']))))
        zoneDict = {int(a): int(b) for a, b in zoneDict.items()}
        invZoneDict = dict((v, k) for k, v in zoneDict.items())

        firmZones = np.array(firms_df['MRDH_ZONE'], dtype=int)

        # Initialize two dictionaries in which we'll store the
        # drawn x- and y-coordinate for each firm
        X = {}
        Y = {}

        nTriesAllowed = 500
        nTimesNumberOfTriesReached = 0
        centroidZones = []

        for i in range(nFirms):
            # Get the zone polygon and its boundaries
            polygon = shapelyZones[invZoneDict[firmZones[i]]]
            minX, minY, maxX, maxY = polygon.bounds

            pointInPolygon = False
            numberOfTries = 0

            while (not pointInPolygon) and (numberOfTries <= nTriesAllowed):
                # Generate a random point within the zone boundaries
                x = minX + (maxX - minX) * np.random.rand()
                y = minY + (maxY - minY) * np.random.rand()
                point = Point(x, y)

                # Check if the random point is actually contained by
                # the zone polygon
                pointInPolygon = polygon.contains(point)
                numberOfTries += 1

            # If we haven't generated a point contained by the
            # zone polygon yet after {nTriesAllowed} times trying,
            # then we just take the centroid of the zone polygon
            if not pointInPolygon:
                x, y = polygon.centroid.coords[0]
                nTimesNumberOfTriesReached += 1
                centroidZones.append(firmZones[i])

            X[i], Y[i] = x, y

            if i % int(nFirms / 100) == 0:
                print('\t' + str(round(i / nFirms * 100, 1)) + '%',
                      end='\r')

                if root != '':
                    root.progressBar['value'] = 65 + (95 - 65) * i / nFirms

        firms_df['X'] = X.values()
        firms_df['Y'] = Y.values()

        message = (
            '\tHad to use the centroid coordinates for ' +
            str(nTimesNumberOfTriesReached) +
            ' of ' +
            str(nFirms) +
            ' firms')
        print(message)
        log_file.write(message + '\n')

        if nTimesNumberOfTriesReached > 0:
            message = (
                '\t(This is the case for the following zone(s): ' +
                str(np.unique(centroidZones)) + ')')
            print(message)
            log_file.write(message + ')\n')

        # ---------------------- Export firms to CSV  -------------------------

        message = (
            'Exporting firms to: ' +
            varDict['OUTPUTFOLDER'] + 'Firms.csv')
        print(message)
        log_file.write(message + '\n')

        if root != '':
            root.update_statusbar('Exporting firms...')

        firms_df.to_csv(varDict['OUTPUTFOLDER'] + 'Firms.csv', index=False)

        if doValidationChecks:
            firms_df.to_csv(
                varDict['OUTPUTFOLDER'] + f'Firms_{synthFirmsLabel}.csv',
                index=False)

        # ------------------------ End of module ------------------------------

        totaltime = round(time.time() - start_time, 2)
        print('Finished. Run time: ' + str(totaltime) + ' seconds')
        log_file.write("Total runtime: %s seconds\n" % (totaltime))
        log_file.write(
            "End simulation at: " +
            datetime.datetime.now().strftime("%y-%m-%d %H:%M") + "\n")
        log_file.close()

        if root != '':
            root.update_statusbar("Firm Synthesis: Done")
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
                root.update_statusbar("Firm Synthesis: Execution failed!")
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

