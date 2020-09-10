#!/usr/bin/env mayapy
# encoding: utf-8

'''
Rigmarole Props Rigging Tools.
A collection of scripts and utilities for rigging props in Autodesk Maya
Chris Lesage - chris@rigmarolestudio.com

Brainstorm:
- Control icon tool
- Lock/unlock params
- Some kind of renaming tools
- Change a constraint to another controller (a bit specific)
- Update constraints on selected objects (When pivot or control moves)
- Shell Skinning and copy weights utilities
- Create a ribbon GUI (fixed-length or stretchy)
- LERP and SLERP any attributes. This is part of the ribbon setup, but can interpolate any attribute you like.
- Create follicles (no ribbon, just follicles on the surface you specify)

'''

__version__ = '0.4'
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

import tenave
import tenave.props_icon_lib as props_icon_lib
import tenave.car_autorig

import os
import posixpath
import math
#import envtools
#import json
from functools import wraps
from mgear.core import attribute

##################################
###### PySide UI Functions #######
##################################


def undo(func):
    """Puts the wrapped func into a single Maya Undo action, then
    ends the chunk when the function enters the finally: block
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


class PropRiggingTools(QtWidgets.QDialog):

    def __init__(self, parent=maya_main_window()):
        super(PropRiggingTools, self).__init__(parent)


    def create(self):
        """Create the UI"""
        self.setWindowTitle('Prop Rigging Tools v' + __version__)
        self.resize(100, 400)
        self.setWindowFlags(QtCore.Qt.Tool)
        self.create_controls()
        self.create_layout()


    def create_controls(self):
        """Create the widgets and signals for the dialog"""

        colorRed = '745a54'
        colorBlue = '5d5d70'
        colorGreen = '597a59'
        colorGrey = '606060'
        colorDarkGrey = '222'
        borderStyle = 'border:1px solid #3a3a3a'

        self.buttonAndFunctions = [
                # name, function, group number
                ['1. Build Basic Guide',      self.buildGuideBtn_pressed,        1, colorGrey],
                ['2. Rig Basic Controls',     self.buildControlsBtn_pressed,     1, colorGrey],
                ['Make Controls Square',      self.makeCtrlSquareBtn_pressed,    1, colorGrey],
                ['Lock Scale and Vis',        self.lockScaleVisBtn_pressed,      1, colorGrey],
                ['Create Control Set',        self.cleanupPropRigBtn_pressed,    1, colorGreen],
                ['Set Default Values',        self.setDefault_pressed,    1, colorGreen],

                ['Make Control at Bottom',    self.controlAtBottomBtn_pressed,   2, colorGrey],
                ['Make Control at Centroid',  self.controlAtCentroidBtn_pressed, 2, colorGrey],
                ['Make a Root',               self.makeRootBtn_pressed,          2, colorGrey],
                ['Chain Parent',              self.chainParentBtn_pressed,       2, colorGrey],
                ['Reorder Hierarchy',         self.reorderHierarchyBtn_pressed,  2, colorGrey],

                ['Select Skin Influences',    self.selectInfluencesBtn_pressed,  3, colorGrey],
                ['Reset Skin',                self.resetSkinBtn_pressed,         3, colorGrey],
                #['Lock params  [...]',       self.lockParamsBtn_pressed,        3, colorDarkGrey],
                #['Renaming Tool  [...]',     self.renameToolBtn_pressed,        3, colorDarkGrey],
                ['Hide/Show Joints below selected', self.hideAllBonesBtn_pressed, 3, colorGrey],

                ['Vehicle Autorigger  [...]', self.vehicleAutorigBtn_pressed,    4, colorBlue],
                #['Create ribbon tool  [...]', self.createRibbonBtn_pressed,      4, colorDarkGrey],
                #['Create follicles  [...]',   self.createFolliclesBtn_pressed,   4, colorDarkGrey],
                #['LERP/SLERP tool  [...]',    self.lerpSlerpBtn_pressed,         4, colorDarkGrey],
        ]

        self.buttons = {}
        for buttonName, buttonFunction, _, bgColor in self.buttonAndFunctions:
            self.buttons[buttonName] = QtWidgets.QPushButton(buttonName)
            self.buttons[buttonName].clicked.connect(buttonFunction)
            self.buttons[buttonName].setFixedHeight(28)
            self.buttons[buttonName].setStyleSheet(
                    'padding:4px; text-align:center; color:#ddd; background-color:#{};'.format(bgColor)
                    )
            #self.buttons[buttonName].setStyleSheet('padding:4px; text-align:center; color:#ddd;')


    def create_layout(self):
        """ Create the layouts and add widgets """

        buttons1 = [button for button, _, groupNumber, _ in self.buttonAndFunctions if groupNumber == 1]
        buttons2 = [button for button, _, groupNumber, _ in self.buttonAndFunctions if groupNumber == 2]
        buttons3 = [button for button, _, groupNumber, _ in self.buttonAndFunctions if groupNumber == 3]
        buttons4 = [button for button, _, groupNumber, _ in self.buttonAndFunctions if groupNumber == 4]
        buttons5 = [button for button, _, groupNumber, _ in self.buttonAndFunctions if groupNumber == 5]

        mainLayout = QtWidgets.QVBoxLayout()
        mainLayout.setContentsMargins(*[6]*4)

        flatStyle = True  # False draws a border around the whole section
        groupFont = QtGui.QFont('Helvetica Neue', 8, QtGui.QFont.Bold)
        labelFont=QtGui.QFont()
        #labelFont.setBold(True)
        groupPadding = 1  # padding at top and bottom of each section

        group1 = QtWidgets.QGroupBox('Basics')
        group1.setStyleSheet('padding: 20px 0px 0px 0px')
        group1.setFlat(flatStyle)
        group1.setFont(groupFont)

        group2 = QtWidgets.QGroupBox('Basic Rigging')
        group2.setStyleSheet('padding: 20px 0px 0px 0px')
        group2.setFlat(flatStyle)
        group2.setFont(groupFont)

        group3 = QtWidgets.QGroupBox('Utilities')
        group3.setStyleSheet('padding: 20px 0px 0px 0px')
        group3.setFlat(flatStyle)
        group3.setFont(groupFont)

        group4 = QtWidgets.QGroupBox('Advanced Rigging')
        group4.setStyleSheet('padding: 20px 0px 0px 0px')
        group4.setFlat(flatStyle)
        group4.setFont(groupFont)

        buttonLayout1 = QtWidgets.QVBoxLayout()
        for buttonName in buttons1:
            buttonLayout1.addWidget(self.buttons[buttonName])
        buttonLayout1.setContentsMargins(*[2]*4)

        buttonLayout2 = QtWidgets.QVBoxLayout()
        for buttonName in buttons2:
            buttonLayout2.addWidget(self.buttons[buttonName])
        buttonLayout2.setContentsMargins(*[2]*4)

        buttonLayout3 = QtWidgets.QVBoxLayout()
        for buttonName in buttons3:
            buttonLayout3.addWidget(self.buttons[buttonName])
        buttonLayout3.setContentsMargins(*[2]*4)

        buttonLayout4 = QtWidgets.QVBoxLayout()
        for buttonName in buttons4:
            buttonLayout4.addWidget(self.buttons[buttonName])
        buttonLayout4.setContentsMargins(*[2]*4)

        group1.setLayout(buttonLayout1)
        group2.setLayout(buttonLayout2)
        group3.setLayout(buttonLayout3)
        group4.setLayout(buttonLayout4)

        mainLayout.addWidget(group1)
        mainLayout.addWidget(group2)
        mainLayout.addWidget(group3)
        mainLayout.addWidget(group4)
        mainLayout.addStretch()

        self.setLayout(mainLayout)


    #--------------------------------------------------------------------------
    # SLOTS
    #--------------------------------------------------------------------------

    def templateBtn_pressed(self):
        # def do() a tip from Mattias so I don't have to use lambda to pass
        # arguments to a button signal. But I don't know why it works.
        def do():
            sender = self.sender()
            print('{} button pressed.'.format(sender.text()))
            # do things here
        return do


    # another template function
    def anotherBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))


    def buildGuideBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        build_basic_guides()
    

    def buildControlsBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        build_base_rig()
    

    def makeCtrlSquareBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        make_ctrl_square()


    def lockScaleVisBtn_pressed(self):
        sender = self.sender()
        print('\n{}\n"{}" pressed'.format('='*20, sender.text()))
        lock_scale_vis()

    def cleanupPropRigBtn_pressed(self):
        sender = self.sender()
        print('\n{}\n"{}" pressed'.format('='*20, sender.text()))

        add_controls_to_set('controls_set')
        #TODO: Define some quality checks for a given pipeline
        quality_check()

    def setDefault_pressed(self):
        sender = self.sender()
        print('\n{}\n"{}" pressed'.format('='*20, sender.text()))
        set_default_values()

    def makeRootBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        make_a_root(pm.selected(type='transform'))
    

    def reorderHierarchyBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        reorder_collection(pm.selected())


    def chainParentBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        if pm.selected(): chain_parent(pm.selected())

    
    def controlAtBottomBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        place_control_at_bottom(pm.selected())
    

    def controlAtCentroidBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        #TODO: Add a checkbox for useBiggest
        place_control_in_bb_center(pm.selected(), useBiggest=False)


    def selectInfluencesBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        select_skin_influences(pm.selected())
    

    def resetSkinBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        reset_skin(pm.selected())
    

    def lockParamsBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        #TODO:
    

    def renameToolBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        #TODO:
    

    def hideAllBonesBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        hide_all_bones(pm.selected())


    def vehicleAutorigBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        import car_autorig
    

    def createRibbonBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        #TODO:
    

    def createFolliclesBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        #TODO:
    

    def lerpSlerpBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        #TODO:


    def importLatestModelBtn_pressed(self):
        sender = self.sender()
        print('"{}" pressed'.format(sender.text()))
        #TODO:


#################################
####### Rigging Functions #######
#################################


@undo
def build_basic_guides():
    ##### 1. BUILD THE BASIC GUIDE CONTROLS #####
    #TODO: If user has a selection, size the controls to match? What about position?
    oGlobal = props_icon_lib.create_control_icon('arrowBox', 'world_ctl', [10.0, 1.0, 10.0])
    oLocal = props_icon_lib.create_control_icon('square', 'master_C0_ctl', [9.0, 1.0, 9.0], offset=[0, 0.2, 0])
    oBody = props_icon_lib.create_control_icon('square', 'COG_C0_ctl', [8.0, 1.0, 8.0])
    oBody.setTranslation([0.0, 3.0, 0.0])
    chain_parent([oGlobal, oLocal, oBody])
    reorder_outliner_nicely()

    oGlobal.getShape().overrideEnabled.set(True)
    oLocal.getShape().overrideEnabled.set(True)
    oBody.getShape().overrideEnabled.set(True)

    oGlobal.getShape().overrideColor.set(13)
    oLocal.getShape().overrideColor.set(22)
    oBody.getShape().overrideColor.set(24)


@undo
def build_base_rig():
    ##### 2. BUILD THE BASE RIG #####
    #TODO: Generate my own generic shapes here.
    #TODO: Better naming conventions
    #TODO: If the guide doesn't exist, just build a rig with all controls at 0,0,0. Don't be an ass about it.
    #nSRT = 'globalsrt'
    nGlobal = 'world_ctl'
    nLocal = 'master_C0_ctl'
    nBody = 'COG_C0_ctl'

    if not pm.objExists("Rig"):
        rigGroup = pm.group(em=True, n='Rig')
    else:
        rigGroup = pm.PyNode("Rig")

    if pm.objExists('RigLayer'):
        pm.delete('RigLayer')
    if pm.objExists('GeoLayer'):
        pm.delete('GeoLayer')
    oLayer = pm.createDisplayLayer('Rig', n='RigLayer', number=1, nr=True)
    oLayer.color.set(14)
    oLayer = pm.createDisplayLayer(pm.ls('Geo'), n='GeoLayer', number=1, nr=True)
    oLayer.color.set(7)

    # Find or create the guide controls
    #if pm.objExists(nSRT):
    #    oSRT = pm.PyNode(nSRT)
    #else:
    #    oSRT = pm.spaceLocator(n='globalsrt')
    if pm.objExists(nGlobal):
        oGlobal = pm.PyNode(nGlobal)
    else:
        oGlobal = props_icon_lib.create_control_icon('arrowBox', 'world_ctl', [10.0, 1.0, 10.0])
    if pm.objExists(nLocal):
        oLocal = pm.PyNode(nLocal)
    else:
        oLocal = props_icon_lib.create_control_icon('square', 'master_C0_ctl', [9.0, 1.0, 9.0])

    localBB = oLocal.getBoundingBox()
    localWidth = localBB.width() - 1.0
    localDepth = localBB.depth() - 1.0
    oLocal2 = props_icon_lib.create_control_icon(
            'square',
            'local_C0_ctl',
            [localWidth, 1.0, localDepth],
            offset = [0.0, 0.2, 0.0],
            )
    oLocal2.setTranslation(oLocal.getTranslation(space='world'), space='world')

    if pm.objExists(nBody):
        oBody = pm.PyNode(nBody)
    else:
        oBody = props_icon_lib.create_control_icon('square', 'COG_C0_ctl', [8.0, 1.0, 8.0])
        oBody.setTranslation([0.0, 3.0, 0.0])

    bodyBB = oBody.getBoundingBox()
    bodyWidth = bodyBB.width() - 1.0
    bodyDepth = bodyBB.depth() - 1.0
    oBody2 = props_icon_lib.create_control_icon(
            'square',
            'COG_C1_ctl',
            [bodyWidth, 1.0, bodyDepth],
            offset = [0.0, 0.0, 0.0],
            )
    oBody2.setTranslation(oBody.getTranslation(space='world'), space='world')

    #chain_parent([rigGroup, oSRT, oGlobal, oLocal, oBody, oBody2])
    chain_parent([rigGroup, oGlobal, oLocal, oLocal2, oBody, oBody2])
    make_a_root([oGlobal, oLocal, oLocal2, oBody, oBody2])

    pm.parentConstraint(oBody2, "Geo", mo=True)
    pm.scaleConstraint(oBody2, "Geo", mo=True)
    
    oGlobal.getShape().overrideEnabled.set(True)
    oLocal.getShape().overrideEnabled.set(True)
    oLocal2.getShape().overrideEnabled.set(True)
    oBody.getShape().overrideEnabled.set(True)
    oBody2.getShape().overrideEnabled.set(True)

    oGlobal.getShape().overrideColor.set(13)
    oLocal.getShape().overrideColor.set(22)
    oLocal2.getShape().overrideColor.set(22)
    oBody.getShape().overrideColor.set(24)
    oBody2.getShape().overrideColor.set(24)


@undo
def make_ctrl_square():
    # This assumed the base controls were already built
    geoColl = pm.selected()
    totalBox = dt.BoundingBox()
    if geoColl:
        [ totalBox.expand(x.getBoundingBox(space='world').min()) for x in geoColl ]
        [ totalBox.expand(x.getBoundingBox(space='world').max()) for x in geoColl ]
    else:
        totalBox.expand([5.0, 1.0, 5.0])
        totalBox.expand([-5.0, 1.0, -5.0])

    width = totalBox.width()
    depth = totalBox.depth()
    heightFactor = (((width * 1.2) - (width * 1.1)) + ((depth * 1.2) - (depth * 1.1))) * 0.1
    
    shPosition = props_icon_lib.create_control_icon(
            'arrowBox', 'positionShape',
            [width * 1.2, 1.0, depth * 1.2], offset=[totalBox.center()[0], 0, totalBox.center()[2]])
    shTrajectory = props_icon_lib.create_control_icon(
            'square', 'trajectoryShape',
            [width * 1.1, 1.0, depth * 1.1], offset=[totalBox.center()[0], heightFactor, totalBox.center()[2]])

    props_icon_lib.swap_shape(pm.PyNode('world_ctl'), shPosition)
    props_icon_lib.swap_shape(pm.PyNode('master_C0_ctl'), shTrajectory)
    pm.select(geoColl)


@undo
def lock_scale_vis():
    # Locks scale and visibility for all controls but "world_ctl"
    oControls = pm.ls('*_ctl', type='transform')
    oGlobal = pm.PyNode("world_ctl")

    oGlobal.attr("v").unlock()
    oGlobal.attr("v").setKeyable(True)
    oGlobal.attr("v").lock()

    for each in oControls:
        if each != oGlobal:
            for i in ['sx','sy','sz','v']:
                each.attr(i).unlock()
                each.attr(i).setKeyable(True)
                each.attr(i).lock()


@undo
def add_controls_to_set(setName):
    # Add all ctrls to the control set.
    oControls = pm.ls('*_ctl', type='transform')
    if not pm.objExists(setName):
        selSet = pm.createNode('objectSet', n=setName)
    else:
        selSet = pm.PyNode(setName)
    setMembers = selSet.members()

    controlsToAdd = [x for x in oControls if x not in setMembers]
    controlsToRemove = [x for x in selSet.members() if not x.endswith('_ctl')]
    [selSet.remove(x) for x in controlsToRemove]
    [selSet.add(x) for x in controlsToAdd]

    if controlsToAdd:
        print('Added {} controls to selection set:'.format(len(controlsToAdd)))
        for each in controlsToAdd:
            print('  {}'.format(each.name()))

    if controlsToRemove:
        print('Removed {} non-controls from selection set:'.format(len(controlsToRemove)))
        for each in controlsToRemove:
            print('  {}'.format(each.name()))




def quality_check():
    ### Check that all controls are at 0,0,0 in translation and rotation
    ### Check that visibility is locked and hidden on all controls
    ### Check that all geometry is at 0,0,0,0,0,0,1,1,1
    ### Report (but don't force) that scaling is unlocked on controllers. It is allowed, but rarely needed.
    ### Check that there are no constraints in the geometry hierarchy (if desired. Ryan Porter figured out that unparenting aimConstraints helped speed up the rig quite a bit.)

    pass


def remove_all_materials():
    """ This removes all materials by first assigning all geometry to Lambert1. It then runs
    the MEL command from the Hypershade to remove unused materials and shading groups. """

    allGeo = [x.getTransform() for x in pm.ls(type=['mesh', 'nurbsSurface'])]
    # restore the user's previous selection after running this.
    # The MEL command requires a selection I think.
    oldSel = pm.selected()
    pm.select(allGeo)
    pm.hyperShade(assign='lambert1')
    #TODO: debug this to make sure it is always "hyperShadePanel1"
    pm.mel.hyperShadePanelMenuCommand("hyperShadePanel1", "deleteUnusedNodes")
    pm.select(oldSel)


@undo
def set_default_values():
    # Set default values for custom attributes to what they are currently set to
    allControls = pm.PyNode('controls_set').members()
    allControls.extend([x for x in pm.ls('*_ctl', type='transform')])

    for oNode in list(set(allControls)):
        # You can't set default values on "non-dynamic attributes". Each shit Maya.
        # So skip all the SRT, v and ro attributes. Maybe there is a flag to filter them.
        params = [
                x for x in oNode.listAttr(keyable=True)
                if not x.attrName() in ['v','tx','ty','tz','rx','ry','rz','sx','sy','sz','ro']
                ]
        for param in params:
            try:
                pm.addAttr(param, defaultValue=param.get(), edit=True)
            except:
                pm.warning('failed to set default value on {}'.format(param))

@undo
def connect_visibility(oColl, level):
    ##### CONNECT VISIBILITY #####
    # 0 is main
    # 1 is important basic controllers
    # 2 is secondary controls, offsets and jiggly bits
    # add 3 if we need more resolution or for minor fixer controls...
    conditionNode = 'm_element_position_ctrl_controlVis_{}_condition'.format(level)

    if pm.objExists(conditionNode):
        visSwitch = pm.PyNode(conditionNode)
    else:
        visSwitch = pm.createNode('condition', n=conditionNode)
    visSwitch.operation.set(3) # greater than or equal
    visSwitch.secondTerm.set(level)
    visSwitch.colorIfTrueR.set(1)
    visSwitch.colorIfFalseR.set(0)
    pm.PyNode('m_element_position_ctrl').controlVis.connect(visSwitch.firstTerm, force=True)

    for each in oColl:
        each.lodVisibility.unlock()
        visSwitch.outColorR.connect(each.lodVisibility, force=True)


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


@undo
def make_a_root(oColl):
    newSuffix = 'npo'

    for each in oColl:
        try:
            suffix = each.name().split('_')[-1]
            #cutsuffix = '_{}_'.format(suffix)
        except:
            suffix, cutsuffix = '', ''
        oRoot = pm.group(n=each.name().replace(suffix,'') + '{}'.format(newSuffix), em=True)
        #TODO: Fix this logic. But in the meantime, hack away any extra underscores
        #for i in xrange(4):
        #    oRoot.rename(oRoot.name().replace('__','_'))
        oRoot.setTranslation(each.getTranslation(space='world'), space='world')
        oRoot.setRotation(each.getRotation(space='world'), space='world')
        try:
            pm.parent(oRoot, each.getParent())
        except:
            pass
        pm.parent(each, oRoot)
        pm.setAttr(oRoot.v, keyable=False, cb=False)
        oRoot.v.lock()
    #TODO: Find a way to expand the outliner automatically afterwards.
    pm.select(oColl)


def reorder_outliner_nicely():
    # reorder the hierarchy so cameras are on top. Otherwise there is a
    # dumb bug where it is harder to select the top node in the outliner.
    #TODO: Fix this to work generically. Just move cameras to top
    return False
    for each in [x.getParent() for x in pm.ls(type='camera')] + [pm.PyNode('root')] + sandbox:
        pm.reorder(each, back=True)


def add_a_keyable_attribute(myObj, oDataType, oParamName, oMin=None, oMax=None, oDefault=0.0):
    """adds an attribute that shows up in the channel box; returns the newly created attribute"""
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
    """adds a string attribute into "extra" attributes. Useful for meta information"""
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
    """a simple skinCluster command with my preferred prefs."""
    pm.skinCluster(
            oJoints,
            oGeo,
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


@undo
def reset_skin(oColl):
    # first, check for shapes vs. transforms. Let the user pick any mix
    gatherShapes = [x.getParent() for x in oColl if type(x) == pm.nodetypes.Mesh]
    gatherTransforms = [x for x in oColl if type(x) == pm.nodetypes.Transform if x.getShape()]
    firstFilter = gatherTransforms + gatherShapes
    geoFilter = [x for x in firstFilter if type(x.getShape()) == pm.nodetypes.Mesh]

    for geo in geoFilter:
        _skinCluster = [x for x in geo.getShape().inputs() if type(x) == pm.nodetypes.SkinCluster][0]
        skinJointList = pm.listConnections(_skinCluster.matrix, t='joint')

        bindPose = pm.listConnections(skinJointList[0].name(), d=True, s=False, t='dagPose')

        if not bindPose == None:
            if not (pm.referenceQuery(bindPose[0], inr=True)):
                pm.delete(bindPose[0])

        sourceGeo = pm.skinCluster(_skinCluster, q=True, g=True)[0]
        pm.skinCluster(_skinCluster, e=True, ubk=True)
        pm.select(skinJointList, r=True)
        pm.skinCluster(skinJointList, sourceGeo, ibp=True, tsb=True)


@undo
def select_skin_influences(oColl):
    """Takes transform selection and selects skin joint influences."""
    pm.select(None)
    resultsFound = False
    for geo in oColl:
        if type(geo) == pm.nodetypes.Transform:
            if geo.getShape():
                _skinCluster = [x for x in geo.getShape().inputs() if type(x) == pm.nodetypes.SkinCluster][0]
                if _skinCluster:
                    skinJointList = pm.listConnections(_skinCluster.matrix, t='joint')
                    pm.select(skinJointList, add=True)
                    resultsFound = True
    if not resultsFound:
        print('no skin clusters were found.')
        pm.select(oColl) # restore original selection if nothing found


@undo
def hide_all_bones(oColl):
    """ This function toggles visibility of all bones under the selected nodes """
    allJoints = [] # collect all joints in a flat list
    for each in oColl:
        allJoints.extend(each.getChildren(ad=True, type='joint'))

    # measure the state of all the joints
    jointState = list(set([x.drawStyle.get() for x in allJoints]))

    # if some joints are visible and others are not, then make them all visible
    if 2 in jointState or 1 in jointState:
        print('visible')
        [jnt.drawStyle.set(0) for jnt in allJoints]
    else:
        print('hidden')
        [jnt.drawStyle.set(2) for jnt in allJoints]


def bb_volume(obj):
    oBB = obj.getBoundingBox()
    return oBB.width() * oBB.height() * oBB.depth()


def group_geometry_masses(geoColl):
    """ This function compares each geometry in a collection for bounding box intersection.
    If they ARE intersecting, they are grouped together. The groups are then returned.
    eg. A intersects with B. B intersects with A and C. C intersects with B.
    [ABC] is a single group. Even if A and C do not intersect. """
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


def constrain_geo(oControl, geoColl):
    for each in geoColl:
        oCons = pm.parentConstraint(oControl, each, mo=True, n='{}_parentconstraint'.format(each.name()))
        oCons2 = pm.scaleConstraint(oControl, each, mo=True, n='{}_scaleconstraint'.format(each.name()))


def delete_constraints(oColl, filter=None):
    #TODO: Write a way to filter which constraints to delete
    #TODO: Add this as a button to Utilities group
    consTypes = {
            'parent': pm.nodetypes.ParentConstraint,
            'scale': pm.nodetypes.ScaleConstraint,
            'orient': pm.nodetypes.OrientConstraint,
            'point': pm.nodetypes.PointConstraint,
            'aim': pm.nodetypes.AimConstraint,
            }
    ### SNIPPET: Delete constraints on selected
    for each in oColl:
        for consKey, consType in consTypes.items():
            constraints = list(set([x for x in each.inputs() if type(x) == consType]))
            pm.delete(constraints)


@undo
def place_control_at_bottom(geoColl):
    """ place a control at the ground and in the center of the biggest geo """
    #TODO: If nothing selected, just place a controller at origin?
    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]

    sizeComp = [x.getBoundingBox().width() * x.getBoundingBox().height() * x.getBoundingBox().depth() for x in geoColl]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    controlName = 'm__{}__ctrl'.format(biggestGeo.name().split('|')[-1].split('_')[1])
    oControl = pm.spaceLocator(n=controlName)
    oPos = biggestGeo.getBoundingBox().center()
    oPos[1] = totalBox.min()[1] # a float value that defaults to 0.0

    oControl.setTranslation(oPos, space='world')
    constrain_geo(oControl, geoColl)
    pm.setAttr(oControl.v, keyable=False, cb=False)
    oControl.v.lock()
    pm.select(oControl)


@undo
def place_control_in_bb_center(geoColl, useBiggest=False):
    """ place a control in the center of the geo. Or use the biggest geometry """
    totalBox = dt.BoundingBox()
    [ totalBox.expand(x.getBoundingBox().min()) for x in geoColl ]
    [ totalBox.expand(x.getBoundingBox().max()) for x in geoColl ]
    
    sizeComp = [
            x.getBoundingBox().width() * x.getBoundingBox().height() * x.getBoundingBox().depth()
            for x in geoColl
            ]
    biggestGeo = geoColl[sizeComp.index(max(sizeComp))]

    oControl = pm.spaceLocator(n='m_{}'.format(biggestGeo.name().replace('_geo','_ctl')))
    if useBiggest:
        oPos = biggestGeo.getBoundingBox().center()
    else:
        oPos = totalBox.center()
    oControl.setTranslation(oPos, space='world')
    constrain_geo(oControl, geoColl)
    pm.setAttr(oControl.v, keyable=False, cb=False)
    oControl.v.lock()
    pm.select(oControl)


@undo
def reorder_collection(oColl):
    for each in oColl:
        pm.reorder(each, back=True)


@undo
def chain_parent(oColl):
    for oParent, oChild in zip(oColl[0:-1], oColl[1:]):
        try:
            pm.parent(oChild, None)
            pm.parent(oChild, oParent)
        except:
            continue
    pm.select(oColl) # restore original selection


def pnt_ws(pnt):
    """ dumb function to help bring line width down """
    return pnt.getPosition(space='world')


def get_midpoint(vecA, vecB, weight=0.5):
    """Helper to get middle point between two vectors. Weight is 0.0 to 1.0 blend between the two.
    So for example, 0.0 would return the position of oObject1. 1.0 would be oObject2. 0.5 is halfway."""
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
    """A function for creating a C-shaped ease-in-fast-out curve. (Or reverse.)"""
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


def swap_shape(oParent, oChild):
    shapeName = oParent.getShape().name()
    shapeColor = oParent.getShape().overrideColor.get()
    oChild.getShape().overrideEnabled.set(True)
    oChild.getShape().overrideColor.set(shapeColor)
    pm.delete(oParent.getShapes())
    if oChild.getParent() != oParent:
        pm.parent(oChild, oParent)
    pm.makeIdentity(oChild, apply=True, t=1, r=1, s=1)
    pm.parent(oChild.getShape(), oParent, shape=True, relative=True)
    pm.delete(oChild)


# Development workaround for PySide winEvent error (Maya 2014)
# Make sure the UI is deleted before recreating
try:
    props_tools_ui
    props_tools_ui.deleteLater()
except NameError:
    pass

# Create UI object
props_tools_ui = PropRiggingTools()
# Delete the UI if errors occur to avoid causing winEvent and event errors
try:
    props_tools_ui.create()
    props_tools_ui.show()
except:
    props_tools_ui.deleteLater()
    traceback.print_exc()
