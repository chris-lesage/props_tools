#!/usr/bin/env mayapy
# encoding: utf-8
"""
Rigmarole Vehicle Autorig
ie. "The Auto Autorigger"
author: Chris Lesage 2017-03.
email: chris@rigmarolestudio.com
A set of tools and scripts for generating a car rig.

This script creates a UI that creates various rig guides that get built into a final vehicle rig.
It can try to auto-generate guides based on the names of geometry,
but the rigger can manually select, add and remove geo from a guide.
"""

#TODO: Solve how to deal with the tires and entire car turning. Currently this only works in translateZ.
#TODO: Add options to set orientation of the vehicle. Currently this assumes the vehicle is pointing +Z
#TODO: Add a surface-following scheme. OR a tool that "solves" wheel rotation after animation has been done.

__version__ = '0.76'
import traceback

try:
    import PySide2.QtCore as QtCore
    import PySide2.QtGui as QtGui
    import PySide2.QtWidgets as QtWidgets
except ImportError:
    print("failed to import PySide2, {}".format(__file__))
    import PySide.QtCore as QtCore
    import PySide.QtGui as QtGui
    import PySide.QtWidgets as QtWidgets

try:
    # future proofing for Maya 2017.
    from shiboken2 import wrapInstance
except ImportError:
    from shiboken import wrapInstance

import pymel.core as pm
import pymel.core.datatypes as dt
import maya.cmds as cmds
import maya.OpenMaya as om
import maya.OpenMayaUI as omui

import props_icon_lib

import os
import math
#import envtools
#import json
from functools import wraps


##################################
###### PySide UI Functions #######
##################################


def undo(func):
    """Puts the wrapped `func` into a single Maya Undo action, then
    undoes it when the function enters the finally: block
    from schworer Github
    """
    @wraps(func) # by using wraps, the decorated function maintains its name and docstring.
    def _undofunc(*args, **kwargs):
        try:
            # start an undo chunk
            cmds.undoInfo(ock=True)
            return func(*args, **kwargs)
        finally:
            # after calling the func, end the undo chunk
            cmds.undoInfo(cck=True)
    return _undofunc


def maya_main_window():
    """Return the Maya main window widget as a Python object."""
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)


class CarRiggingTools(QtWidgets.QDialog):

    def __init__(self, parent=maya_main_window()):
        super(CarRiggingTools, self).__init__(parent)

    def create(self):
        """Create the UI"""
        self.setWindowTitle('Auto Autorigger v' + __version__)
        self.resize(460, 640)
        self.setWindowFlags(QtCore.Qt.Tool)
        self.create_data_structure()
        self.create_controls()
        self.create_layout()
        self.find_existing_guides()


    def create_data_structure(self):
        """Create the structure that contains the meta information and guide/geo information"""

        self.addButtonTypes = ['body', 'wheel', 'door', 'seat', 'steering', 'piston', 'jiggly']
        # the categorized list of all guides in the scene.
        self.oGidTable = { key: [] for key in self.addButtonTypes }
        # a name-key list of guides that contains info like the name, type and guide transform.
        self.oGidList = {}
        self.metaAttributes = [
                'gid_type',
                'gid_side',
                'gid_basename',
                'gid_front_side',
                'gid_ctrl_name',
                'gid_root',
                ]
        self.metaTableData = {}


    def create_controls(self):
        """Create the widgets and signals for the dialog"""

        cRed    = '745a54'
        cBlue   = '5d5d6a'
        cGreen  = '597a59'
        borderStyle = 'border:1px solid #3a3a3a'

        self.guideTable = QtWidgets.QTreeWidget()
        self.guideTable.setColumnCount(1)
        self.guideTable.setMaximumWidth(210)
        header = QtWidgets.QTreeWidgetItem(['Guide Name'])
        self.guideTable.setStyleSheet('max-width:240px; min-width:140px;')
        self.guideTable.setHeaderItem(header)
        self.guideTable.setItemsExpandable(True)
        self.guideTable.setExpandsOnDoubleClick(False)
        self.guideTable.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.guideTable.currentItemChanged.connect(self.on_table_changed)
        self.guideTable.itemClicked.connect(self.on_table_clicked)
        self.guideTable.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.guideTable.customContextMenuRequested[QtCore.QPoint].connect(self.on_table_rightclicked)
        
        self.metaTable = QtWidgets.QTreeWidget()

        #self.metaTable.setEditTriggers(self.metaTable.NoEditTriggers)
        # a function that filters for only column 1, so user doesn't edit column 0
        self.metaTable.itemDoubleClicked.connect(self.on_meta_table_edit)

        self.metaTable.setColumnCount(2)
        header = QtWidgets.QTreeWidgetItem(['Attribute Name', 'value'])
        self.metaTable.setHeaderItem(header)
        self.metaTable.setItemsExpandable(True)
        self.metaTable.currentItemChanged.connect(self.on_meta_table_changed)
        for eachMeta in self.metaAttributes:
            self.metaTableData[eachMeta] = QtWidgets.QTreeWidgetItem(self.metaTable, [eachMeta, ''])
            self.metaTableData[eachMeta].setTextAlignment(0, QtCore.Qt.AlignTop)

        self.geoList = QtWidgets.QListWidget()
        self.geoList.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        
        self.addButtons = {}
        for eachButton in self.addButtonTypes:
            self.addButtons[eachButton] = QtWidgets.QPushButton('Add {} Guide'.format(eachButton.title()))
            self.addButtons[eachButton].clicked.connect(self.addGuideBtn_pressed(eachButton))
            self.addButtons[eachButton].setStyleSheet(
                    '{}; padding:5px; max-width:100px;\
                    background-color: #{}; color: #eee;'.format(borderStyle, cBlue))

        self.addGeoBtn = QtWidgets.QPushButton('+')
        self.addGeoBtn.clicked.connect(self.addGeoBtn_pressed)
        self.addGeoBtn.setStyleSheet(
                '{}; padding:1px; max-width:15px; min-width:15px;\
                background-color: #{}; color: #eee;'.format(borderStyle, cBlue))

        self.removeGeoBtn = QtWidgets.QPushButton('-')
        self.removeGeoBtn.clicked.connect(self.removeGeoBtn_pressed)
        self.removeGeoBtn.setStyleSheet(
                '{}; padding:1px; max-width:15px; min-width:15px;\
                background-color: #{}; color: #eee;'.format(borderStyle, cRed))

        self.reloadGuideBtn = QtWidgets.QPushButton('Rebuild Guide')
        self.reloadGuideBtn.clicked.connect(self.reloadGuideBtn_pressed)
        self.reloadGuideBtn.setStyleSheet(
                '{}; padding:1px; text-align:center; color:#ddd'.format(borderStyle))

        self.removeGuideBtn = QtWidgets.QPushButton('Remove Guide')
        self.removeGuideBtn .clicked.connect(self.removeGuideBtn_pressed)
        self.removeGuideBtn .setStyleSheet(
                '{}; padding:5px; max-width:100px;\
                background-color: #{}; color: #eee;'.format(borderStyle, cRed))

        self.autoGuideBtn = QtWidgets.QPushButton('Automatically Detect Guides')
        self.autoGuideBtn.setFixedHeight(30)
        self.autoGuideBtn.clicked.connect(self.autoGuideBtn_pressed)

        self.refreshGuidesBtn = QtWidgets.QPushButton('Refresh Guide List')
        self.refreshGuidesBtn.setFixedHeight(30)
        self.refreshGuidesBtn.clicked.connect(self.refreshGuidesBtn_pressed)

        self.buildRigBtn = QtWidgets.QPushButton('Build Vehicle Rig')
        self.buildRigBtn.setFixedHeight(30)
        self.buildRigBtn.clicked.connect(self.buildRigBtn_pressed)
        self.buildRigBtn.setStyleSheet(
                '{}; padding:1px; background-color: #{}; color: #eee;'.format(borderStyle, cGreen))


    def create_layout(self):
        """Create the layouts and add widgets"""

        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.setContentsMargins(*[6]*4)

        flatStyle = True  # False draws a border around the whole section
        groupFont = QtGui.QFont('Helvetica Neue', 10, QtGui.QFont.Bold)
        labelFont=QtGui.QFont()
        #labelFont.setBold(True)
        groupPadding = 4  # padding at top and bottom of each section
        groupSpacing = 4  # the space between each section

        guideGroup = QtWidgets.QGroupBox('Vehicle Guides')
        guideGroup.setFlat(flatStyle)
        guideGroup.setFont(groupFont)

        guideLayout = QtWidgets.QVBoxLayout()
        guideLayout.setContentsMargins(*[2]*4)
        guideLayout.addSpacing(groupPadding)
        
        tableGroupLayout = QtWidgets.QHBoxLayout()
        tableGroupLayout.addWidget(self.guideTable)

        metaLayout = QtWidgets.QVBoxLayout()
        metaLayout.setAlignment(QtCore.Qt.AlignLeft)
        metaLayout.setAlignment(QtCore.Qt.AlignBottom)
        metaLayout.setContentsMargins(*[2]*4)
        metaLayout.addWidget(self.metaTable)

        geoRowLayout = QtWidgets.QHBoxLayout()
        geometryLabel = QtWidgets.QLabel('Geometry in Guide:')
        geoRowLayout.addWidget(geometryLabel)
        geoRowLayout.addWidget(self.addGeoBtn)
        geoRowLayout.addWidget(self.removeGeoBtn)
        geoRowLayout.addWidget(self.reloadGuideBtn)
        geometryLabel.setFont(labelFont)
        
        metaLayout.addLayout(geoRowLayout)
        metaLayout.addWidget(self.geoList)
        for eachButton in self.addButtonTypes:
            metaLayout.addWidget(self.addButtons[eachButton])
        metaLayout.addWidget(self.removeGuideBtn)
        tableGroupLayout.addLayout
        tableGroupLayout.addLayout(metaLayout)
        guideLayout.addLayout(tableGroupLayout)
        guideLayout.addSpacing(groupPadding)
        guideGroup.setLayout(guideLayout)

        buildGroup = QtWidgets.QGroupBox('Build')
        buildGroup.setFlat(flatStyle)
        buildGroup.setFont(groupFont)
        buildingOptionsLayout = QtWidgets.QHBoxLayout()
        buildingOptionsLayout.setContentsMargins(*[2]*4)

        buildingLayout = QtWidgets.QVBoxLayout()
        buildingLayout.setContentsMargins(*[2]*4)
        buildingLayout.addSpacing(groupPadding)
        buildingLayout.addSpacing(groupPadding)
        buttonRow = QtWidgets.QHBoxLayout()
        buttonRow.addWidget(self.autoGuideBtn)
        buttonRow.addWidget(self.refreshGuidesBtn)
        buttonRow.addWidget(self.buildRigBtn)
        buildingLayout.addLayout(buildingOptionsLayout)
        buildingLayout.addLayout(buttonRow)
        buildingLayout.addSpacing(groupPadding)
        buildGroup.setLayout(buildingLayout)

        mainLayout.addWidget(guideGroup)
        mainLayout.addWidget(buildGroup)
        mainLayout.addSpacing(groupSpacing)
        mainLayout.addStretch()

        self.setLayout(mainLayout)


    #--------------------------------------------------------------------------
    # SLOTS
    #--------------------------------------------------------------------------

    def update_guide_table(self):
        ### clear existing widget
        self.guideTable.clear()
        for gidType in self.oGidTable:
            if len(self.oGidTable[gidType]) > 0:
                newCategory = QtWidgets.QTreeWidgetItem(self.guideTable, [gidType])
                ### add the category
                for eachGid in self.oGidTable[gidType]:
                    ### add the gid
                    newItem = QtWidgets.QTreeWidgetItem(newCategory, [eachGid])
        self.guideTable.expandAll()
        if len(self.guideTable.selectedItems()) == 0:
            self.clear_meta_info()


    def find_existing_guides(self):
        """Searches for existing guides when the GUI first opens and adds them to the list."""

        # find any existing GIDs that already exist in the scene.
        gidColl = [x for x in pm.ls('*__gid__', type='transform') if pm.objExists(x.name() + '.gid_type')]

        gid = {}

        for gidType in self.addButtonTypes:
            gid[gidType] = [x for x in gidColl if x.gid_type.get() == gidType]
            for eachGid in gid[gidType]:
                if pm.objExists(eachGid.name() + '.gid_basename'):
                    if eachGid.gid_basename.get():
                        gidName = eachGid.gid_basename.get()
                    else: gidName = 'DEBUG BASENAME WAS BLANK'
                else:
                    gidName = 'DEBUG BASENAME ATTR MISSING'

                self.oGidList[gidName] = [gidName, gidType, eachGid]
                if not gidName in self.oGidTable[gidType]:
                    self.oGidTable[gidType].append(gidName)

        self.update_guide_table()


    def refresh_guide_data(self):
        # empty out the data and clear the gid table.
        self.oGidTable = { key: [] for key in self.addButtonTypes }
        self.oGidList = {}
        # and then build it back up.
        self.update_guide_table()
        self.find_existing_guides()


    def add_guide(self, geoType, geoFilter):
        """Takes geo selection, and adds that geo into a new rig guide of the type specified by that button."""
        self.refresh_guide_data()
        oGeoGroups = group_geometry_masses(geoFilter)
        guideCounter = 0
        sideKey = {'l': 'left_', 'r': 'right_', 'm': '', 'x': ''} # turn the side letter into a side word.
        for oGeo in oGeoGroups:
            # find the biggest geo by boundingBox volume. Use it to name the guide.
            sizeComp = [bb_volume(x) for x in oGeo]
            biggestGeo = oGeo[sizeComp.index(max(sizeComp))]
            #TODO: Check for name clashes first.
            # eg. l__front_seat__geo__ would become "left_front_seat"
            biggestBaseName = '{}'.format(biggestGeo)

            if biggestBaseName in self.oGidTable[geoType]:
                print('{} guide already exists'.format(geoType))
            else:
                guideCounter += 1
                eachGid = build_guide(geoType, biggestBaseName, oGeo)
                self.oGidList[biggestBaseName] = [biggestBaseName, geoType, eachGid]
                if not biggestBaseName in self.oGidTable[geoType]:
                    self.oGidTable[geoType].append(biggestBaseName)
        if guideCounter > 1:
            print('added {} {} guides.'.format(guideCounter, geoType))
        elif guideCounter == 1:
            print('added {} guide.'.format(geoType))


    def remove_guide(self, guide):
        category = guide.parent().text(0)
        item = self.oGidList[guide.text(0)][0]
        ### delete the data from the data model
        self.oGidTable[category].pop( self.oGidTable[category].index(item) )
        ### delete the guide's parent
        oGuide = self.oGidList[item][2].gid_root.outputs()[0]
        pm.delete(oGuide)


    def auto_add_guides(self):
        """Automatically searches the geometry in the scene and builds default sets of guides."""
        self.refresh_guide_data()
        geoTypes = {
            'body': '*_body_*_msh__',
            'wheel': ['*_tire_*_msh__', '*_wheel_*_msh__', '*_rims_*_msh__', '*_rim_*_msh__'],
            'door': '*_door_*_msh__',
            'seat': ['*_seat_*_msh__', '*_seats_*_msh__'],
            'steering': ['*_steering_*_msh__', '*_drive_wheel_*_msh__'],
        }
        rootNames = ['|root|x__base__grp__', '|root|x__model__grp__', 'x__model__grp__']
        for geoKey in geoTypes:
            geoFilter = [x for x in pm.ls(geoTypes[geoKey], type='transform') if x.getParent().name() in rootNames]
            if geoKey == 'wheel':
                # filter out steering wheels from the tire wheels.
                geoFilter = [x for x in geoFilter if not any([match in x.name() for match in ['steering', 'drive']])]
            self.add_guide(geoKey, geoFilter)
        self.refresh_guide_data()
        print('Vehicle guides successfully built.')


    def update_meta_info(self, oGeo):
        for i, eachMeta in enumerate(self.metaAttributes):
            try:
                mData = pm.PyNode(oGeo + '.' + eachMeta).get()
            except:
                mData = '-----'
            finally:
                self.metaTableData[eachMeta].setText(1, mData)
        listCount = self.geoList.count()
        for i in xrange(listCount):
            self.geoList.takeItem(listCount-1-i) # take in reverse to avoid index errors
        self.geoList.addItems([x for x in oGeo.gid_geo.get().split(',')])


    def clear_meta_info(self):
        for i, eachMeta in enumerate(self.metaAttributes):
            self.metaTableData[eachMeta].setText(1, '')


    def addGuideBtn_pressed(self, geoType):
        # def do() a tip from Mattias so I don't have to use lambda to pass
        # arguments to a button signal. But I don't know why it works.
        def do():
            sender = self.sender()
            # filter out 1: only the transforms who 2: have a mesh shape
            firstFilter = [x for x in pm.selected(type='transform') if x.getShape()]
            geoFilter = [x for x in firstFilter if type(x.getShape()) == pm.nodetypes.Mesh]
            self.add_guide(geoType, geoFilter)
            self.refresh_guide_data()
        return do


    def addGeoBtn_pressed(self):
        if len(self.guideTable.selectedItems()) > 0:
            if self.guideTable.currentItem().parent(): # filter out categories by checking for a parent
                currentGuide = self.guideTable.currentItem()
                guideName = currentGuide.text(0)
                oGuide = self.oGidList[guideName][2]
                guideGeo = oGuide.gid_geo.get().split(',')
                [guideGeo.pop(i) for i, x in enumerate(guideGeo) if x == ''] # filter out any blanks
                # Get selected geo. Filter for 1: only the transforms who 2: have a mesh shape
                firstFilter = [x for x in pm.selected(type='transform') if x.getShape()]
                geoFilter = [x for x in firstFilter if type(x.getShape()) == pm.nodetypes.Mesh]
                for eachGeo in geoFilter:
                    geoName = eachGeo.name()
                    # 1: check if the geo is in the list
                    if geoName not in guideGeo:
                        # 2: append the geo to the list
                        guideGeo.append(geoName)
                # 3: write the list to the metalist
                oGuide.gid_geo.set(','.join(guideGeo))
                # 4: refresh the geo table list
                self.update_meta_info(self.oGidList[guideName][2])
        else:
            print('No guide is selected.')


    def removeGeoBtn_pressed(self):
        if len(self.guideTable.selectedItems()) > 0:
            if self.guideTable.currentItem().parent(): # filter out categories by checking for a parent
                currentGuide = self.guideTable.currentItem()
                guideName = currentGuide.text(0)
                oGuide = self.oGidList[guideName][2]
                guideGeo = oGuide.gid_geo.get().split(',')
                [guideGeo.pop(i) for i, x in enumerate(guideGeo) if x == ''] # filter out any blanks
                for eachGeo in self.geoList.selectedItems():
                    geoName = eachGeo.text()
                    # 1: delete the geo from the metalist
                    if geoName in guideGeo:
                        guideGeo.pop(guideGeo.index(geoName))
                # 2: write the metalist back to the meta attribute
                oGuide.gid_geo.set(','.join(guideGeo))
                # 3: refresh the geo table list
                self.update_meta_info(self.oGidList[guideName][2])
        else:
            print('No guide is selected.')

    
    def reloadGuideBtn_pressed(self):
        selectedRows = [x for x in self.guideTable.selectedItems() if x.parent()]
        for each in selectedRows:
            # 1. Query the existing collection of geo
            curSel = each.text(0)
            category = each.parent().text(0)
            oGuide = self.oGidList[curSel][2]
            guideGeo = oGuide.gid_geo.get().split(',')
            ### TODO: 2. Check first for geo guide conflicts (geo in 2 guides, except body.)
            ### If a conflict, how do I solve that?
            ### 3. delete the existing guide
            self.remove_guide(each)
            ### 4. build the guide with the collection of geo
            self.add_guide(category, guideGeo)
            print 'reloading "{}" guide'.format(curSel)
        self.refresh_guide_data()
        if len(selectedRows) == 0:
            print('No guide is selected.')


    def removeGuideBtn_pressed(self):
        sender = self.sender()
        selectedRows = [x for x in self.guideTable.selectedItems() if x.parent()]
        selectedItems = [self.oGidList[x.text(0)] for x in selectedRows]
        for each in selectedRows:
            self.remove_guide(each)
        ### refresh the UI if that is needed
        self.refresh_guide_data()


    def autoGuideBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))

        self.refresh_guide_data()
        self.auto_add_guides()


    def refreshGuidesBtn_pressed(self):
        print('Refresh pressed')
        self.refresh_guide_data()


    def buildRigBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        build_rig()
        self.refresh_guide_data()


    def on_table_clicked(self, current):
        """When you left click on the guide list, it selects the main guide control"""
        self.on_table_changed(current, None)


    def on_table_changed(self, current, previous):
        """When you click or scrub on the guide list, it selects the main guide control"""
        if current:
            curSel = current.text(0)
        else:
            curSel = 'nothing'
            return False
        if current.parent():
            # if it has a parent, we know it isn't the top header items
            if self.oGidList[curSel][2]:
                pm.select(self.oGidList[curSel][2])
                self.update_meta_info(self.oGidList[curSel][2])
                pm.select([self.oGidList[x.text(0)][2] for x in self.guideTable.selectedItems() if x.parent()])
            else:
                # the rig guide no longer seems to exist. Refresh.
                self.refresh_guide_data()
        else:
            pass
            #TODO: If I need to do anything with headers (like select all children)
            #childrenList = [current.child(i) for i in xrange(current.childCount())]
            #for child in childrenList:
            #    print child
        if len(self.guideTable.selectedItems()) == 0:
            self.clear_meta_info()


    def on_table_rightclicked(self, current):
        """When you right click on the guide list, it selects all the geo found under .gid_geo"""
        curItem = self.guideTable.currentItem()
        if curItem:
            curSel = curItem.text(0)
            # if not curItem.parent() then this is a header item
            if curSel in self.oGidList and curItem.parent():
                metaGeo = self.oGidList[curSel][2].gid_geo.get()
                geoList = metaGeo.split(',')
                [geoList.pop(i) for i, x in enumerate(geoList) if x == ''] # filter out any blanks
                if geoList:
                    pm.select(geoList)
                else:
                    print('"{}" guide contains no geo.'.format(curSel))
            else:
                print('{} section right clicked'.format(curSel))


    def on_meta_table_changed(self, current, previous):
        if previous:
            prevSel = previous.text(0)
        else:
            prevSel = 'nothing'
        if current:
            curSel = current.text(0)
        else:
            curSel = 'nothing'


    def on_meta_table_edit(self, item, column):
        if column == 1:
            print 'ok'
            #item.setFlags(QtCore.Qt.ItemIsEditable)
            self.metaTable.editItem(item, column)


#################################
####### Rigging Functions #######
#################################

def find_closest_vert(geo, pos):
    if type(geo) is list:
        geoList = geo
    else:
        geoList = [geo]
    closestVerts = []
    for eachGeo in geoList:
        nodeDagPath = om.MObject()
        selectionList = om.MSelectionList()
        selectionList.add(eachGeo.name())
        nodeDagPath = om.MDagPath()
        selectionList.getDagPath(0, nodeDagPath)

        mfnMesh = om.MFnMesh(nodeDagPath)

        pointA = om.MPoint(pos[0], pos[1], pos[2])
        pointB = om.MPoint()
        space = om.MSpace.kWorld

        util = om.MScriptUtil()
        util.createFromInt(0)
        idPointer = util.asIntPtr()

        mfnMesh.getClosestPoint(pointA, pointB, space, idPointer)
        idx = om.MScriptUtil(idPointer).asInt()

        # getClosestPoint() finds a point on a face. Next find the closest vertex to that point.
        faceVerts = [eachGeo.vtx[i] for i in eachGeo.f[idx].getVertices()]
        # measure each from the original pos
        compareFaceVerts = [(pos - x.getPosition(space='world')).length() for x in faceVerts]
        # and get the index of the shortest one
        closestIndex = compareFaceVerts.index(min(compareFaceVerts))
        closestVerts.append(faceVerts[closestIndex])
        
    # Now we have the closest vertex for each geo. Find the closest out of those ones.
    compareVerts = [(pos - x.getPosition(space='world')).length() for x in closestVerts]
    # and get the index of the shortest one
    closestIndex = compareVerts.index(min(compareVerts))
    finalClosest = closestVerts[closestIndex]
    return (finalClosest, finalClosest.getPosition())


def add_a_keyable_attribute(myObj, oDataType, oParamName, oMin=None, oMax=None, oDefault=0.0):
    """Adds an attribute that shows up in the channel box; returns the newly created attribute."""
    oFullName = '.'.join( [str(myObj),oParamName] )
    if pm.objExists(oFullName):
        return pm.PyNode(oFullName)
    else:
        myObj.addAttr(oParamName, at=oDataType, keyable=True, dv=oDefault)
        myAttr = pm.PyNode(myObj + '.' + oParamName)
        if oMin != None:
            myAttr.setMin(oMin)
        if oMax != None:
            myAttr.setMax(oMax)
        pm.setAttr(myAttr, e=True, channelBox=True)
        pm.setAttr(myAttr, e=True, keyable=True)
        return myAttr


def add_meta_attribute(myObj, oParamName, oValue):
    """Adds a string attribute into "extra" attributes. Useful for meta information."""
    oFullName = '.'.join( [str(myObj),oParamName] )
    if pm.objExists(oFullName):
        pm.PyNode(str(oFullName)).set(oValue) # if it exists, just set the value
        return pm.PyNode(oFullName)
    else:
        myObj.addAttr(oParamName, dt='string')
        oParam = pm.PyNode(str(oFullName))
        oParam.set(oValue)
        return oParam


def lock_main_params(oNode, pLocked=False, pChannelBox=True, pKeyable=True, pParams=None):
    """oNode should be a transform or PyNode, or unique node name
    usage: Specify pParams=[".tx"] to only set translateX, otherwise it defaults to scale and visibility.
    pLocked, pChannelBox and pKeyable refer to the main channel box attributes.
    example: lock_main_params('locator1', pLocked=True, pParams=['.tx','.rz'])
    example: lock_main_params(pm.PyNode('locator1'), pLocked=False, pChannel=True)
    """
    if pParams == None:
        pParams = ['.tx','.ty','.tz','.rx','.ry','.rz','.sx','.sy','.sz','.v']
    if oNode:
        for param in pParams:
            try:
                pm.setAttr( pm.Attribute(oNode + param), keyable = pKeyable)
                pm.setAttr( pm.Attribute(oNode + param), channelBox = pChannelBox)
                pm.setAttr( pm.Attribute(oNode + param), lock = pLocked)
            except:
                print('{} lock failed on node: {}.'.format(param, oNode))
                continue


def create_rig_joint(jointName='unnamed_sjnt', radius=1.0):
    pm.select(None)
    oJoint = pm.joint(n=jointName, r=radius)
    pm.select(None)
    return oJoint


def skin_geometry(oJoints, oGeo, pName):
    """A simple skinCluster command with my preferred prefs."""
    pm.skinCluster(oJoints, oGeo,
            bindMethod=0, # closest distance
            dropoffRate=1.0,
            maximumInfluences=1,
            normalizeWeights=1, # interactive
            obeyMaxInfluences=False,
            skinMethod=0, # classic linear
            removeUnusedInfluence=0,
            weightDistribution=1, # neighbors
            name=pName,
        )


def find_group_bb(geoColl):
    """A function which returns some specific points from a combined bounding box
    specifically, the bottom of the BB in Y, the outside edges in X, and the center as a vector.
    I wrote this specifically for the wheel geometry. It might not be very useful as a generic function.
    """
    if geoColl:
        # find the Y value of the bottom of the tire
        bottomBB = min([x.getBoundingBox().min()[1] for x in geoColl])

        # find the center of the combined mass of the whole geometry group
        totalBox = dt.BoundingBox()
        [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl]
        [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl]
        bbCenter = totalBox.center()

        # find the inner and outer X value of the width of the tire
        edgesBB = [ totalBox.min()[0], totalBox.max()[0] ]
        if edgesBB[0] < 0.0:
            # reverse X if the wheel is on the left vs. the right side.
            edgesBBFlip = list(reversed(edgesBB))
            return [bottomBB, edgesBBFlip[0], edgesBBFlip[1], bbCenter, totalBox]

        # return [bottomY, innerX, outerX, centralMassCenter, complete BB]
        return [bottomBB, edgesBB[0], edgesBB[1], bbCenter, totalBox]
    else:
        # if no geometry is passed, return a "unit" BB.
        return [0.0, 0.0, 1.0, [1.0, 1.0, 0.0], dt.BoundingBox()]


def bb_volume(obj):
    oBB = obj.getBoundingBox()
    return oBB.width() * oBB.height() * oBB.depth()


def group_geometry_masses(geoColl):
    """Compares each geometry in a collection for bounding box intersection.
    If they ARE intersecting, they are grouped together. The groups are then returned.
    eg. A intersects with B. B intersects with A and C. C intersects with B.
    [ABC] is a single group. Even if A and C do not intersect.
    """
    oGeoColl = [pm.PyNode(x) for x in geoColl] # initialize as PyNodes.
    bbGroups = []
    smallBBs = []
    for i, each in enumerate(oGeoColl):
        # slightly shrink the boundingBox to avoid clumping doors which are modelled right beside each other.
        fullBB = each.getBoundingBox()
        smallBB = dt.BoundingBox()
        
        # next, I only want to scale the 2 longest sides. 2 doors beside each other should shrink.
        # But a handle that is sitting on the broad side of the door should not.
        fullScale = [fullBB.width(), fullBB.height(), fullBB.depth()]
        
        # get the shortest axis with an integer truth-table. example: [0, 0, 1] means Z is the shortest width
        shortTrue = [x == min(fullScale) for x in fullScale]
        # use the truth table as an index to choose whether to use the center or edge
        for axis in fullBB:
            comparisonPos = [
                [fullBB.center()[0], axis[0]][ shortTrue[0] ],
                [fullBB.center()[1], axis[1]][ shortTrue[1] ],
                [fullBB.center()[2], axis[2]][ shortTrue[2] ],
                ]
            # scale the BB relative to its center point.
            smallBB.expand(get_midpoint(axis, comparisonPos, 0.03)) # the smaller the number, the less the BB shrinks.
        smallBBs.append(smallBB)
        
    for i, each in enumerate(oGeoColl):
        group = [x for j, x in enumerate(oGeoColl) if smallBBs[i].intersects(smallBBs[j])]
        bbGroups.append(group)
    # iterate over each geo again. Gather each group that it belongs to in one joined group.
    for each in oGeoColl:
        # find the index of each group that contains this geo. Reverse the matches so I can pop them safely later.
        matchingGroups = list(reversed(sorted( [i for i, x in enumerate(bbGroups) if each in x] )))
        # Create a new list of the matching groups. This clumps all the matching groups together.
        newList = [bbGroups[i] for i in matchingGroups]
        # Cycle through the list of lists and then use set() to filter out duplicates.
        newListUnique = list(set( [item for subitem in newList for item in subitem] ))
        # Then pop those old groups out of bbGroups, leaving only the clumps.
        [bbGroups.pop(i) for i in matchingGroups]
        # The append the clumped group to bbGroups
        bbGroups.append(newListUnique)
    return bbGroups


def chain_parent(oColl):
    for oParent, oChild in zip(oColl[0:-1], oColl[1:]):
        try:
            pm.parent(oChild, None)
            pm.parent(oChild, oParent)
        except:
            continue


def pnt_ws(pnt):
    """Dumb function to help bring line width down."""
    return pnt.getPosition(space='world')


def get_midpoint(vecA, vecB, weight=0.5):
    """Helper to get middle point between two vectors. Weight is 0.0 to 1.0 blend between the two.
    So for example, 0.0 would return the position of oObject1. 1.0 would be oObject2. 0.5 is halfway.
    """
    try:
        vecA = dt.Vector(vecA) # just in case it isn't already cast as a vector
        vecB = dt.Vector(vecB)
        vecC = vecB-vecA
        vecD = vecC * weight # 0.5 is default which finds the mid-point.
        vecE = vecA + vecD
        return vecE

    except Exception, e:
        # TODO: include some useful error checking
        return False


# t = time
# b = beginning value
# c = change in value
# d = duration
def easeInSine(t, b, c, d):
    return -c * math.cos(t/d * (math.pi * 0.5)) + c + b;
def easeOutSine(t, b, c, d):
    return c * math.sin(t/d * (math.pi * 0.5)) + b;

# bx = beginning value for x (by for y)
# cx = CHANGE in value for x (cy for y)
# density = how many samples to take
def cEasing(bx, by, cx, cy, density=10, direction='up'):
    easeArray = []
    duration = 1.0 # (always want this to be 1.0 to be normalized)
    # a function that describes a quarter-arc type of fast-in, ease-out.
    for iter, i in enumerate(xrange(density+1)):
        timeFloat = i/float(density)
        if direction == 'down':
            inFloat = easeInSine(timeFloat, by, cy, duration)
            outFloat = easeOutSine(timeFloat, bx, cx, duration)
        elif direction == 'up':
            inFloat = easeOutSine(timeFloat, by, cy, duration)
            outFloat = easeInSine(timeFloat, bx, cx, duration)
        easeArray.append([outFloat, inFloat])
    return easeArray


#################################################
####### MAIN GUIDE BUILDING FUNCTIONS ###########
#################################################


def build_body_guide(section, basename, geoColl, guideParent):
    constraintParent = pm.PyNode('x__element__gid_driven__grp__')
    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    side = 'm'

    # find the biggest geo by boundingBox volume
    sizeComp = [bb_volume(x) for x in geoColl]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    scaleFactor = [1.25, 1.0, 1.05]
    controlScale = [totalBox.width() * scaleFactor[0], 1.0, totalBox.depth() * scaleFactor[2]]
    controlOffset = [0.0, 0.0, totalBox.center()[2]]

    # Store the components of names in a dictionary for readable formatting strings.
    nameStructure = {
        'side': side,
        'section': section,
        'front': '',
        'base': basename
        }

    oRigRoot = pm.group(em=True, n='{side}__{section}__{base}_gid_root__grp__'.format(**nameStructure))
    oRig = props_icon_lib.create_control_icon(
            'square',
            '{side}__{section}__{base}_main__gid__'.format(**nameStructure),
            controlScale,
            offset=controlOffset
            )

    ### PARTS ###
    oBody = props_icon_lib.create_control_icon(
            'square',
            '{side}__{section}__{base}_cog__gidloc__'.format(**nameStructure),
            controlScale
            )

    # connect a meta network which will be used in the build stage.
    oMeta = add_meta_attribute(oRig, 'gid_type', section)
    oMeta = add_meta_attribute(oRig, 'gid_side', 'm')
    oMeta = add_meta_attribute(oRig, 'gid_basename', basename)
    oMeta = add_meta_attribute(oRig, 'gid_front_side', 'mid')
    oMeta = add_meta_attribute(oRig, 'gid_ctrl_name', '{}__{}'.format(side, basename))
    oMetaRoot = add_meta_attribute(oRigRoot, 'gid_root', 'meta_' + oRigRoot.name().split('__')[2])
    oMetaRootSource = add_meta_attribute(oRig, 'gid_root', 'meta_' + oRigRoot.name().split('__')[2])
    oMetaGeo = add_meta_attribute(oRig, 'gid_geo', ','.join([str(x) for x in geoColl]))
    oMetaRootSource.connect(oMetaRoot)

    for oNode in [oBody]: # this is a list for if I add additional GID controls later
        metaName = 'meta_' + oNode.name().split('__')[2]
        metaAttrName = metaName.replace(basename, section)
        oMeta = add_meta_attribute(oNode, metaAttrName, metaAttrName)
        oMetaRig = add_meta_attribute(oRig, metaAttrName, metaAttrName)
        oMetaRig.connect(oMeta)

    pm.parent(oRigRoot, guideParent)
    pm.parent(oRig, oRigRoot)
    pm.parent(oBody, oRig)
    oBody.ty.set((totalBox.min()[1] + totalBox.center()[1]) * 0.5) # halfway between center and bottom
    oBody.tz.set(controlOffset[2])

    oRig.getShape().overrideEnabled.set(True)
    oRig.getShape().overrideColor.set(17)
    oBody.getShape().overrideEnabled.set(True)
    oBody.getShape().overrideColor.set(18)

    return oRig


def build_wheel_guide(section, basename, geoColl, guideParent, initRadius=1.0):
    """Creates a simple guide rig for placing a tire rig.
    Also chooses smart default positions based on the bounding box of the tire geo.
    """
    constraintParent = pm.PyNode('x__element__gid_driven__grp__')

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    if totalBox.center()[0] > 0.00:
        rigFlip = 1.0
        side = 'l'
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
        side = 'm'
    else:
        rigFlip = -1.0
        side = 'r'

    if totalBox.center()[2] > 0.05:
        frontOrBack = 'front'
    elif totalBox.center()[2] == 0.0:
        frontOrBack = 'mid'
    else:
        frontOrBack = 'back'

    # find the biggest geo by boundingBox volume
    sizeComp = [bb_volume(x) for x in geoColl]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    # Store the components of names in a dictionary for readable formatting strings.
    nameStructure = {
        'side': side,
        'section': section,
        'front': frontOrBack,
        'base': basename
        }

    #USER: Use the circle as an outer edge. Use oInner as an inner edge when placing the guides.
    oRigRoot = pm.group(n='{side}__{section}__{front}_gid_root__grp__'.format(**nameStructure), em=True)
    oRig = pm.circle(n='{side}__{section}__{front}_{base}_rig__gid__'.format(**nameStructure), nr=(1, 0, 0), ch=True)[0]
    pm.parent(oRigRoot, guideParent)
    pm.parent(oRig, oRigRoot)

    ### PARTS ###
    oBase = pm.spaceLocator(
            n='{side}__{section}__{front}_{base}_base__gidloc__'.format(**nameStructure)
            )
    oInner = pm.spaceLocator(
            n='{side}__{section}__{front}_{base}_inner__gidloc__'.format(**nameStructure)
            )
    oAltPivot = pm.spaceLocator(
            n='{side}__{section}__{front}_{base}_alternate_pivot__gidloc__'.format(**nameStructure)
            )
    oRadius = oRig.getShape().inputs()[0]

    partsColl = [oBase, oInner, oAltPivot]
    for eachLoc in partsColl:
        # scale the locators down
        eachLoc.localScale.set([0.2]*3)
    oBase.localScale.set([0.4]*3)

    # connect a meta network which will be used in the build stage.
    oMeta = add_meta_attribute(oRig, 'gid_type', section)
    oMeta = add_meta_attribute(oRig, 'gid_side', side)
    oMeta = add_meta_attribute(oRig, 'gid_basename', basename)
    oMeta = add_meta_attribute(oRig, 'gid_front_side', frontOrBack)
    oMeta = add_meta_attribute(oRig, 'gid_ctrl_name', '{side}__{front}_{base}'.format(**nameStructure))
    oMetaRoot = add_meta_attribute(
            oRigRoot, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaRootSource = add_meta_attribute(
            oRig, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaGeo = add_meta_attribute(oRig, 'gid_geo', ','.join([str(x) for x in geoColl]))
    oMetaRootSource.connect(oMetaRoot)
    for oNode in partsColl:
        metaName = 'meta_' + oNode.name().split('__')[2]
        metaAttrName = metaName.replace(basename, section).replace(frontOrBack + '_','')
        oMeta = add_meta_attribute(oNode, metaAttrName, metaAttrName)
        oMetaRig = add_meta_attribute(oRig, metaAttrName, metaAttrName)
        oMetaRig.connect(oMeta)

    pm.parent(oInner, oAltPivot, oRig)
    pm.parent(oBase, oRigRoot)
    pm.parent(oInner, oBase)

    # set initial connections and positions
    wheelBB = find_group_bb(geoColl)

    oRig.getShape().overrideEnabled.set(1)
    #oRig.getShape().lineWidth.set(2)
    oBase.getShape().overrideEnabled.set(1)
    oInner.getShape().overrideEnabled.set(1)
    oAltPivot.getShape().overrideEnabled.set(1)

    if wheelBB[1] < 0.0:
        rigFlip = -1.0
        oRig.getShape().overrideColor.set(20)
        oBase.getShape().overrideColor.set(13)
        oInner.getShape().overrideColor.set(13)
        oAltPivot.getShape().overrideColor.set(13)
    else:
        rigFlip = 1.0
        oRig.getShape().overrideColor.set(18)
        oBase.getShape().overrideColor.set(6)
        oInner.getShape().overrideColor.set(6)
        oAltPivot.getShape().overrideColor.set(6)

    oRig.ty.set(initRadius)
    oBase.ty.set(0)
    oRig.tx.connect(oBase.tx)
    oRig.tz.connect(oBase.tz)
    oInner.tx.set(initRadius * rigFlip * -0.25)
    oInner.ty.lock()
    oInner.tz.lock()

    vRadius = pm.createNode('plusMinusAverage',
            n='{side}__{section}__{front}_{base}_radius_vector__add__'.format(**nameStructure)
            )
    vRadius.operation.set(2) # subtract
    oRig.ty.connect(vRadius.input2D[0].input2Dx)
    oBase.ty.connect(vRadius.input2D[1].input2Dx)
    vRadius.output2D.output2Dx.connect(oRadius.radius)

    # if geometry is passed, try to set the guide to match
    centerOut = [wheelBB[2], wheelBB[3][1], wheelBB[3][2]]
    centerIn = [wheelBB[1], wheelBB[3][1], wheelBB[3][2]]
    bottomOut = [wheelBB[2], wheelBB[0], wheelBB[3][2]]
    oRig.setTranslation(centerOut, space='world')
    oInner.setTranslation(centerIn, space='world')
    oBase.setTranslation(bottomOut, space='world') # only Y will be set
    oAltPivot.setTranslation(wheelBB[3], space='world') #TODO: wheelBB is dumb. Refactor into readable BB data.
    oAltPivot.getShape().localScale.set([2.0, 1.0, 1.0])

    return oRig


def build_door_guide(section, basename, geoColl, guideParent):
    """Build a door guide. Use the first geo in geoColl as the main door.
    The follow geo will be accessories, windows, mirrors, etc.
    """
    constraintParent = pm.PyNode('x__element__gid_driven__grp__')

    totalBox = geoColl[0].getBoundingBox()
    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
        side = 'l'
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
        side = 'm'
    else:
        rigFlip = -1.0
        side = 'r'

    if totalBox.center()[2] > 0.0:
        frontOrBack = 'front'
        rigFront = 1.0
    elif totalBox.center()[2] == 0.0:
        frontOrBack = 'mid'
        rigFront = -1.0
    else:
        frontOrBack = 'back'
        rigFront = -1.0

    # find the biggest geo by boundingBox volume
    sizeComp = [bb_volume(x) for x in geoColl]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    # Store the components of names in a dictionary for readable formatting strings.
    nameStructure = {
        'side': side,
        'section': section,
        'front': frontOrBack,
        'base': basename
        }

    oRigRoot = pm.group(
            n='{side}__{section}__{front}_{base}_gid_root__grp__'.format(**nameStructure),
            em=True
            )
    oRig = pm.spaceLocator(
            n='{side}__{section}__{front}_{base}_hinge__gid__'.format(**nameStructure)
            )

    pm.parent(oRigRoot, guideParent)
    pm.parent(oRig, oRigRoot)

    # connect a meta network which will be used in the build stage.
    oMeta = add_meta_attribute(oRig, 'gid_type', section)
    oMeta = add_meta_attribute(oRig, 'gid_side', side)
    oMeta = add_meta_attribute(oRig, 'gid_basename', basename)
    oMeta = add_meta_attribute(oRig, 'gid_front_side', frontOrBack)
    oMeta = add_meta_attribute(oRig, 'gid_ctrl_name', '{side}__{front}_{base}'.format(**nameStructure))
    oMetaRoot = add_meta_attribute(
            oRigRoot, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaRootSource = add_meta_attribute(
            oRig, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaGeo = add_meta_attribute(oRig, 'gid_geo', ','.join([str(x) for x in geoColl]))
    oMetaRootSource.connect(oMetaRoot)
    for oNode in []:
        metaName = 'meta_' + oNode.name().split('__')[2]
        metaAttrName = metaName.replace(basename, section).replace(frontOrBack + '_','')
        oMeta = add_meta_attribute(oNode, metaAttrName, metaAttrName)
        oMetaRig = add_meta_attribute(oRig, metaAttrName, metaAttrName)
        oMetaRig.connect(oMeta)

    # place a locator in front of and outside of the door. This will find the nearest point for the hinge.
    if totalBox.depth() > totalBox.width():
        # the door is likely on the side of the vehicle
        if rigFlip == 1.0:
            closestPos = [totalBox.max()[0] + (0.1 * rigFlip), totalBox.center()[1], totalBox.max()[2] + 8.0]
        else:
            closestPos = [totalBox.min()[0] + (0.1 * rigFlip), totalBox.center()[1], totalBox.max()[2] + 8.0]
    else:
        # the door is likely on the back of the car. Get the closest point off the outside edge instead of the front.
        if rigFront >= 0.0:
            zPos = totalBox.max()[2]
        else:
            zPos = totalBox.min()[2]
        if rigFlip == 1.0:
            closestPos = [totalBox.max()[0] + (8.0 * rigFlip), totalBox.center()[1], zPos + (1.0 * rigFront)]
        else:
            closestPos = [totalBox.min()[0] + (8.0 * rigFlip), totalBox.center()[1], zPos + (1.0 * rigFront)]
    _, hingePos = find_closest_vert(geoColl, dt.Vector(closestPos))
    oRig.setTranslation(hingePos, space='world')
    if side == 'l':
        oRig.rx.set(180)

    if rigFlip == 1.0:
        oRig.getShape().overrideEnabled.set(True)
        oRig.getShape().overrideColor.set(18)
    else:
        oRig.getShape().overrideEnabled.set(True)
        oRig.getShape().overrideColor.set(20)

    return oRig


def build_steering_guide(section, basename, geoColl, guideParent):
    constraintParent = pm.PyNode('x__element__gid_driven__grp__')

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    pos = [totalBox.center()[0], totalBox.max()[1], totalBox.min()[2]]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
        side = 'l'
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
        side = 'm'
    else:
        rigFlip = -1.0
        side = 'r'

    # find the biggest geo by boundingBox volume
    sizeComp = [bb_volume(x) for x in geoColl]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    # Store the components of names in a dictionary for readable formatting strings.
    nameStructure = {
        'side': side,
        'section': section,
        'front': '',
        'base': basename
        }

    oRigRoot = pm.group(em=True, n='{side}__{section}__{base}_gid_root__grp__'.format(**nameStructure))
    oRig = pm.circle(
            n='{side}__{section}__{base}__gid__'.format(**nameStructure),
            nr=(0, 0, 1), sections=12, ch=True)[0]

    ### PARTS ###
    oSteeringBase = pm.spaceLocator(n='{side}__{section}__{base}_base__gidloc__'.format(**nameStructure))
    oSteeringWidth = pm.spaceLocator(n='{side}__{section}__{base}_width__gidloc__'.format(**nameStructure))

    # connect a meta network which will be used in the build stage.
    oMeta = add_meta_attribute(oRig, 'gid_type', section)
    oMeta = add_meta_attribute(oRig, 'gid_side', 'm') # default to middle, even if the steering wheel is on one side.
    oMeta = add_meta_attribute(oRig, 'gid_basename', basename)
    oMeta = add_meta_attribute(oRig, 'gid_front_side', 'mid')
    oMeta = add_meta_attribute(oRig, 'gid_ctrl_name', '{side}__{base}'.format(**nameStructure))
    oMetaRoot = add_meta_attribute(oRigRoot, 'gid_root', 'meta_' + oRigRoot.name().split('__')[2])
    oMetaRootSource = add_meta_attribute(oRig, 'gid_root', 'meta_' + oRigRoot.name().split('__')[2])
    oMetaGeo = add_meta_attribute(oRig, 'gid_geo', ','.join([str(x) for x in geoColl]))
    oMetaRootSource.connect(oMetaRoot)

    for oNode in [oSteeringBase, oSteeringWidth]:
        metaName = 'meta_' + oNode.name().split('__')[2]
        metaAttrName = metaName.replace(basename, section)
        oMeta = add_meta_attribute(oNode, metaAttrName, metaAttrName)
        oMetaRig = add_meta_attribute(oRig, metaAttrName, metaAttrName)
        oMetaRig.connect(oMeta)

    oSteeringBase.getShape().overrideEnabled.set(True)
    oSteeringWidth.getShape().overrideEnabled.set(True)
    oRig.getShape().overrideEnabled.set(True)
    oSteeringBase.getShape().overrideColor.set(17)
    oSteeringWidth.getShape().overrideColor.set(17)
    oRig.getShape().overrideColor.set(17)
    oSteeringBase.localScale.set([0.2, 0.2, 0.2])
    oSteeringWidth.localScale.set([0.2, 0.2, 0.2])

    # sample above and below the steering wheel to find the angle of the steering column.
    # This will likely fail except in circular steering wheels.
    closestPos = [pos[0], pos[1] + 4.0, pos[2]]
    _, topSteeringPos = find_closest_vert(geoColl, dt.Vector(closestPos))
    closestPos = [pos[0], totalBox.min()[1], pos[2] - 4.0]
    _, bottomSteeringPos = find_closest_vert(geoColl, dt.Vector(closestPos))

    midSteeringPos = (topSteeringPos + bottomSteeringPos) * 0.5
    # find a vector perpindicular to the steering wheel to find the position down the steering column geo.
    findCross = (bottomSteeringPos - (bottomSteeringPos[0]-1.0, bottomSteeringPos[1], bottomSteeringPos[2]))
    crossVector = findCross.normal() * (bottomSteeringPos-topSteeringPos).length()
    crossPos = midSteeringPos + (bottomSteeringPos - topSteeringPos).cross(crossVector)
    # sample slightly above and below the bottom column, to try and find the center position
    _, columnPosTop = find_closest_vert(geoColl, dt.Vector(crossPos + dt.Vector(0.0, 0.5, 0.0)))
    _, columnPosBottom = find_closest_vert(geoColl, dt.Vector(crossPos + dt.Vector(0.0, -0.5, 0.0)))
    # columnPos is the bottom of the steering column
    columnPos = (columnPosTop + columnPosBottom) * 0.5

    # Project back UP the steering column, and project back to the steering wheel vectors.
    # We do this because the steering wheel and steering column don't necessarily line up in center.
    # centerPos is the top of the steering column. The pivot where the wheel will turn.
    centerPos = topSteeringPos + (columnPos-topSteeringPos).projectionOnto(bottomSteeringPos-topSteeringPos)

    # Set the positions
    oRigRoot.setTranslation(centerPos, space='world')
    oSteeringBase.setTranslation(columnPos, space='world')
    #TODO: totalBox.min() vs max() will depend on orientation of car.
    oSteeringWidth.setTranslation([totalBox.min()[0], centerPos[1], centerPos[2]], space='world')
    oRig.setTranslation(centerPos, space='world')

    pm.parent(oSteeringWidth, oRig)
    pm.parent(oRigRoot, guideParent)
    pm.parent(oRig, oSteeringBase, oRigRoot)

    # Make the steering base an aim constraint for the wheel guide
    pm.aimConstraint(oSteeringBase, oRig, mo=False, aim=[0,0,1], u=[0,1,0],
            n='{side}__{section}__guide__aimconstraint__'.format(**nameStructure)
            )
    oRig.r.lock()
    oSteeringWidth.ty.lock()
    oSteeringWidth.tz.lock()

    # Set the radius of the circle based on the width of the oSteeringWidth
    metaRadius = oRig.getShape().inputs()[0] # the radius value of the circle in the guide
    oSteeringWidth.tx.connect(metaRadius.radius)

    return oRig


def build_seat_guide(section, basename, geoColl, guideParent):
    constraintParent = pm.PyNode('x__element__gid_driven__grp__')

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
        side = 'l'
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
        side = 'm'
    else:
        rigFlip = -1.0
        side = 'r'

    if totalBox.center()[2] > 0.05:
        frontOrBack = 'front'
    elif totalBox.center()[2] == 0.0:
        frontOrBack = 'mid'
    else:
        frontOrBack = 'back'

    # find the biggest geo by boundingBox volume
    sizeComp = [bb_volume(x) for x in geoColl]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    scaleFactor = [1.0, 1.0, 1.0]

    # Store the components of names in a dictionary for readable formatting strings.
    nameStructure = {
        'side': side,
        'section': section,
        'front': frontOrBack,
        'base': basename
        }

    oRigRoot = pm.group(
            em=True,
            n='{side}__{section}__{front}_{base}_gid_root__grp__'.format(**nameStructure)
            )
    oRig = props_icon_lib.create_control_icon(
            'square',
            '{side}__{section}__{front}_{base}__gid__'.format(**nameStructure),
            [totalBox.width() + scaleFactor[0], 1.0, totalBox.depth() + scaleFactor[2]]
            )

    ### PARTS ###
    scaleFactor = [1.0, 1.0, -0.4]
    oSeatBack = props_icon_lib.create_control_icon(
            'square',
            '{side}__{section}__{front}_{base}_rear_pivot__gidloc__'.format(**nameStructure),
            [totalBox.width() + scaleFactor[0], 1.0, totalBox.depth() + scaleFactor[2]]
            )

    # connect a meta network which will be used in the build stage.
    oMeta = add_meta_attribute(oRig, 'gid_type', section)
    oMeta = add_meta_attribute(oRig, 'gid_side', side)
    oMeta = add_meta_attribute(oRig, 'gid_basename', basename)
    oMeta = add_meta_attribute(oRig, 'gid_front_side', frontOrBack)
    oMeta = add_meta_attribute(oRig, 'gid_ctrl_name', '{side}__{front}_{base}'.format(**nameStructure))
    oMetaRoot = add_meta_attribute(
            oRigRoot, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaRootSource = add_meta_attribute(
            oRig, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaGeo = add_meta_attribute(oRig, 'gid_geo', ','.join([str(x) for x in geoColl]))
    oMetaRootSource.connect(oMetaRoot)

    for oNode in [oSeatBack]:
        metaName = 'meta_' + oNode.name().split('__')[2].replace('{front}_{base}_'.format(**nameStructure),'')
        metaAttrName = metaName.replace(basename, section)
        oMeta = add_meta_attribute(oNode, metaAttrName, metaAttrName)
        oMetaRig = add_meta_attribute(oRig, metaAttrName, metaAttrName)
        oMetaRig.connect(oMeta)

    pm.parent(oRigRoot, guideParent)
    pm.parent(oRig, oSeatBack, oRigRoot)

    pos = totalBox.center()

    # set a point in FRONT of the seat, to attempt to find the front edge of the seat.
    closestPos = [pos[0], pos[1] + 1.0, totalBox.max()[2] + 4.0]
    _, seatEdgePos = find_closest_vert(geoColl, dt.Vector(closestPos))
    # set a point ABOVE the seat, to attempt to find the top edge of the seat.
    closestPos = [pos[0], pos[1] + 8.0, pos[2] + 2.0]
    _, seatTopPos = find_closest_vert(geoColl, dt.Vector(closestPos))

    oRigRoot.setTranslation([pos[0], seatEdgePos[1], pos[2]], space='world')
    oSeatBack.setTranslation([pos[0], seatEdgePos[1] + 0.2, seatTopPos[2]], space='world')

    if rigFlip == 1.0:
        oRig.getShape().overrideEnabled.set(True)
        oSeatBack.getShape().overrideEnabled.set(True)
        oRig.getShape().overrideColor.set(6)
        oSeatBack.getShape().overrideColor.set(18)
    else:
        oRig.getShape().overrideEnabled.set(True)
        oSeatBack.getShape().overrideEnabled.set(True)
        oRig.getShape().overrideColor.set(13)
        oSeatBack.getShape().overrideColor.set(20)

    return oRig


def build_piston_guide(section, basename, geoColl, guideParent):
    """Build guide for a piston mechanic."""
    constraintParent = pm.PyNode('x__element__gid_driven__grp__')

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
        side = 'l'
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
        side = 'm'
    else:
        rigFlip = -1.0
        side = 'r'

    if totalBox.center()[2] > 0.05:
        frontOrBack = 'front'
    elif totalBox.center()[2] == 0.0:
        frontOrBack = 'mid'
    else:
        frontOrBack = 'back'

    controlScale = dt.BoundingBox()
    controlScale.expand(totalBox.min() * 1.08)
    controlScale.expand(totalBox.max() * 1.08)

    # find the biggest geo by boundingBox volume
    sizeComp = [bb_volume(x) for x in geoColl]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    # Store the components of names in a dictionary for readable formatting strings.
    nameStructure = {
        'side': side,
        'section': section,
        'front': frontOrBack,
        'base': basename
        }

    oRigRoot = pm.group(n='{side}__{section}__{base}_gid_root__grp__'.format(**nameStructure), em=True)
    oRig = props_icon_lib.create_control_icon(
            'square', '{side}__{section}__{base}_top_piston__gid__'.format(**nameStructure),
            [controlScale.width(), controlScale.height(), controlScale.depth()]
            )
    oBottomPiston = pm.spaceLocator(n='{side}__{section}__{base}_bottom_piston__gid__'.format(**nameStructure))

    boxTop = [ totalBox.center()[0], totalBox.max()[1], totalBox.max()[2] ]
    boxBottom = [ totalBox.center()[0], totalBox.min()[1], totalBox.min()[2] ]
    
    oRigRoot.setTranslation([0.0, totalBox.center()[1], totalBox.center()[2]], space='world')
    oRig.setTranslation(boxTop, space='world')
    oBottomPiston.setTranslation(boxBottom, space='world')

    chain_parent([guideParent, oRigRoot, oRig])
    chain_parent([guideParent, oRigRoot, oBottomPiston])

    pm.aimConstraint(oBottomPiston, oRig, mo=False, aim=[0,1,0], u=[0,0,1],
            n='{side}__{section}__top_piston__aimconstraint__'.format(**nameStructure)
            )

    # connect a meta network which will be used in the build stage.
    oMeta = add_meta_attribute(oRig, 'gid_type', section)
    oMeta = add_meta_attribute(oRig, 'gid_side', side)
    oMeta = add_meta_attribute(oRig, 'gid_basename', basename)
    oMeta = add_meta_attribute(oRig, 'gid_front_side', frontOrBack)
    oMeta = add_meta_attribute(oRig, 'gid_ctrl_name', '{side}__{front}_{base}'.format(side, frontOrBack, basename))
    oMetaRoot = add_meta_attribute(
            oRigRoot, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaRootSource = add_meta_attribute(
            oRig, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaGeo = add_meta_attribute(oRig, 'gid_geo', ','.join([str(x) for x in geoColl]))
    oMetaRootSource.connect(oMetaRoot)
    oMetaPivotRig = add_meta_attribute(oRig, 'meta_piston_pivot', 'meta_piston_pivot')
    oMetaPivot = add_meta_attribute(oBottomPiston, 'meta_piston_pivot', 'meta_piston_pivot')
    oMetaPivotRig.connect(oMetaPivot)
    for oNode in []:
        metaName = 'meta_' + oNode.name().split('__')[2]
        metaAttrName = metaName.replace(basename, section).replace(frontOrBack + '_','')
        oMeta = add_meta_attribute(oNode, metaAttrName, metaAttrName)
        oMetaRig = add_meta_attribute(oRig, metaAttrName, metaAttrName)
        oMetaRig.connect(oMeta)

    oRig.getShape().overrideEnabled.set(True)
    if rigFlip == 1.0:
        oRig.getShape().overrideColor.set(18)
        oBottomPiston.getShape().overrideColor.set(18)
    else:
        oRig.getShape().overrideColor.set(20)
        oBottomPiston.getShape().overrideColor.set(20)

    return oRig



def build_jiggly_bits_guide(section, basename, geoColl, guideParent):
    """Build guides for all the extra bits, like mirrors, stick-shift,
    bumpers, or whatever needs to have a basic transform.
    """
    constraintParent = pm.PyNode('x__element__gid_driven__grp__')

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
        side = 'l'
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
        side = 'm'
    else:
        rigFlip = -1.0
        side = 'r'

    if totalBox.center()[2] > 0.05:
        frontOrBack = 'front'
    elif totalBox.center()[2] == 0.0:
        frontOrBack = 'mid'
    else:
        frontOrBack = 'back'

    controlScale = dt.BoundingBox()
    controlScale.expand(totalBox.min() * 1.08)
    controlScale.expand(totalBox.max() * 1.08)

    # find the biggest geo by boundingBox volume
    sizeComp = [bb_volume(x) for x in geoColl]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    # Store the components of names in a dictionary for readable formatting strings.
    nameStructure = {
        'side': side,
        'section': section,
        'front': frontOrBack,
        'base': basename
        }

    oRigRoot = pm.group(n='{side}__{section}__{base}_gid_root__grp__'.format(**nameStructure), em=True)
    oRig = props_icon_lib.create_control_icon(
            'box', '{side}__{section}__{base}_main__gid__'.format(**nameStructure),
            [controlScale.width(), controlScale.height(), controlScale.depth()]
            )
    oPivot = pm.spaceLocator(n='{side}__{section}__jiggle_pivot__gid__'.format(**nameStructure))

    oRigRoot.setTranslation(totalBox.center(), space='world')
    oRig.setTranslation(totalBox.center(), space='world')
    oPivot.setTranslation(totalBox.center(), space='world')

    chain_parent([guideParent, oRigRoot, oRig, oPivot])

    # connect a meta network which will be used in the build stage.
    oMeta = add_meta_attribute(oRig, 'gid_type', section)
    oMeta = add_meta_attribute(oRig, 'gid_side', side)
    oMeta = add_meta_attribute(oRig, 'gid_basename', basename)
    oMeta = add_meta_attribute(oRig, 'gid_front_side', frontOrBack)
    oMeta = add_meta_attribute(oRig, 'gid_ctrl_name', '{side}__{front}_{base}'.format(**nameStructure))
    oMetaRoot = add_meta_attribute(
            oRigRoot, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaRootSource = add_meta_attribute(oRig, 'gid_root',
            'meta_' + oRigRoot.name().split('__')[2].replace(frontOrBack + '_','')
            )
    oMetaGeo = add_meta_attribute(oRig, 'gid_geo', ','.join([str(x) for x in geoColl]))
    oMetaRootSource.connect(oMetaRoot)
    oMetaPivotRig = add_meta_attribute(oRig, 'meta_jiggle_pivot', 'meta_jiggle_pivot')
    oMetaPivot = add_meta_attribute(oPivot, 'meta_jiggle_pivot', 'meta_jiggle_pivot')
    oMetaPivotRig.connect(oMetaPivot)
    for oNode in []:
        metaName = 'meta_' + oNode.name().split('__')[2]
        metaAttrName = metaName.replace(basename, section).replace(frontOrBack + '_','')
        oMeta = add_meta_attribute(oNode, metaAttrName, metaAttrName)
        oMetaRig = add_meta_attribute(oRig, metaAttrName, metaAttrName)
        oMetaRig.connect(oMeta)

    oRig.getShape().overrideEnabled.set(True)
    if rigFlip == 1.0:
        oRig.getShape().overrideColor.set(18)
    else:
        oRig.getShape().overrideColor.set(20)

    return oRig


@undo
def build_guide(section, basename, geoColl):

    oGuide = None

    guideParentName = 'x__element__main_guide_group__grp__'
    if not pm.objExists(guideParentName):
        guideParent = pm.group(em=True, n=guideParentName)
    else:
        guideParent = pm.PyNode(guideParentName)

    constraintParentName = 'x__element__gid_driven__grp__'
    if not pm.objExists(constraintParentName):
        constraintParent = pm.group(em=True, n=constraintParentName)
    else:
        constraintParent = pm.PyNode(constraintParentName)
    pm.parent(constraintParent, guideParent)

    # BODY
    if section == 'body':
        meshParent = pm.PyNode('|root|x__model__grp__')
        allCarGeo = list(set([mesh.getParent() for mesh in meshParent.getChildren(ad=True, type='mesh')]))
        oGuide = build_body_guide(section, basename, allCarGeo, guideParent)

    # WHEELS
    if section == 'wheel':
        oGuide = build_wheel_guide(section, basename, geoColl, guideParent, initRadius=1.5)

    # DOORS
    if section == 'door':
        oGuide = build_door_guide(section, basename, geoColl, guideParent)

    # STEERING WHEELS
    if section == 'steering':
        oGuide = build_steering_guide(section, basename, geoColl, guideParent)

    # SEAT
    if section == 'seat':
        oGuide = build_seat_guide(section, basename, geoColl, guideParent)

    if section == 'piston':
        oGuide = build_piston_guide(section, basename, geoColl, guideParent)

    # JIGGLY
    if section == 'jiggly':
        oGuide = build_jiggly_bits_guide(section, basename, geoColl, guideParent)


    return oGuide


#################################################
###### MAIN CAR BUILDING FUNCTION ###############
#################################################


def build_body_rig(section, rigGuide, wheelGuides):
    # init the parts of the rig guide
    metaGuideRoot = pm.PyNode(rigGuide.name() + '.' + 'gid_root').outputs()[0]
    metaCarCog = pm.PyNode(rigGuide.name() + '.' + 'meta_body_cog').outputs()[0]
    constraintParent = pm.PyNode('x__constraints__grp__')

    # group the wheels into their pairs, left and right and front and back. (DEBUG this on motorcycles.)
    leftWheelGuides =  [gid for gid in wheelGuides if gid.gid_side.get() in ['l', 'm']] # mid goes to left side.
    rightWheelGuides = [gid for gid in wheelGuides if gid.gid_side.get() in ['r']]
    frontWheelGuides = [gid for gid in wheelGuides if gid.gid_front_side.get() in ['front', 'mid']] # mid goes to front.
    rearWheelGuides =  [gid for gid in wheelGuides if gid.gid_front_side.get() in ['back']]

    geoColl = rigGuide.gid_geo.get().split(',')
    [geoColl.pop(i) for i, x in enumerate(geoColl) if x == ''] # filter out any blanks
    geoColl = [pm.PyNode(x) for x in geoColl]

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    side = rigGuide.gid_side.get()
    basename = rigGuide.gid_basename.get()
    ctrlName = rigGuide.gid_ctrl_name.get()
    ctrlPos = metaCarCog.getTranslation(space='world')

    # Store the components of names in a dictionary for readable formatting strings.
    nameStructure = {
        'side': side,
        'section': section,
        'front': '',
        'base': basename
        }

    # a bunch of if statements. If wheel guides aren't found, use bounding box for control positions instead.
    #TODO: When there are no wheels, use closest point instead of BB,
        # because if mirrors are sticking out the sides, it will affect the min() of the BB.
    if rightWheelGuides:
        rightWheelPos = [x.meta_wheel_base.outputs()[0].getTranslation(space='world') for x in rightWheelGuides]
        rightTiltPos = [min([x[0] for x in rightWheelPos]), 0.0, 0.0]
    else:
        rightTiltPos = [totalBox.min()[0], totalBox.min()[1], 0.0]
    
    if leftWheelGuides:
        leftWheelPos = [x.meta_wheel_base.outputs()[0].getTranslation(space='world') for x in leftWheelGuides]
        leftTiltPos = [max([x[0] for x in leftWheelPos]), 0.0, 0.0]
    else:
        leftTiltPos = [totalBox.max()[0], totalBox.min()[1], 0.0]
    
    if frontWheelGuides:
        # wheelTurnPos is between the wheels at the ground
        # frontTiltPos is between the wheels at X = 0
        numOfWheels = float(len(frontWheelGuides))
        wheelTurnPos = sum( [x.getTranslation(space='world') for x in frontWheelGuides] ) / numOfWheels
        frontTiltPos = [0.0, wheelTurnPos[1], wheelTurnPos[2]]
        wheelTurnPos[0] = 0.0 # X position
        wheelTurnPos[1] = 0.0 # Y position
    else:
        # if there are no wheel guides, get the front of the body's bounding box.
        wheelTurnPos = [totalBox.center()[0], totalBox.min()[1], totalBox.max()[2]]
        frontTiltPos = [0.0, wheelTurnPos[1], wheelTurnPos[2]]

    if rearWheelGuides:
        # between the wheels at the ground
        numOfWheels = float(len(rearWheelGuides))
        rearTiltPos = sum( [x.getTranslation(space='world') for x in rearWheelGuides] ) / numOfWheels
        rearTiltPos[0] = 0.0
    else:
        rearTiltPos = [0.0, totalBox.min()[1], totalBox.min()[2]]
    
    if wheelGuides:
        numOfWheels = float(len(wheelGuides))
        wheelAveragePos = sum( [x.getTranslation(space='world') for x in wheelGuides] ) / numOfWheels
    else:
        wheelAveragePos = totalBox.center()
    wheeliePos = [0.0, totalBox.max()[1] + 1.0, wheelAveragePos[2]]

    # each parent of the geometry. Bug test in case geometry is ever parented under other geo.
    geoCollParents = list(set([x.getParent() for x in geoColl]))

    ##### BUILD THE BASIC GUIDE CONTROLS #####
    #TODO: DEBUG THIS. This used to build ON style controls
    auto1 = pm.group(empty=True, n='m__element__position__ctrl__')
    auto2 = pm.group(empty=True, n='m__element__trajectory__ctrl__')
    auto3 = pm.group(empty=True, n='m__element__root__ctrl_jorig__')
    auto4 = pm.group(empty=True, n='m__element__root__ctrl__')
    auto5 = pm.group(empty=True, n='m__element__root_offset__ctrl__')
    chain_parent([auto1, auto2, auto3, auto4, auto5])
    add_a_keyable_attribute(auto1, 'double', 'globalSize', oDefault=1)

    ##### BUILD THE BASE RIG #####
    #TODO: DEBUG THIS. I have no idea what the base names were.

    # create all the parts
    # the control names
    nPosition =        'm__element__position__ctrl__'
    nTrajectory =      'm__element__trajectory__ctrl__'
    nCtrlRootGrp =     'm__element__root__ctrl_jorig__'
    nCtrlRoot =        'm__element__root__ctrl__'
    nCtrlOffset =      'm__element__root_offset__ctrl__'
    nWheelPin =        'm__wheels__pin__'
    nWheelTurnRoot =   'm__front_wheel_turn__ctrlroot__'
    nWheelTurn =       'm__front_wheel_turn__ctrl__'
    nWheelie =         'm__body_tilt__ctrl__'
    nFrontAxle =       'm__front_axle_pivot__ctrl__'
    nRearAxle =        'm__rear_axle_pivot__ctrl__'

    shPosition = props_icon_lib.create_control_icon(
            'arrowBox', nPosition + 'ShapeTemp',
            [totalBox.width() + 2.0, 1.0, totalBox.depth() + 2.0], offset=[0, 0, totalBox.center()[2]])
    shTrajectory = props_icon_lib.create_control_icon(
            'square', nTrajectory + 'ShapeTemp',
            [totalBox.width() + 1.0, 1.0, totalBox.depth() + 1.0], offset=[0, 0.1, totalBox.center()[2]])
    shCtrlRoot = props_icon_lib.create_control_icon(
            'square', nCtrlRoot + 'ShapeTemp',
            [totalBox.width() + 2.0, 1.0, totalBox.depth() + 2.0], offset=[0, 0, totalBox.center()[2] - ctrlPos[2]])
    shCtrlOffset = props_icon_lib.create_control_icon(
            'square', nCtrlOffset + 'ShapeTemp',
            [totalBox.width() + 1.0, 1.0, totalBox.depth() + 1.0], offset=[0, 0.1, totalBox.center()[2] - ctrlPos[2]])

    oFrontAxleRoot = pm.group(n=nFrontAxle.replace('__ctrl__','__ctrlroot__'), em=True)
    oRearAxleRoot = pm.group(n=nRearAxle.replace('__ctrl__','__ctrlroot__'), em=True)
    #TODO: Set an offset based on the geo bounding box.
    oFrontAxle = props_icon_lib.create_control_icon('rings', nFrontAxle, [0.5, 0.5, 0.5], offset=[0, 2.0, 6.0])
    oRearAxle = props_icon_lib.create_control_icon('rings', nRearAxle, [0.5, 0.5, 0.5], offset=[0, 2.0, -6.0])

    oFrontAxleRoot.setTranslation(frontTiltPos, space='world')
    oFrontAxle.setTranslation(frontTiltPos, space='world')
    oRearAxleRoot.setTranslation(rearTiltPos, space='world')
    oRearAxle.setTranslation(rearTiltPos, space='world')

    # "pop-a-wheelie" control. For now, it is named body_tilt.
    oWheelieRoot = pm.group(n=nWheelie.replace('__ctrl__','__ctrlroot__'), em=True)
    oWheelie = props_icon_lib.create_control_icon('rings', nWheelie, [0.5, 0.5, 0.5])
    for ctrl in [oWheelie, oFrontAxle, oRearAxle]:
        ctrl.getShape().overrideEnabled.set(True)
        ctrl.getShape().overrideColor.set(17)

    # locators for controlling the pop-a-wheelie rotations
    tiltRoot =  pm.group(n='x__wheel_tilt_root__grp__')
    leftTilt =  pm.spaceLocator(n='l__wheel_tilt__loc__')
    rightTilt = pm.spaceLocator(n='r__wheel_tilt__loc__')
    frontTilt = pm.spaceLocator(n='m__front_wheel_tilt__loc__')
    rearTilt =  pm.spaceLocator(n='m__rear_wheel_tilt__loc__')
    leftTiltPivot =  pm.spaceLocator(n='l__wheel_tilt__pivot__')
    rightTiltPivot = pm.spaceLocator(n='r__wheel_tilt__pivot__')
    frontTiltPivot = pm.spaceLocator(n='m__front_wheel_tilt__pivot__')
    rearTiltPivot =  pm.spaceLocator(n='m__rear_wheel_tilt__pivot__')

    leftTiltMap =  pm.createNode('remapValue', n='l__wheel_tilt__map__')
    rightTiltMap = pm.createNode('remapValue', n='l__wheel_tilt__map__')
    frontTiltMap = pm.createNode('remapValue', n='m__front_wheel_tilt__map__')
    rearTiltMap =  pm.createNode('remapValue', n='m__rear_wheel_tilt__map__')

    # the tilt locators are left at origin. But their pivot points will be moved later when the wheels are built.
    # this is more flexible, because the order of build doesn't matter, and the pivot locators
    # can be adjusted by the rigger later, if they are in the wrong place.
    leftTiltPivot.t.connect(leftTilt.rotatePivot)
    rightTiltPivot.t.connect(rightTilt.rotatePivot)
    frontTiltPivot.t.connect(frontTilt.rotatePivot)
    rearTiltPivot.t.connect(rearTilt.rotatePivot)

    oWheelie.tx.connect(leftTiltMap.inputValue)
    oWheelie.tx.connect(rightTiltMap.inputValue)
    oWheelie.tz.connect(frontTiltMap.inputValue)
    oWheelie.tz.connect(rearTiltMap.inputValue)

    leftTiltMap.outValue.connect(leftTilt.rz)
    rightTiltMap.outValue.connect(rightTilt.rz)
    frontTiltMap.outValue.connect(frontTilt.rx)
    rearTiltMap.outValue.connect(rearTilt.rx)

    #TODO: Make this an option, or relative to rig size.
    tiltAmount = 80.0
    leftTiltMap.inputMax.set(tiltAmount)
    rightTiltMap.inputMax.set(-tiltAmount)
    frontTiltMap.inputMax.set(tiltAmount)
    rearTiltMap.inputMax.set(-tiltAmount)
    leftTiltMap.outputMax.set(-180.0)
    rightTiltMap.outputMax.set(180.0)
    frontTiltMap.outputMax.set(180.0)
    rearTiltMap.outputMax.set(-180.0)

    leftTiltPivot.setTranslation(leftTiltPos, space='world')
    rightTiltPivot.setTranslation(rightTiltPos, space='world')
    frontTiltPivot.setTranslation(frontTiltPos, space='world')
    rearTiltPivot.setTranslation(rearTiltPos, space='world')

    rigGroup = pm.PyNode('x__additive_rig__grp__')
    oPosition = pm.PyNode(nPosition)
    oTrajectory = pm.PyNode(nTrajectory)
    oCtrlRootGrp = pm.PyNode(nCtrlRootGrp)
    oCtrlRoot = pm.PyNode(nCtrlRoot)
    oCtrlOffset = pm.PyNode(nCtrlOffset)

    # integrate the axle pivots into the main hierarchy
    chain_parent([oTrajectory, oFrontAxleRoot, oFrontAxle, oRearAxleRoot, oRearAxle])
    pm.parent(oCtrlRootGrp, oRearAxle)

    #oPosition.controlVis.set(3) # set all levels as visible

    oWheelPin = pm.group(n=nWheelPin, em=True)
    oBodySkin = create_rig_joint(jointName='m__{section}__sjnt__'.format(**nameStructure), radius=1.0)
    oSkinGroup = pm.group(n='x__{section}__skin_joints__grp__'.format(**nameStructure), em=True)
    oPartsGroup = pm.group(n='x__{section}__parts__grp__'.format(**nameStructure), em=True)
    oWheelsGroup = pm.group(n='x__{section}__wheels__grp__'.format(**nameStructure), em=True)
    oComponentsGroup = pm.group(n='x__{section}__components__grp__'.format(**nameStructure), em=True)

    shCtrlRoot.setTranslation(ctrlPos, space='world')
    shCtrlOffset.setTranslation(ctrlPos, space='world')

    # the oCtrlRoot parent is locked. Unlock it so I can zero out the control.
    lockParams = ['.tx','.ty','.tz','.rx','.ry','.rz','.sx','.sy','.sz','.v']
    lock_main_params(oCtrlRoot.getParent(), pLocked=False, pChannelBox=True, pKeyable=True, pParams=lockParams)
    oCtrlRoot.getParent().setTranslation(ctrlPos, space='world')
    oCtrlRoot.setTranslation(ctrlPos, space='world')
    oCtrlOffset.setTranslation(ctrlPos, space='world')
    oWheelPin.setTranslation(ctrlPos, space='world')
    oBodySkin.setTranslation(ctrlPos, space='world')
    oPartsGroup.setTranslation(ctrlPos, space='world')
    lock_main_params(oCtrlRoot.getParent(), pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)

    # add switches to turn off auto wheels
    for wheelGuide in wheelGuides:
        paramName = '{}_{}_auto_wheel'.format(wheelGuide.gid_side.get(), wheelGuide.gid_front_side.get())
        add_a_keyable_attribute(oPosition, 'double', paramName, oMin=0, oMax=1, oDefault=1)

    # use the car icons instead of the standard icons (square arrow box instead of circle, for example.)
    props_icon_lib.swap_shape(oPosition, shPosition)
    props_icon_lib.swap_shape(oTrajectory, shTrajectory)
    props_icon_lib.swap_shape(oCtrlRoot, shCtrlRoot)
    props_icon_lib.swap_shape(oCtrlOffset, shCtrlOffset)

    oWheelieRoot.setTranslation(wheeliePos, space='world')
    oWheelie.setTranslation(wheeliePos, space='world')
    lockParams = ['.rx','.ry','.rz','.sx','.sy','.sz','.v']
    lock_main_params(oWheelie, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)
    chain_parent([oPartsGroup, oWheelieRoot, oWheelie])
    oPosition.globalSize.connect(oWheelieRoot.sx)
    oPosition.globalSize.connect(oWheelieRoot.sy)
    oPosition.globalSize.connect(oWheelieRoot.sz)
    pm.parentConstraint(pm.PyNode('m__element__root_offset__ctrl__'), oWheelieRoot, mo=True)

    pm.parent(oBodySkin, oSkinGroup)
    oCons = pm.parentConstraint(oCtrlOffset, oBodySkin, mo=True,
            n='{side}__{section}__{base}_skin__parentconstraint__'.format(**nameStructure))
    #####pm.parent(oCons, constraintParent)
    oCons = pm.scaleConstraint(oCtrlOffset, oBodySkin, mo=True,
            n='{side}__{section}__{base}_skin__scaleconstraint__'.format(**nameStructure))
    #####pm.parent(oCons, constraintParent)
    pm.parent(oWheelPin, oCtrlRoot)
    pm.parent(oPartsGroup, oWheelsGroup, oComponentsGroup, constraintParent, oSkinGroup, rigGroup)
    oComponentsGroup.v.set(0)
    oSkinGroup.v.set(0)
    chain_parent([oComponentsGroup, tiltRoot, leftTilt, rightTilt, frontTilt, rearTilt])
    pm.parent(leftTiltPivot, rightTiltPivot, frontTiltPivot, rearTiltPivot, oComponentsGroup)

    oCtrlRootGrp.tx.unlock()
    oCtrlRootGrp.ty.unlock()
    oCtrlRootGrp.tz.unlock()
    oCtrlRootGrp.rx.unlock()
    oCtrlRootGrp.ry.unlock()
    oCtrlRootGrp.rz.unlock()
    oPosition.globalSize.connect(tiltRoot.sx)
    oPosition.globalSize.connect(tiltRoot.sy)
    oPosition.globalSize.connect(tiltRoot.sz)
    oCons = pm.parentConstraint(oRearAxle, tiltRoot, mo=True,
            n=tiltRoot.name().replace('__grp__','__parentconstraint__'))
    oCons = pm.parentConstraint(rearTilt, oCtrlRootGrp, mo=True,
            n='m__wheel_tilt_constraint__parentconstraint__')

    ##### CONNECT VISIBILITY #####
    ####oVis0 = pm.PyNode('m__element__position__ctrl___controlVis__0__condition__')
    ####oVis1 = pm.PyNode('m__element__position__ctrl___controlVis__1__condition__')
    ####oVis2 = pm.PyNode('m__element__position__ctrl___controlVis__2__condition__')

    if frontWheelGuides:
        # build the front arrow control that rotates all front wheels at once.
        oWheelTurnRoot = pm.group(n=nWheelTurnRoot, em=True)
        oWheelTurn = props_icon_lib.create_control_icon('arrow', nWheelTurn, [0.5, 0.5, 0.5], offset=[0, 0.2, 0])

        oWheelTurnRoot.setTranslation(wheelTurnPos, space='world')
        oWheelTurn.setTranslation(wheelTurnPos, space='world')
        
        oWheelTurn.getShape().overrideEnabled.set(True)
        oWheelTurn.getShape().overrideColor.set(6)
        
        chain_parent([oPartsGroup, oWheelTurnRoot, oWheelTurn])
        oPosition.globalSize.connect(oWheelTurnRoot.sx)
        oPosition.globalSize.connect(oWheelTurnRoot.sy)
        oPosition.globalSize.connect(oWheelTurnRoot.sz)
        pm.parentConstraint(rearTilt, oWheelTurnRoot, mo=True)
        lockParams = ['.tx', '.ty', '.tz', '.rx', '.rz', '.sx','.sy','.sz','.v']
        lock_main_params(oWheelTurn, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)

        # a hack based on curve point numbers to move the control arrow into place.
        arrowPos1 = sum([pnt_ws(x) for x in oPosition.cv[14:18]]) / (len(oPosition.cv[14:18]) * 1.0)
        arrowPos2 = sum([pnt_ws(x) for x in oWheelTurn.cv[2:6]]) / (len(oWheelTurn.cv[2:6]) * 1.0)
        pm.move(oWheelTurn.cv[2:6], [0, 0, arrowPos1[2] - arrowPos2[2]], relative=True)
        #####oVis2.outColorR.connect(oWheelTurn.lodVisibility, force=True)
    else:
        oWheelTurn = None
    
    for i, eachParent in enumerate(geoCollParents):
        oCons = pm.parentConstraint(oCtrlOffset, eachParent, mo=True,
                n='{}__{}__{}_body_geo{}__parentconstraint__'.format(side, section, basename, i+1))
        pm.parent(oCons, constraintParent)
        oCons = pm.scaleConstraint(oCtrlOffset, eachParent, mo=True,
                n='{}__{}__{}_body_geo{}__scaleconstraint__'.format(side, section, basename, i+1))
        pm.parent(oCons, constraintParent)

    oCons = pm.pointConstraint(oCtrlRootGrp, oWheelPin, skip=['x', 'z'], mo=True,
            n='{side}__{section}__{base}_wheels_pin__pointconstraint__'.format(**nameStructure))
    oCons = pm.scaleConstraint(oCtrlOffset, oWheelsGroup,
            n='{side}__{section}__{base}_wheels__scaleconstraint__'.format(**nameStructure))
    oCons = pm.parentConstraint(oCtrlOffset, oPartsGroup,
            n='{side}__{section}__{base}_parts__parentconstraint__'.format(**nameStructure))

    #####oVis2.outColorR.connect(oWheelie.lodVisibility, force=True)

    pm.delete(metaGuideRoot)
    # a collection of parts the rest of the rig will reference.
    bodyRigParts = {
        'riggroup': rigGroup,
        'position': oPosition,
        'trajectory': oTrajectory,
        'controlroot': oCtrlRoot,
        'body': oCtrlOffset,
        'partsgroup':oPartsGroup,
        'skingroup':oSkinGroup,
        'wheelsgroup': oWheelsGroup,
        'components': oComponentsGroup,
        'wheelpin': oWheelPin,
        'wheelturn': oWheelTurn,
        'leftTilt': leftTiltPivot,
        'rightTilt': rightTiltPivot,
        'frontTilt': frontTiltPivot,
        'rearTilt': rearTiltPivot,
        }

    return bodyRigParts


def build_wheel_rig(section, rigGuide, bodyRig):
    # init the parts of the rig guide and the body rig
    parentObj = bodyRig['trajectory']
    rigPosition = bodyRig['position']
    wheelPin = bodyRig['wheelpin']
    mainRigGroup = bodyRig['riggroup']
    bodyControlRoot = bodyRig['controlroot']
    partsGroup = bodyRig['partsgroup']
    skinGroup = bodyRig['skingroup']
    wheelsGroup = bodyRig['wheelsgroup']
    wheelTurn = bodyRig['wheelturn']
    componentsGroup = bodyRig['components']
    constraintParent = pm.PyNode('x__constraints__grp__')

    metaGuideRoot = pm.PyNode(rigGuide.name() + '.' + 'gid_root').outputs()[0]
    metaBase = pm.PyNode(rigGuide.name() + '.' + 'meta_wheel_base').outputs()[0]
    metaInner = pm.PyNode(rigGuide.name() + '.' + 'meta_wheel_inner').outputs()[0]
    metaAltPivot = pm.PyNode(rigGuide.name() + '.' + 'meta_wheel_alternate_pivot').outputs()[0]
    metaRadius = rigGuide.getShape().inputs()[0] # the radius value of the circle in the guide

    basename = rigGuide.gid_basename.get()
    ctrlName = rigGuide.gid_ctrl_name.get()
    side = rigGuide.gid_side.get()
    frontOrBack = rigGuide.gid_front_side.get()

    # .gid_geo stores the names of the geo from the guide process in a comma-separated string.
    # It is NOT assumed that geometry was specified.
    geoColl = rigGuide.gid_geo.get().split(',')
    [geoColl.pop(i) for i, x in enumerate(geoColl) if x == ''] # filter out any blanks
    geoColl = [pm.PyNode(x) for x in geoColl]

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    wheelCenterPos = (metaBase.getTranslation(space='world') + metaInner.getTranslation(space='world')) * 0.5
    #TODO: Test on motorocycle, where wheel is in middle.
    if wheelCenterPos[0] > 0.00:
        rigFlip = 1.0
    elif wheelCenterPos[0] == 0.0:
        rigFlip = 1.0
    else:
        rigFlip = -1.0

    # get a vector to offset the arrow indicator out of the tire. An icon which shows the tire spinning.
    bbCenter = totalBox.center()
    bbMax = totalBox.max()
    arrowName = '{}_pivot__sjnt__'.format(ctrlName)

    # create all the parts
    rigGroup = pm.group(n='{}_rig__grp__'.format(ctrlName), em=True)
    oWheelBaseRoot = pm.group(n='{}_base__root__'.format(ctrlName), em=True)
    oWheelBase = pm.group(n='{}_base__loc__'.format(ctrlName), em=True)
    oWheelPivotZero = pm.group(n='{}_pivot__zero__'.format(ctrlName), em=True)
    oWheelPivotRoot = pm.group(n='{}_pivot__root__'.format(ctrlName), em=True)
    oWheelPivot = pm.group(n='{}_pivot__loc__'.format(ctrlName), em=True)
    oWheelSkin = props_icon_lib.create_control_icon('arrow', arrowName, [0.1, 0.1, 0.1], joint=True)
    oInner = pm.group(n='{}_inner__loc__'.format(ctrlName), em=True)
    oOuter = pm.group(n='{}_outer__loc__'.format(ctrlName), em=True)
    oControlZero = pm.group(n='{}_ctrl_zero__root__'.format(ctrlName), em=True)
    oControlRoot = pm.group(n='{}_ctrl__root__'.format(ctrlName), em=True)
    oControlDriver = pm.group(n='{}_ctrl__driver__'.format(ctrlName), em=True)
    oControlFollow = pm.group(n='{}_ctrl_follow__grp__'.format(ctrlName), em=True)
    oWobble = pm.group(n='{}_wheel_wobble__grp__'.format(ctrlName), em=True)
    oControl = pm.circle(n='{}_offset__ctrl__'.format(ctrlName), nr=(1, 0, 0), sections=24, ch=True)[0]
    oControl2 = pm.circle(n='{}__ctrl__'.format(ctrlName), nr=(1, 0, 0), sections=24, ch=True)[0]
    localWheelPin = pm.group(n='{}_wheel_pin__hook__'.format(ctrlName), em=True)

    # modify the position of the oWheelSkin arrow so it sits outside of the wheel. It is the turn indicator.
    # Also instead of an arrow, use a saw-tooth pattern to make a thick line
    height = metaRadius.radius.get() * 0.25
    curvePoints = [pnt for pnt in props_icon_lib.sawtooth_wave_pattern(height, width=height*0.2, segments=30)]
    sawCurve = pm.curve( name='temporary_saw_curve', d=1, p=curvePoints )
    props_icon_lib.swap_shape(oWheelSkin, sawCurve)
    wheelSkinShape = oWheelSkin.getShape()
    arrowOffset = [(bbCenter[0] - bbMax[0]) * rigFlip * -1.2, bbMax[1] * 0.35, 0]
    pm.move(wheelSkinShape.cv, arrowOffset, r=True)
    #pm.rotate(wheelSkinShape.cv, [0, -90, 0], r=True, fo=True)
    #pm.rotate(wheelSkinShape.cv, [0, 0, -90], r=True, fo=True)
    wheelSkinShape.overrideDisplayType.set(1) # template

    oControl.getShape().overrideEnabled.set(1)
    oControl2.getShape().overrideEnabled.set(1)
    oWheelSkin.getShape().overrideEnabled.set(1)
    #####bodyRig['vis2'].outColorR.connect(oControl.lodVisibility, force=True)
    #####bodyRig['vis2'].outColorR.connect(oControl2.lodVisibility, force=True)
    #####bodyRig['vis2'].outColorR.connect(oWheelSkin.lodVisibility, force=True)

    # A parameter for manually turning the wheel, in addition to all other inputs
    add_a_keyable_attribute(oControl2, 'double', 'wheel_manual_spin')
    pManualSpin = pm.PyNode(oControl2.name() + '.' + 'wheel_manual_spin')

    # create the hierarchy
    chain_parent(
            [wheelsGroup, rigGroup, oWheelBaseRoot, oWheelBase, oWheelPivotZero, oWheelPivotRoot,
            oControl, oWheelPivot, oWobble, oWheelSkin])
    pm.parent(oInner, oOuter, oWheelBaseRoot)
    chain_parent([rigGroup, oControlZero, oControlRoot, oControlDriver, oControlFollow, oControl2])
    pm.parent(localWheelPin, wheelPin)

    ### create a pivot to constrain the tire to.
    centerXZ = (metaBase.getTranslation(space='world') + metaInner.getTranslation(space='world')) * 0.5
    centerY = rigGuide.getTranslation(space='world')
    centerOfWheel = [centerXZ[0], centerY[1], centerXZ[2]]
    centerAltPivot = metaAltPivot.getTranslation(space='world')
    centerAltXZ = metaAltPivot.getTranslation(space='world')
    centerAltXZ.y = 0.0

    oWheelBaseRoot.setTranslation(centerAltXZ, space='world')
    oWheelBase.setTranslation(centerAltXZ, space='world')
    oWheelPivotZero.setTranslation(centerAltPivot, space='world')
    oWheelPivotRoot.setTranslation(centerAltPivot, space='world')
    oWheelPivot.setTranslation(centerAltPivot, space='world')
    oWobble.setTranslation(centerOfWheel, space='world')
    oWheelSkin.setTranslation(centerOfWheel, space='world')
    oInner.setTranslation(metaInner.getTranslation(space='world'), space='world')
    oOuter.setTranslation(metaBase.getTranslation(space='world'), space='world')
    oControlZero.setTranslation(centerAltPivot, space='world')
    oControlRoot.setTranslation(centerAltPivot, space='world')
    oControlDriver.setTranslation(centerAltPivot, space='world')
    oControlFollow.setTranslation(centerAltPivot, space='world')
    oControl.setTranslation(centerAltPivot, space='world')
    oControl2.setTranslation(centerAltPivot, space='world')
    localWheelPin.setTranslation(wheelPin.getTranslation(space='world'), space='world')

    if geoColl:
        for each in geoColl:
            geoBaseName = each.name()
            # set the translation of the constraints, otherwise it interferes with the bounding box!
            oCons = pm.parentConstraint(oWheelSkin, each, mo=True,
                    n='{}__{}__{}_{}__parentconstraint__'.format(side, section, basename, geoBaseName))
            oCons.setTranslation(centerOfWheel, space='world')
            pm.parent(oCons, constraintParent)
            oCons = pm.scaleConstraint(oWheelSkin, each, mo=True,
                    n='{}__{}__{}_{}__scaleconstraint__'.format(side, section, basename, geoBaseName))
            oCons.setTranslation(centerOfWheel, space='world')
            pm.parent(oCons, constraintParent)

    # create the utility nodes that drive the rotation of the wheel.
    mult360 = pm.createNode('multiplyDivide', n='{}_rig_360__mlt__'.format(ctrlName))
    dividePI = pm.createNode('multiplyDivide', n='{}_rig_pi__mlt__'.format(ctrlName))
    dividePI.operation.set(2) # divide
    # this PMA will combine both the auto-control and the auto-driver. When the entire car is translating.
    mult360Add = pm.createNode('plusMinusAverage', n='{}_rig_auto_driver__add__'.format(ctrlName))
    # this plusMinusAverage will combine all the various channels to rotate the tire
    tireRotateADD = pm.createNode('plusMinusAverage', n='{}_rig_rotation_driver__add__'.format(ctrlName))
    # tiltRemap takes the sideways translation of the control and rotates the tire sideways.
    # The rotatePivot is animated to give it a rocking effect.
    tiltRemap = pm.createNode('remapValue', n='{}_rig_tilt__map__'.format(ctrlName))
    tiltCondition = pm.createNode('condition', n='{}_rig_tilt__cond__'.format(ctrlName))

    oControl2.tz.connect(mult360Add.input2D[0].input2Dx)
    oControlDriver.tz.connect(mult360Add.input2D[1].input2Dx)
    mult360Add.output2Dx.connect(mult360.input1X)

    oControl.t.connect(oControlFollow.t)

    oControl2.tz.connect(oWheelPivotRoot.tz)
    oControl2.r.connect(oWobble.r)
    oControl2.rotateOrder.set(3) # xzy
    oWobble.rotateOrder.set(3) # xzy

    # turn the front wheels in rotateY based on the wheel turn arrow control.
    if wheelTurn and frontOrBack in ['front', 'mid']:
        wheelTurn.ry.connect(oWheelBaseRoot.ry)
        wheelTurn.ry.connect(oControlFollow.ry)

    oControl.getShape().inputs()[0].radius.set(metaRadius.radius.get() * 0.85)
    oControl.getShape().inputs()[0].centerX.set(oOuter.tx.get() * 1.5)
    oControl2.getShape().inputs()[0].radius.set(metaRadius.radius.get() * 0.7)
    oControl2.getShape().inputs()[0].centerX.set(oOuter.tx.get() * 1.6)

    # create a pointed end on the controllers so you can tell how they are rotating
    ctrlCVs = oControl.getShape().cv
    topPoint = ctrlCVs[1].getPosition(space='world') + [0, 0.05*metaRadius.radius.get(), 0]
    ctrlCVs[0].setPosition(topPoint, space='world')
    ctrlCVs[2].setPosition(topPoint, space='world')
    ctrlCVs[1].setPosition(topPoint, space='world')

    ctrlCVs = oControl2.getShape().cv
    topPoint = ctrlCVs[1].getPosition(space='world') + [0, 0.05*metaRadius.radius.get(), 0]
    ctrlCVs[0].setPosition(topPoint, space='world')
    ctrlCVs[2].setPosition(topPoint, space='world')
    ctrlCVs[1].setPosition(topPoint, space='world')

    pm.delete(oControl, ch=True)
    pm.delete(oControl2, ch=True)

    mult360.input2X.set(360)
    mult360.outputX.connect(dividePI.input1X)
    dividePI.input2X.set(math.pi * 2.0 * metaRadius.radius.get())
    dividePI.outputX.connect(tireRotateADD.input2D[1].input2Dx)

    # connect manual rotation and multiply by 360 so 1 = one turn.
    oManualUnit = pm.createNode('unitConversion', n='{}_rig_manual__unit__'.format(ctrlName))
    oManualUnit.conversionFactor.set(360)
    oManualUnit2 = pm.createNode('unitConversion', n='{}_rig_manual2__unit__'.format(ctrlName))
    oManualUnit2.conversionFactor.set(math.pi * 2.0)
    pManualSpin.connect(oManualUnit.input)
    pManualSpin.connect(oManualUnit2.input)
    oManualUnit.output.connect(tireRotateADD.input2D[2].input2Dx)
    oManualUnit2.output.connect(oWheelSkin.rx)

    wheelExpression = False
    if wheelExpression:
        pass
    else:
        #TODO: edit out unecessary nodes. oWheelPivot is now controlled by an expression.
        tireRotateADD.output2Dx.connect(oWheelPivot.rx)

    if wheelExpression:
        # add an expression to control the wheel in all directions of movement.    
        # add the directionReader locator, 5 units behind the wheel.
        #TODO: Add an on off integer attribute on the master control, PER wheel.
        #TODO: Unhook the existing translateZ parameter. OR make it a switch. When auto is off, then it reads the nodes instead.
        #TODO: Try to make a more general kind of direction that doesn't rely on the getAttr -t.
        directionReader = pm.spaceLocator(n='{}__{}_dir_reader__loc__'.format(side, frontOrBack))
        pm.parent(directionReader, oControl)
        directionReader.t.set([0, 0, -5.0])
        paramName = '{}_{}_auto_wheel'.format(rigGuide.gid_side.get(), rigGuide.gid_front_side.get())
        onOffSwitch = '{}.{}'.format(rigPosition.name(), paramName)
        # the expression. It uses getAttr -t to sample time one frame before:
        lastPos1 = 'getAttr -t ( frame -1 ) {}'.format(oControlDriver.name())
        lastPos2 = 'getAttr -t ( frame -1 ) {}'.format(oControlFollow.name())
        expList = [
            'if ({} == 1){{'.format(onOffSwitch),
            '    float $tau = 6.28318530718;',
            '    float $twoPir = {} * 2.0 * $tau;'.format( metaRadius.radius.get() ),
            '    // Measure which way the car is facing',
            '    float $tireWS[] = `xform -q -ws -t {}`;'.format( oWheelSkin.name() ),
            '    float $dirWS[] = `xform -q -ws -t {}`;'.format( directionReader.name() ),
            '    vector $carFacing = << $tireWS[0] - $dirWS[0], $tireWS[1] - $dirWS[1], $tireWS[2] - $dirWS[2] >>;',
            '    // Measure the current and last positions',
            '    vector $curPos = <<',
            '        {}.translateX + {}.translateX,'.format(oControlDriver.name(), oControlFollow.name()),
            '        {}.translateY + {}.translateY,'.format(oControlDriver.name(), oControlFollow.name()),
            '        {}.translateZ + {}.translateZ'.format(oControlDriver.name(), oControlFollow.name()),
            '        >>;',
            '    float $lastPosX = `{}.tx` + `{}.tx`;'.format(lastPos1, lastPos2),
            '    float $lastPosY = `{}.ty` + `{}.ty`;'.format(lastPos1, lastPos2),
            '    float $lastPosZ = `{}.tz` + `{}.tz`;'.format(lastPos1, lastPos2),
            '    vector $lastPos = <<$lastPosX, $lastPosY, $lastPosZ>>;',
            '    vector $movement = $curPos - $lastPos;',
            '    // measure the direction (reverse or forward) of the cars motion using dot product',
            '    float $carReverse = dot(unit($movement), unit($carFacing));',
            '    float $carDirection = 0.0;',
            '    if ($carReverse >= 0){',
            '            $carDirection = 1.0;',
            '    }else{',
            '            $carDirection = -1.0;',
            '    }',
            '    float $rotateWheel = ((mag($movement) * $twoPir) * $carDirection);',
            '    {pivot}.rotateX = {pivot}.rotateX + $rotateWheel;'.format(pivot = oWheelPivot),
            '}',
        ]

        pm.expression( name='{}__{}_wheel_turn__expr__'.format(side, frontOrBack), s='\n'.join(expList))

    # set the tilt parameters
    oControl2.tx.connect(tiltRemap.inputValue)
    tiltRemap.outValue.connect(oWheelBase.rz)
    # values which mean 1.0 will be a 45 degree rotation. 2.0 will be 90.
    #TODO: Set this as an option or a sane value based on rig world scale.
    tiltAmount = 80
    tiltRemap.inputMin.set(-tiltAmount)
    tiltRemap.inputMax.set(tiltAmount)
    tiltRemap.outputMin.set(180)
    tiltRemap.outputMax.set(-180)

    tiltCondition.operation.set(3) # greater or equal
    oControl2.tx.connect(tiltCondition.firstTerm)

    if rigFlip == 1.0:
        oInner.tx.connect(tiltCondition.colorIfFalseR)
        oOuter.tx.connect(tiltCondition.colorIfTrueR)
    else:
        oInner.tx.connect(tiltCondition.colorIfTrueR)
        oOuter.tx.connect(tiltCondition.colorIfFalseR)

    tiltCondition.outColorR.connect(oWheelBase.rotatePivotX)

    if rigFlip == 1.0:
        oControl.getShape().overrideColor.set(13)
        oControl2.getShape().overrideColor.set(20)
        oWheelSkin.getShape().overrideColor.set(20)
    else:
        oControl.getShape().overrideColor.set(6)
        oControl2.getShape().overrideColor.set(18)
        oWheelSkin.getShape().overrideColor.set(18)

    #TODO: Add a local wheel pin for each wheel, for special cases like the motorcycle fork.
    oCons = pm.parentConstraint(localWheelPin, oControlDriver, mo=True,
            n='{}__{}__{}_driver__parentconstraint__'.format(side, section, basename))
    oCons.setTranslation(centerOfWheel, space='world')
    #####pm.parent(oCons, constraintParent)
    oCons = pm.pointConstraint(localWheelPin, oWheelBaseRoot, mo=True,
            n='{}__{}__{}_base_root__pointconstraint__'.format(side, section, basename))
    oCons.setTranslation(centerOfWheel, space='world')
    #####pm.parent(oCons, constraintParent)
    oCons = pm.parentConstraint(pm.PyNode('m__element__position__ctrl__'), oControlRoot, mo=True,
            n='{}__{}__{}_wheel_root__parentconstraint__'.format(side, section, basename))
    oCons = pm.parentConstraint(pm.PyNode('m__element__root__ctrl__'), oControlZero, mo=True,
            n='{}__{}__{}_wheel_zero__parentconstraint__'.format(side, section, basename))
    oCons = pm.parentConstraint(pm.PyNode('m__element__root__ctrl__'), rigGroup, mo=True,
            n='{}__{}__{}_rig_position__parentconstraint__'.format(side, section, basename))
    oCons = pm.orientConstraint(parentObj, oWheelPivotZero, skip=['y', 'z'], mo=True,
            n='{}__{}__{}_wheelpivotzero__orientconstraint__'.format(side, section, basename))
    oCons = pm.orientConstraint(parentObj, oControlFollow, skip=['y', 'z'], mo=True,
            n='{}__{}__{}_wheelctrlfollow__orientconstraint__'.format(side, section, basename))

    trajectoryChild = pm.PyNode('m__element__root__ctrl_jorig__')
    oCons = pm.pointConstraint(trajectoryChild, localWheelPin, skip=['x', 'z'], mo=True,
            n='{}__{}__{}_wheels_hook__pointconstraint__'.format(side, section, basename))

    lockParams = ['.sx','.sy','.sz','.v']
    lock_main_params(oControl, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)
    lock_main_params(oControl2, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)
    oWheelSkin.drawStyle.set(2) # hide the bone

    # Add a lattice for deforming the wheel
    #NOTE: When creating lattices, watch for bugs where there are any transforms below the geo.
    # eg. Constraints whose transform is at origin. This will expand the lattice bounding box!
    if geoColl:
        latticeRows = 18
        wheelBB = find_group_bb(geoColl)
        latticeCenter = [centerOfWheel[0], (centerOfWheel[1]+wheelBB[0])*0.5, centerOfWheel[2]]
        pm.select(geoColl)
        latticeName = '{}__lattice__'.format(ctrlName)
        oFFD, oLattice, oBase = pm.lattice(divisions=[2,latticeRows,2], n=latticeName, oc=True, ol=1)
        oFFD.local.set(False)
        oFFD.localInfluenceT.set(6)

        # Duplicate the lattice to act as a blendshape
        # a little hack since duplicating a lattice duplicates the base. Parent the base temporarily.
        origParent = oBase.getParent()
        pm.parent(oBase, oLattice)
        oSquashBS = pm.duplicate([oLattice.getShape()], n='{}_squash_lattice__target__'.format(ctrlName))[0]
        oSkewBS = pm.duplicate([oLattice.getShape()], n='{}_skew_lattice__target__'.format(ctrlName))[0]
        pm.delete(oSquashBS.getChildren(type='constraint')) # deletes any child constraints
        pm.delete(oSquashBS.getChildren(type='transform')) # deletes the extra Base
        pm.delete(oSkewBS.getChildren(type='constraint')) # deletes any child constraints
        pm.delete(oSkewBS.getChildren(type='transform')) # deletes the extra Base
        pm.parent(oBase, origParent) # restores order to the land...
        pm.parent(oSquashBS, oSkewBS, componentsGroup)
        oLattice.v.set(0)
        oBase.v.set(0)

        # Shape the points of the blendshape using cEasing() which returns an ease-in or ease-out curve.
        # this creates a bulging shape at the bottom of the lattice.
        rows = 5
        #TODO: This should likely be relative to the size of the wheel and hub, or a locator the rigger can place!
        moveAmount = 10
        #TODO: Store moveAmount which will be fed into the driver when the wheel control moves down by that amount
        zScale = [x[0] for x in cEasing(1.2, 0.0, -0.2, 0.0, rows, 'up')]
        xScale = [x[0] for x in cEasing(1.5, 0.0, -0.5, 0.0, rows, 'up')]
        yMoves = [x[0] for x in cEasing(moveAmount, 0.0, -moveAmount, 0.0, rows, 'down')]
        latBB = oSquashBS.getBoundingBox()
        for i in xrange(rows):
            scaleFactor = [xScale[i], 1.0, zScale[i]]
            moveFactor = yMoves[i]
            latPoints = oSquashBS.pt[0:1][i]
            oPivot = (latBB.center()[0], latBB.min()[1], latBB.center()[2])
            pm.scale(latPoints, scaleFactor, r=True, p=oPivot)
            pm.move(latPoints, 0, moveFactor, 0, r=True)

        # Create a skew shape that skews the wheel from side to side.
        latBB = oSkewBS.getBoundingBox()
        #TODO: Should the skew be normalized to world space, or to the size of the tire? (depends on the driver?)
        skewAmount = 10.0
        for i in xrange(latticeRows):
            pm.move(oSkewBS.getShape().pt[0][i], (i/float(latticeRows))*skewAmount, 0, 0, r=True)
            pm.move(oSkewBS.getShape().pt[1][i], (i/float(latticeRows))*skewAmount, 0, 0, r=True)

        oBB = wheelBB[4] # the totalBox from find_group_bb()

        #latticeScale = [oBB.width(), oBB.height() * 0.5, oBB.depth()]
        #oLattice.scale.set(latticeScale)
        #oBase.scale.set(latticeScale)
        pm.parentConstraint(oControl, oLattice,
                n='{}__{}__{}_squash_lattice__parentconstraint__'.format(side, section, basename),
                mo=True)
        oCons.setTranslation(centerOfWheel, space='world')
        #####pm.parent(oCons, constraintParent)
        pm.parentConstraint(oControl, oBase,
                n='{}__{}__{}_squash_lattice_base__parentconstraint__'.format(side, section, basename),
                mo=True)
        oCons.setTranslation(centerOfWheel, space='world')
        #####pm.parent(oCons, constraintParent)

        # bottom row of lattice:
        oLattice.pt[1][0][1]
        oLattice.pt[0][0][1]
        oLattice.pt[0][0][0]
        oLattice.pt[1][0][0]

        pm.parent(oLattice, oBase, rigGroup)
        oBlend = pm.blendShape(oSquashBS, oSkewBS, oLattice, n='{}_squash__blendshape__'.format(ctrlName))[0]

        # create 2 remapValues to drive the squash blendshape
        squashRemap = pm.createNode('remapValue', n='{}_squash__map__'.format(ctrlName))
        squashClamp = pm.createNode('remapValue', n='{}_squash_clamp__map__'.format(ctrlName))
        oSkewMLT = pm.createNode('multiplyDivide', n='{}_skew_blendshape__mlt__'.format(ctrlName))
        oSkewMLT.input2X.set(2.0)
        squashRemap.inputMax.set(-moveAmount)
        squashClamp.inputMin.set(-moveAmount)
        squashClamp.outputMin.set(-moveAmount)
        squashClamp.inputMax.set(3)
        squashClamp.outputMax.set(3)
        oControl2.ty.connect(squashRemap.inputValue)
        oControl2.ty.connect(squashClamp.inputValue)
        squashRemap.outValue.connect(oBlend.w[0]) # the squash blendshape target
        pm.PyNode('m__element__root_offset__ctrl__').tx.connect(oSkewMLT.input1X)
        oSkewMLT.outputX.connect(oBlend.w[1]) # the skew side-to-side blendshape target
        squashClamp.outValue.connect(oWheelPivotRoot.ty)

    pm.delete(metaGuideRoot)


def build_seat_rig(section, rigGuide, bodyRig):
    # init the parts of the rig guide
    parentObj = bodyRig['trajectory']
    mainRigGroup = bodyRig['riggroup']
    partsGroup = bodyRig['partsgroup']
    bodyOffset = bodyRig['body']
    skinGroup = bodyRig['skingroup']
    rigPosition = bodyRig['position']
    constraintParent = pm.PyNode('x__constraints__grp__')

    metaGuideRoot = pm.PyNode(rigGuide.name() + '.' + 'gid_root').outputs()[0]
    metaRearPivot = pm.PyNode(rigGuide.name() + '.' + 'meta_rear_pivot').outputs()[0]

    basename = rigGuide.gid_basename.get()
    ctrlName = rigGuide.gid_ctrl_name.get()
    side = rigGuide.gid_side.get()
    frontOrBack = rigGuide.gid_front_side.get()

    geoColl = rigGuide.gid_geo.get().split(',')
    [geoColl.pop(i) for i, x in enumerate(geoColl) if x == ''] # filter out any blanks
    geoColl = [pm.PyNode(x) for x in geoColl]

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
    else:
        rigFlip = -1.0

    # create all the parts
    rigGroup = pm.group(n='{}_rig__grp__'.format(ctrlName), em=True)
    oSeatRoot = pm.group(em=True, n='{}__ctrlroot__'.format(ctrlName))
    oSeatRearRoot = pm.group(em=True, n='{}_rear__ctrlroot__'.format(ctrlName))
    oSeat = props_icon_lib.create_control_icon(
            'square', '{}__ctrl__'.format(ctrlName),
            [totalBox.width() * 1.1, 1.0, totalBox.depth() * 1.1], offset=[0, 0.25, 0])
    oSeatRear = props_icon_lib.create_control_icon(
            'square', '{}_rear__ctrl__'.format(ctrlName),
            [totalBox.width() * 1.1, 1.0, totalBox.depth() * 0.65], offset=[0, 0.5, 0])
    oSeatJoint = create_rig_joint('{}__skjnt__'.format(ctrlName), radius=0.3)
    oSeatRearJoint = create_rig_joint('{}_rear__skjnt__'.format(ctrlName), radius=0.3)

    oSeatRoot.setTranslation(rigGuide.getTranslation(space='world'), space='world')
    oSeatRearRoot.setTranslation(metaRearPivot.getTranslation(space='world'), space='world')
    oSeat.setTranslation(rigGuide.getTranslation(space='world'), space='world')
    oSeatRear.setTranslation(metaRearPivot.getTranslation(space='world'), space='world')
    oSeatJoint.setTranslation(rigGuide.getTranslation(space='world'), space='world')
    oSeatRearJoint.setTranslation(metaRearPivot.getTranslation(space='world'), space='world')

    for each in geoColl:
        each.tx.unlock()
        each.ty.unlock()
        each.tz.unlock()
        each.rx.unlock()
        each.ry.unlock()
        each.rz.unlock()
        each.sx.unlock()
        each.sy.unlock()
        each.sz.unlock()
        #TODO: I'm constraining the geo to not double-transform. Figure something more robust out.
        oCons = pm.parentConstraint(pm.PyNode('x__additive_rig__grp__'), each,
                n='{}__{}__{}_{}__parentconstraint__'.format(side, section, basename, each.name()),
                mo=True)
        oCons.setTranslation(totalBox.center(), space='world')
        pm.parent(oCons, constraintParent)
        oCons = pm.scaleConstraint(pm.PyNode('x__additive_rig__grp__'), each,
                n='{}__{}__{}_{}__scaleconstraint__'.format(side, section, basename, each.name()),
                mo=True)
        oCons.setTranslation(totalBox.center(), space='world')
        pm.parent(oCons, constraintParent)

    # skin before parenting the joints, otherwise the tip joint doesn't get any influence.
    for eachGeo in geoColl:
        skin_geometry(
                [oSeatJoint, oSeatRearJoint], eachGeo,
                '{}_{}__skincluster__'.format(ctrlName, each.name())
                )

    chain_parent([partsGroup, rigGroup, oSeatRoot, oSeat, oSeatRearRoot, oSeatRear])
    chain_parent([skinGroup, oSeatJoint, oSeatRearJoint])

    oCons = pm.parentConstraint(oSeat, oSeatJoint,
            n='{}__{}__{}_skin__parentconstraint__'.format(side, section, basename),
            mo=True)
    oCons = pm.parentConstraint(oSeatRear, oSeatRearJoint,
            n='{}__{}__{}_rear_skin__parentconstraint__'.format(side, section, basename),
            mo=True)
    oCons = pm.scaleConstraint(bodyOffset, oSeatJoint,
            n='{}__{}__{}_skin__scaleconstraint__'.format(side, section, basename),
            mo=True)
    oCons = pm.scaleConstraint(bodyOffset, oSeatRearJoint,
            n='{}__{}__{}_rear_skin__scaleconstraint__'.format(side, section, basename),
            mo=True)

    if rigFlip == 1.0:
        oSeat.getShape().overrideEnabled.set(True)
        oSeatRear.getShape().overrideEnabled.set(True)
        oSeat.getShape().overrideColor.set(6)
        oSeatRear.getShape().overrideColor.set(18)
    else:
        oSeat.getShape().overrideEnabled.set(True)
        oSeatRear.getShape().overrideEnabled.set(True)
        oSeat.getShape().overrideColor.set(13)
        oSeatRear.getShape().overrideColor.set(20)

    #####bodyRig['vis2'].outColorR.connect(oSeat.lodVisibility, force=True)
    #####bodyRig['vis2'].outColorR.connect(oSeatRear.lodVisibility, force=True)

    pm.parentConstraint(bodyOffset, rigGroup,
            n='{}__{}__{}_riggrp__parentconstraint__'.format(side, section, basename),
            mo=True)
    rigPosition.s.connect(rigGroup.s)

    lockParams = ['.sx','.sy','.sz','.v']
    lock_main_params(oSeat, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)
    lock_main_params(oSeatRear, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)

    pm.delete(metaGuideRoot)


def build_door_rig(section, rigGuide, bodyRig):
    # init the parts of the rig guide
    parentObj = bodyRig['trajectory']
    mainRigGroup = bodyRig['riggroup']
    partsGroup = bodyRig['partsgroup']
    skinGroup = bodyRig['skingroup']
    constraintParent = pm.PyNode('x__constraints__grp__')

    metaGuideRoot = pm.PyNode(rigGuide.name() + '.' + 'gid_root').outputs()[0]

    basename = rigGuide.gid_basename.get()
    ctrlName = rigGuide.gid_ctrl_name.get()
    side = rigGuide.gid_side.get()
    frontOrBack = rigGuide.gid_front_side.get()

    geoColl = rigGuide.gid_geo.get().split(',')
    [geoColl.pop(i) for i, x in enumerate(geoColl) if x == ''] # filter out any blanks
    geoColl = [pm.PyNode(x) for x in geoColl]

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
    else:
        rigFlip = -1.0

    # create all the parts
    rigGroup = pm.group(n='{}_rig__grp__'.format(ctrlName), em=True)
    oControlRoot = pm.group(n='{}_door__ctrlroot__'.format(ctrlName), em=True)
    oControl = props_icon_lib.create_control_icon('box', '{}_door__ctrl__'.format(ctrlName), [0.5, 2.0, 0.5])

    oControlRoot.setTranslation(rigGuide.getTranslation(space='world'), space='world')
    oControl.setTranslation(rigGuide.getTranslation(space='world'), space='world')
    oControlRoot.setRotation(rigGuide.getRotation(space='world'), space='world')
    oControl.setRotation(rigGuide.getRotation(space='world'), space='world')

    for each in geoColl:
        eachName = each.name()
        oCons = pm.parentConstraint(oControl, each,
                n='{}__{}__{}_{}__parentconstraint__'.format(side, section, basename, eachName),
                mo=True)
        oCons.setTranslation(totalBox.center(), space='world')
        pm.parent(oCons, constraintParent)
        oCons = pm.scaleConstraint(oControl, each,
                n='{}__{}__{}_{}__scaleconstraint__'.format(side, section, basename, eachName),
                mo=True)
        oCons.setTranslation(totalBox.center(), space='world')
        pm.parent(oCons, constraintParent)

    chain_parent([partsGroup, rigGroup, oControlRoot, oControl])

    oControl.getShape().overrideEnabled.set(True)
    if rigFlip == 1.0:
        oControl.getShape().overrideColor.set(6)
    else:
        oControl.getShape().overrideColor.set(13)
    #####bodyRig['vis2'].outColorR.connect(oControl.lodVisibility, force=True)

    pm.parentConstraint(pm.PyNode('m__element__root_offset__ctrl__'), rigGroup,
            n='{}__{}__{}_riggrp__parentconstraint__'.format(side, section, basename),
            mo=True)
    pm.scaleConstraint(pm.PyNode('m__element__root_offset__ctrl__'), rigGroup,
            n='{}__{}__{}_riggrp__scaleconstraint__'.format(side, section, basename),
            mo=True)

    lockParams = ['.sx','.sy','.sz','.v']
    lock_main_params(oControl, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)

    pm.delete(metaGuideRoot)


def build_steering_rig(section, rigGuide, bodyRig):
    # init the parts of the rig guide
    parentObj = bodyRig['trajectory']
    mainRigGroup = bodyRig['riggroup']
    partsGroup = bodyRig['partsgroup']
    skinGroup = bodyRig['skingroup']
    constraintParent = pm.PyNode('x__constraints__grp__')

    metaGuideRoot = pm.PyNode(rigGuide.name() + '.' + 'gid_root').outputs()[0]
    metaWheelBase = pm.PyNode(rigGuide.name() + '.' + 'meta_steering_base').outputs()[0]
    metaWheelWidth = pm.PyNode(rigGuide.name() + '.' + 'meta_steering_width').outputs()[0]

    controlRadius = metaWheelWidth.tx.get() * 1.0

    basename = rigGuide.gid_basename.get()
    ctrlName = rigGuide.gid_ctrl_name.get()
    side = rigGuide.gid_side.get()
    frontOrBack = rigGuide.gid_front_side.get()

    geoColl = rigGuide.gid_geo.get().split(',')
    [geoColl.pop(i) for i, x in enumerate(geoColl) if x == ''] # filter out any blanks
    geoColl = [pm.PyNode(x) for x in geoColl]

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
    else:
        rigFlip = -1.0

    # create all the parts
    rigGroup = pm.group(n='{}_rig__grp__'.format(ctrlName), em=True)
    oControlRoot = pm.group(n='{}__ctrlroot__'.format(ctrlName), em=True)
    oControl = pm.circle(n='{}__ctrl__'.format(ctrlName), nr=(0, 0, -1), sections=24, ch=True)[0]
    oControl.getShape().inputs()[0].radius.set(controlRadius)
    pm.delete(oControl, ch=True)

    chain_parent([partsGroup, rigGroup, oControlRoot, oControl])

    oControlRoot.setTranslation(rigGuide.getTranslation(space='world'), space='world')
    oControlRoot.setRotation(rigGuide.getRotation(space='world'), space='world')

    for each in geoColl:
        eachName = each.name()
        oCons = pm.parentConstraint(oControl, each, 
                n='{}__{}__{}_{}__parentconstraint__'.format(side, section, basename, eachName),
                mo=True)
        oCons.setTranslation(totalBox.center(), space='world')
        pm.parent(oCons, constraintParent)

    ctrlCVs = oControl.getShape().cv
    topPoint = ctrlCVs[1].getPosition(space='world') + [0, -0.08*controlRadius, 0]
    ctrlCVs[0].setPosition(topPoint, space='world')
    ctrlCVs[2].setPosition(topPoint, space='world')
    ctrlCVs[1].setPosition(topPoint, space='world')

    oControl.getShape().overrideEnabled.set(True)
    if rigFlip == 1.0:
        oControl.getShape().overrideColor.set(6)
    else:
        oControl.getShape().overrideColor.set(13)
    #####bodyRig['vis2'].outColorR.connect(oControl.lodVisibility, force=True)

    pm.parentConstraint(pm.PyNode('m__element__root_offset__ctrl__'), rigGroup,
            n='{}__{}__{}_riggrp__parentconstraint__'.format(side, section, basename),
            mo=True)
    pm.scaleConstraint(pm.PyNode('m__element__root_offset__ctrl__'), rigGroup,
            n='{}__{}__{}_riggrp__scaleconstraint__'.format(side, section, basename),
            mo=True)

    lockParams = ['.sx','.sy','.sz','.v']
    lock_main_params(oControl, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)

    pm.delete(metaGuideRoot)


def build_piston_rig(section, rigGuide, bodyRig):
    # init the parts of the rig guide
    parentObj = bodyRig['trajectory']
    mainRigGroup = bodyRig['riggroup']
    partsGroup = bodyRig['partsgroup']
    skinGroup = bodyRig['skingroup']
    constraintParent = pm.PyNode('x__constraints__grp__')

    metaGuideRoot = pm.PyNode(rigGuide.name() + '.' + 'gid_root').outputs()[0]
    metaWheelBase = pm.PyNode(rigGuide.name() + '.' + 'meta_piston_pivot').outputs()[0]

    topPos = rigGuide.getTranslation(space='world')
    topRot = rigGuide.getRotation(space='world')
    botPos = metaWheelBase.getTranslation(space='world')

    basename = rigGuide.gid_basename.get()
    ctrlName = rigGuide.gid_ctrl_name.get()
    side = rigGuide.gid_side.get()
    frontOrBack = rigGuide.gid_front_side.get()

    geoColl = rigGuide.gid_geo.get().split(',')
    [geoColl.pop(i) for i, x in enumerate(geoColl) if x == ''] # filter out any blanks
    geoColl = [pm.PyNode(x) for x in geoColl]

    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
    else:
        rigFlip = -1.0

    # create all the parts
    rigGroup = pm.group(n='{}_piston_rig__grp__'.format(ctrlName), em=True)
    oTopRoot = pm.group(n='{}_top_piston__root__'.format(ctrlName), em=True)
    oBotRoot = pm.group(n='{}_bottom_piston__root__'.format(ctrlName), em=True)
    oTopControl = pm.spaceLocator(n='{}_top_piston__hook__'.format(ctrlName))
    oBotControl = pm.spaceLocator(n='{}_bottom_piston__hook__'.format(ctrlName))

    topJointRoot = create_rig_joint('{}_top_piston_jnt__grp__'.format(ctrlName))
    botJointRoot = create_rig_joint('{}_bottom_piston_jnt__grp__'.format(ctrlName))
    topJoint = create_rig_joint('{}_top_piston__jnt__'.format(ctrlName))
    botJoint = create_rig_joint('{}_bottom_piston__jnt__'.format(ctrlName))

    topPole = pm.spaceLocator(n='{}_top_piston__polevector__'.format(ctrlName))
    botPole = pm.spaceLocator(n='{}_bot_piston__polevector__'.format(ctrlName))
    topPole.tz.set(5.0)
    botPole.tz.set(5.0)

    chain_parent([partsGroup, rigGroup, oTopRoot, oTopControl, topJointRoot, topJoint])
    chain_parent([rigGroup, oBotRoot, oBotControl, botJointRoot, botJoint])
    pm.parent(topPole, oTopControl)
    pm.parent(botPole, oBotControl)

    oTopRoot.setTranslation(topPos, space='world')
    oTopRoot.setRotation(topRot, space='world')
    oBotRoot.setTranslation(botPos, space='world')
    oBotRoot.setRotation(topRot, space='world')
    topJoint.setTranslation(get_midpoint(topPos, botPos, 0.333), space='world')
    botJoint.setTranslation(get_midpoint(topPos, botPos, 0.666), space='world')

    topIK = pm.ikHandle(
            sj=topJointRoot, ee=topJoint,
            n='{}_top_piston__ikhandle__'.format(ctrlName),
            solver='ikRPsolver', snapHandleFlagToggle=False)
    botIK = pm.ikHandle(
            sj=botJointRoot, ee=botJoint,
            n='{}_bottom_piston__ikhandle__'.format(ctrlName),
            solver='ikRPsolver', snapHandleFlagToggle=False)
    topIK[0].v.set(0)
    botIK[0].v.set(0)
    topIK[1].v.set(0)
    botIK[1].v.set(0)
    #TODO: Add pole vectors
    pm.poleVectorConstraint(topPole, topIK[0])
    pm.poleVectorConstraint(botPole, botIK[0])
    topPole.localScale.set([0.2, 0.2, 0.2])
    botPole.localScale.set([0.2, 0.2, 0.2])

    # parent each ik handle to the opposite joint, so they point towards each other.
    topIK[0].setTranslation(botJointRoot.getTranslation(space='world'), space='world')
    botIK[0].setTranslation(topJointRoot.getTranslation(space='world'), space='world')
    pm.parent(topIK[0], oBotControl)
    pm.parent(botIK[0], oTopControl)

    for each in geoColl:
        each.tx.unlock()
        each.ty.unlock()
        each.tz.unlock()
        each.rx.unlock()
        each.ry.unlock()
        each.rz.unlock()
        each.sx.unlock()
        each.sy.unlock()
        each.sz.unlock()
        #TODO: I'm constraining the geo to not double-transform. Figure something more robust out.
        oCons = pm.parentConstraint(pm.PyNode('x__additive_rig__grp__'), each,
                n='{}__{}__{}_{}__parentconstraint__'.format(side, section, basename, each.name()),
                mo=True)
        oCons.setTranslation(totalBox.center(), space='world')
        pm.parent(oCons, constraintParent)
        oCons = pm.scaleConstraint(pm.PyNode('x__additive_rig__grp__'), each, mo=True,
                n='{}__{}__{}_{}__scaleconstraint__'.format(side, section, basename, each.name()))
        oCons.setTranslation(totalBox.center(), space='world')
        pm.parent(oCons, constraintParent)

    for each in geoColl:
        skin_geometry(
                [topJoint, botJoint], each,
                '{}_{}__skincluster__'.format(ctrlName, each.name())
                )

    oTopControl.getShape().overrideEnabled.set(True)
    oBotControl.getShape().overrideEnabled.set(True)
    if rigFlip == 1.0:
        oTopControl.getShape().overrideColor.set(6)
        oBotControl.getShape().overrideColor.set(6)
    else:
        oTopControl.getShape().overrideColor.set(13)
        oBotControl.getShape().overrideColor.set(13)
    #####bodyRig['vis2'].outColorR.connect(oTopControl.lodVisibility, force=True)
    #####bodyRig['vis2'].outColorR.connect(oBotControl.lodVisibility, force=True)

    # TODO: set up constraints. The piston will have 4 hooks into other parts of the rig:
    # These hooks will be defined in the guide. Or easy to expose so the rigger can manually hook them up.
    # 1. upper hook
    # 2. lower hook
    # 3. upper twist
    # 4. lower twist

    pm.parentConstraint(pm.PyNode('m__element__root_offset__ctrl__'), rigGroup,
            n='{}__{}__{}_riggrp__parentconstraint__'.format(side, section, basename),
            mo=True)
    pm.scaleConstraint(pm.PyNode('m__element__root_offset__ctrl__'), rigGroup,
            n='{}__{}__{}_riggrp__scaleconstraint__'.format(side, section, basename),
            mo=True)

    pm.delete(metaGuideRoot)


def build_jiggly_bits_rig(section, rigGuide, bodyRig):
    # init the parts of the rig guide
    parentObj = bodyRig['trajectory']
    mainRigGroup = bodyRig['riggroup']
    partsGroup = bodyRig['partsgroup']
    skinGroup = bodyRig['skingroup']
    constraintParent = pm.PyNode('x__constraints__grp__')

    metaGuideRoot = rigGuide.gid_root.outputs()[0]
    metaPivot = rigGuide.meta_jiggle_pivot.outputs()[0]

    basename = rigGuide.gid_basename.get()
    ctrlName = rigGuide.gid_ctrl_name.get()
    side = rigGuide.gid_side.get()
    frontOrBack = rigGuide.gid_front_side.get()

    geoColl = [pm.PyNode(x) for x in rigGuide.gid_geo.get().split(',')]
    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    if totalBox.center()[0] > 0.0:
        rigFlip = 1.0
    elif totalBox.center()[0] == 0.0:
        rigFlip = 1.0
    else:
        rigFlip = -1.0

    # create all the parts
    rigGroup = pm.group(n='{}_rig__grp__'.format(ctrlName), em=True)
    oControlRoot = pm.group(n='{}_door__ctrlroot__'.format(ctrlName), em=True)
    oControl = pm.spaceLocator(n='{}_door__ctrl__'.format(ctrlName))

    oControlRoot.setTranslation(metaPivot.getTranslation(space='world'), space='world')
    oControl.setTranslation(metaPivot.getTranslation(space='world'), space='world')
    oControlRoot.setRotation(metaPivot.getRotation(space='world'), space='world')
    oControl.setRotation(metaPivot.getRotation(space='world'), space='world')

    for each in geoColl:
        eachName = each.name()
        oCons = pm.parentConstraint(oControl, each, 
                n='{}__{}__{}_{}__parentconstraint__'.format(side, section, basename, eachName),
                mo=True)
        oCons.setTranslation(totalBox.center(), space='world')
        pm.parent(oCons, constraintParent)

    chain_parent([partsGroup, rigGroup, oControlRoot, oControl])

    pm.parentConstraint(pm.PyNode('m__element__root_offset__ctrl__'), rigGroup,
            n='{}__{}__{}_riggrp__parentconstraint__'.format(side, section, basename),
            mo=True)
    pm.scaleConstraint(pm.PyNode('m__element__root_offset__ctrl__'),
            rigGroup, n='{}__{}__{}_riggrp__scaleconstraint__'.format(side, section, basename),
            mo=True)

    oControl.getShape().overrideEnabled.set(True)
    if rigFlip == 1.0:
        oControl.getShape().overrideColor.set(6)
    else:
        oControl.getShape().overrideColor.set(13)
    #####bodyRig['vis2'].outColorR.connect(oControl.lodVisibility, force=True)

    # just grab the shape from the guide
    props_icon_lib.swap_shape(oControl, rigGuide)

    lockParams = ['.sx','.sy','.sz','.v']
    lock_main_params(oControl, pLocked=True, pChannelBox=False, pKeyable=False, pParams=lockParams)

    pm.delete(metaGuideRoot)
    #TODO: for every bit, have a skinning joint and a base joint. A lot of the geo will not be separated.


@undo
def build_rig():
    constraintParentName = 'x__constraints__grp__'
    if not pm.objExists(constraintParentName):
        constraintParent = pm.group(em=True, n=constraintParentName)
    else:
        constraintParent = pm.PyNode(constraintParentName)

    # find the existing GIDs from when the guide rig was built.
    gidColl = [x for x in pm.ls('*__gid__', type='transform') if pm.objExists(x.name() + '.gid_type')]

    # group each type of guides into a dictionary key.
    gidTypes = ['body', 'wheel', 'seat', 'door', 'steering', 'piston', 'jiggly']
    gids = { gidType: [x for x in gidColl if x.gid_type.get() == gidType] for gidType in gidTypes }

    # I assume that there will only be one body
    if not gids['body']:
        print('It seems there is no body guide rig. Quitting.')
        return False

    gid = gids['body'][0]
    # pass the wheel guides into the body to build the common middle controls.
    oBodyRig = build_body_rig('body', gid, gids['wheel'])

    for gid in gids['wheel']:
        build_wheel_rig('wheel', gid, oBodyRig)

    for gid in gids['seat']:
        build_seat_rig('seat', gid, oBodyRig)

    for gid in gids['door']:
        build_door_rig('door', gid, oBodyRig)

    for gid in gids['steering']:
        build_steering_rig('steering', gid, oBodyRig)

    for gid in gids['piston']:
        build_piston_rig('piston', gid, oBodyRig)

    for gid in gids['jiggly']:
        build_jiggly_bits_rig('jiggly', gid, oBodyRig)

    guideParentName = 'x__element__main_guide_group__grp__'
    if pm.objExists(guideParentName):
        pm.delete(guideParentName)

    ##### SET DEFAULT ATTRIBUTES. If not 0, then it will add an extra override attribute to the transform. #####
    #####oControls = pm.ls('*__ctrl__', type='transform')
    # Add all controls the selection set.
    #####[pm.PyNode('m__element__anim__set__').add(x) for x in oControls]

    # Digital Supervisor requires sandbox to be parented outside the rig. But the rig utils parent it automatically.
    #####if pm.objExists('sandbox'):
    #####if pm.PyNode('sandbox').getParent():
    #####pm.parent(pm.PyNode('sandbox'), None)


# Development workaround for PySide winEvent error (Maya 2014)
# Make sure the UI is deleted before recreating
try:
    car_tools
    car_tools.deleteLater()
except NameError:
    pass

# Create UI object
car_tools = CarRiggingTools()

# Delete the UI if errors occur to avoid causing winEvent and event errors
try:
    car_tools.create()
    car_tools.show()
except:
    car_tools.deleteLater()
    traceback.print_exc()
