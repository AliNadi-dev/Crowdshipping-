# -*- coding: utf-8 -*-
"""
Created on Fri Jun 28 09:33:15 2019

@author: STH
"""

import pandas as pd
import numpy as np
import time
import datetime
import os.path
from sys import argv
import sys
import traceback
import scipy.sparse.csgraph
from scipy.sparse import lil_matrix
import multiprocessing as mp
import functools
from __functions__ import read_shape, write_mtx

    

def get_prev(csgraph, nNodes, zoneDict, linkDict, linksTime, linksDist, nZones, indices):
    '''
    For each origin zone and destination node, determine the previously visited node on the shortest path.
    '''
    whichCPU = indices[1]
    indices  = indices[0]
    nOrigSelection = len(indices)

    skimTime = np.zeros((nOrigSelection,nZones), dtype=float)
    skimDist = np.zeros((nOrigSelection,nZones), dtype=float)
          
    for i in range(nOrigSelection):
        prev = scipy.sparse.csgraph.dijkstra(csgraph, indices=indices[i], return_predecessors=True)[1]

        for j in range(nZones):         
            destNode = zoneDict[j]
            sequenceNodes = []
            sequenceLinks = []
            
            if prev[destNode] >= 0:
                while prev[destNode]>=0:
                    sequenceNodes.insert(0,destNode)
                    destNode = prev[destNode]
                else:
                    sequenceNodes.insert(0,destNode)  
                    
            sequenceLinks = [linkDict[sequenceNodes[w]][sequenceNodes[w+1]] for w in range(len(sequenceNodes)-1)]
            
            skimTime[i,j] = np.sum(linksTime[sequenceLinks])
            skimDist[i,j] = np.sum(linksDist[sequenceLinks])
                
        if whichCPU == 0:
            if i%int(round(nOrigSelection/20,0)) == 0:
                print('\t\t' + str(int(round((i / nOrigSelection)*100, 0))) + '%')
    
    if whichCPU == 0:
        if i%int(round(nOrigSelection/10,0)) != 0:
            print('\t\t100%')     

                
    return [skimTime, skimDist]



def main(datapaths, linksPath, skimDistancePath, selectedLinks, label, exportShp=True, allZones=True, whichZone=1, timeOfDays=np.arange(24), emissions=True):
    '''
    Skim: Main body of the script where all calculations are performed. 
    '''
    try:      
        
        start_time = time.time()

        datapath  = datapaths[0]
        datapathI = datapaths[1]
        datapathO = datapaths[2]
        datapathP = datapaths[3]
        
        log_file=open(f"{datapathO}Logfile_Skim_{label}.log", "w")
        log_file.write("Start simulation at: "+datetime.datetime.now().strftime("%y-%m-%d %H:%M")+"\n")        
        
        
        # ------------------- Importing and preprocessing network ---------------------------------------
        print("Importing and preprocessing network..."), log_file.write("Importing and preprocessing network...\n")
        
        # Import node/link shapefiles into dataframes
        MRDHlinks, MRDHlinksGeometry = read_shape(linksPath, returnGeometry=True)
        MRDHnodes = read_shape(f"{datapathI}nodes_v5.shp")
        zones     = read_shape(f"{datapathI}Zones_v4.shp")
        nNodes = len(MRDHnodes)                
        
        # Get zone numbering
        zones = zones.sort_values('AREANR')
        areaNumbers = np.array(zones['AREANR'], dtype=int)
        nIntZones   = len(zones)
        nSupZones   = 43
        nZones      = nIntZones + nSupZones
        
        # Dictionary with zone numbers (keys) to corresponding centroid node ID as given in the shapefile (values) 
        zoneDictKeys    = np.arange(nIntZones)
        zoneDictValues  = [np.where((MRDHnodes['AREANR']==areaNumbers[i]) & (MRDHnodes['TYPENO']==99))[0][0] for i in range(nIntZones)]
        zoneDict        = dict(np.transpose(np.vstack((zoneDictKeys,zoneDictValues))))
        for i in range(nSupZones):
            zoneDict[nIntZones+i] = np.where((MRDHnodes['AREANR']==99999900+i+1) & (MRDHnodes['TYPENO']==99))[0][0]
            
        # Dictionary with zone number (used in this script) to corresponding zone number (used in input/output)
        tourZoneDict    = dict(np.transpose(np.vstack( (np.arange(1,nIntZones+1), zones['AREANR']) )))
        tourZoneDict    = {int(a):int(b) for a,b in tourZoneDict.items()}
        for i in range(nSupZones):
            tourZoneDict[nIntZones+i+1] = 99999900 + i + 1
        invTourZoneDict = dict((v, k) for k, v in tourZoneDict.items())   
        
        # The node IDs as given in the shapefile (values) and a new ID numbering from 0 to nNodes (keys)
        nodeDict    = dict(np.transpose(np.vstack( (np.arange(nNodes), MRDHnodes['NODENR']) )))
        invNodeDict = dict((v, k) for k, v in nodeDict.items())
        
        # Recode the node IDs
        MRDHnodes['NODENR'] = np.arange(nNodes)
        MRDHlinks['A']      = [invNodeDict[x] for x in MRDHlinks['A']]
        MRDHlinks['B']      = [invNodeDict[x] for x in MRDHlinks['B']]
        
        # Recode the link IDs from 0 to len(MRDHlinks)
        MRDHlinks.index = np.arange(len(MRDHlinks))
        MRDHlinks.index = MRDHlinks.index.map(int)
        
        # Matrix with fromNodeID/toNodeID (row/col no.) and link IDs (values)        
        linkDict = {}
        for i in MRDHlinks.index:
            aNode = MRDHlinks['A'][i]
            bNode = MRDHlinks['B'][i]
            try:
                linkDict[aNode][bNode] = i
            except:
                linkDict[aNode] = {}
                linkDict[aNode][bNode] = i
        
        # Travel times
        MRDHlinks.loc[MRDHlinks['V_FR_OS']<=0,'V_FR_OS'] = 50
        MRDHlinks['T0'] = MRDHlinks['LENGTH'] / MRDHlinks['V_FR_OS']
        MRDHlinks['Impedance'] = np.array(MRDHlinks['T0'].copy())
        
        # Set connector travel times high so these are not chosen other than for entering/leaving network
        MRDHlinks.loc[MRDHlinks['WEGTYPE']=='voedingslink','Impedance'] = 10000
        MRDHlinks.loc[MRDHlinks['WEGTYPE']=='Vrachtverbod','Impedance'] = 10000
        
        # Set travel times on links in ZEZ Rotterdam high so these are only used to go to UCC and not for through traffic
        if label == 'UCC':
            MRDHlinks.loc[MRDHlinks['ZEZ']==1, 'Impedance'] = 10000

        # The network with costs between nodes
        csgraph = lil_matrix((nNodes, nNodes))
        csgraph[np.array(MRDHlinks['A']), np.array(MRDHlinks['B'])] = np.array(MRDHlinks['Impedance'])


        # ------------------------- Route search --------------------------------------------                   
        print("Start traffic assignment"), log_file.write("Start traffic assignment\n")        
        
        print("\tSearching routes..."), log_file.write("\tSearching routes...\n")
        # Het aantal CPUs waarover we de routekeuze spreiden
        nCPU = max(1, min(mp.cpu_count()-1, 16))
        origSelection = np.arange(nZones)
        nOrigSelection = len(origSelection)

        # Vanuit welke nodes moet 'ie gaan zoeken
        indices = np.array([zoneDict[x] for x in origSelection], dtype=int)
        indicesPerCPU       = [[indices[cpu::nCPU], cpu] for cpu in range(nCPU)]
        origSelectionPerCPU = [np.arange(nOrigSelection)[cpu::nCPU] for cpu in range(nCPU)]

        linksTime = np.array(MRDHlinks['T0'], dtype=float)
        linksDist = np.array(MRDHlinks['LENGTH'], dtype=float)
        
        skimTime = np.zeros((nOrigSelection,nZones), dtype=float)
        skimDist = np.zeros((nOrigSelection,nZones), dtype=float)
                  
        # Initialiseer een pool object dat de taken verdeelt over de CPUs
        p = mp.Pool(nCPU)
        
        # Voer de Dijkstra functie uit
        skimPerCPU = p.map(functools.partial(get_prev, csgraph, nNodes, zoneDict, linkDict, linksTime, linksDist, nZones), indicesPerCPU)
        
        # Wait for completion of processes
        p.close()
        p.join()    
            
        # Combine the results from the different CPUs
        for cpu in range(nCPU):
            for i in range(len(indicesPerCPU[cpu][0])):
                skimTime[origSelectionPerCPU[cpu][i], :] = skimPerCPU[cpu][0][i, :]
                skimDist[origSelectionPerCPU[cpu][i], :] = skimPerCPU[cpu][1][i, :]
                        
        print('Writing skim time...')
        write_mtx(datapathO + 'skimTijd_REF.mtx', np.array(np.round(skimTime.flatten()*3600,0), dtype=int), nZones)
        
        print('Writing skim distance...')
        write_mtx(datapathO + 'skimAfstand_REF.mtx', np.array(np.round(skimDist.flatten()*1000,0), dtype=int), nZones)

        # --------------------------- End of module ---------------------------
                
        totaltime = round(time.time() - start_time, 2)
        print("Total runtime: %s seconds" % (totaltime)), log_file.write("Total runtime: %s seconds\n" % (totaltime))  
        log_file.write("End simulation at: "+datetime.datetime.now().strftime("%y-%m-%d %H:%M")+"\n")
        log_file.close()    

        # Successful execution returns 0
        return [0, [0,0]]
        
    except BaseException:
        print(sys.exc_info()[0]), log_file.write(str(sys.exc_info()[0])), log_file.write("\n")
        print(traceback.format_exc()), log_file.write(str(traceback.format_exc())), log_file.write("\n")
        print("Execution failed!")
        log_file.write("Execution failed!")
        log_file.close()
        
        if __name__ == '__main__':
            input()
        
        # Use this information to display as error message in GUI
        return [1, [sys.exc_info()[0], traceback.format_exc()]]
    


#%% For if you want to run the module from this script itself (instead of calling it from the GUI module)

if __name__ == '__main__':
    
    # Define datapaths
    datapath  = os.path.dirname(os.path.realpath(argv[0]))
    datapath  = datapath.replace(os.sep, '/') + '/'
    datapath  = datapath[:-5]
    datapathI = datapath + '/data/2016/'
    datapathO = datapath + '/output/RunREF2016/'
    datapathP = datapath + '/parameters/'
    datapaths = [datapath, datapathI, datapathO, datapathP]
    
    # Parameters
    label               = 'REF'
    exportShp           = True              # Export the NRMWlinksLoaded shapefile
    allZones            = True              # Assign traffic for all zones
    whichZone           = 1                 # If allZones = False, assign only for this zone
    emissions           = True              # Calculate emissions
    timeOfDays          = np.arange(24)
    
    linksPath        = datapathI + 'links_v5.shp'
    skimDistancePath = datapathI[:-5] + 'LOS/2016/skimAfstand_REF.mtx'
    selectedLinks = ''
    
    main(datapaths, linksPath, skimDistancePath, selectedLinks, label, exportShp, allZones, whichZone, timeOfDays, emissions)

     
#%% For visualization of a particular OD-path during debugging
    
#import matplotlib.pyplot as plt
#import geopandas as gpd
##xLower =  65000
##xUpper = 100000
##yLower = 425000
##yUpper = 470000
#
#xLower =  50000
#xUpper = 250000
#yLower = 300000
#yUpper = 500000
#
##zones = gpd.read_file(datapathI + 'Zones_v4.shp')
##links = gpd.read_file(linksPath)
#
#route = np.array(dijkstraPaths[6666][6])
##route = np.array(dijkstraPaths[6666][6])
#ax = zones.plot(figsize=(15,15),color='#b2b2b2')
#links.plot(ax=ax, color='k', linewidth=0.1)
#links.iloc[route,:].plot(ax=ax, color='r')
#plt.xlim(xLower,xUpper)
#plt.ylim(yLower,yUpper)

