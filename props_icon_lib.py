#!/usr/bin/env mayapy
# encoding: utf-8

import pymel.core as pm
import pymel.core.datatypes as dt
import maya.cmds as cmds
import maya.OpenMaya as om
import maya.OpenMayaUI as omui

import os
import posixpath
import math


def pnt_ws(pnt, pSpace='world'):
    """Dumb function to help bring line width down."""
    return pnt.getPosition(space=pSpace)


def icon_library(iconKey):
    #TODO: Store this library somewhere (a file, or JSON or something.)
    # This is a nested dictionary of information that procedurally draws controller icons.
    # It is used by create_control_icon()
    controlIconLib = {}
    '''
    controlIconLib['iconName'] = {}
    controlIconLib['iconName']['description'] = 'description here'
    controlIconLib['iconName']['points'] = [[],[],[]]
    controlIconLib['iconName']['degree'] = 1
    controlIconLib['iconName']['closed'] = True
    '''

    ###
    controlIconLib['arrowCircle'] = {}
    controlIconLib['arrowCircle']['description'] = '4 directional arrows for the master SRT controller'
    controlIconLib['arrowCircle']['points'] = [
            [0.0, 0.0, -0.77],
            [0.17, 0.0, -0.6],
            [0.09, 0.0, -0.6],
            [0.09, 0.0, -0.5],
            [0.16, 0.0, -0.48],
            [0.24, 0.0, -0.44],
            [0.31, 0.0, -0.4],
            [0.35, 0.0, -0.36],
            [0.4, 0.0, -0.31],
            [0.44, 0.0, -0.24],
            [0.48, 0.0, -0.16],
            [0.5, 0.0, -0.09],
            [0.6, 0.0, -0.09],
            [0.6, 0.0, -0.17],
            [0.77, 0.0, -0.0],
            [0.6, 0.0, 0.17],
            [0.6, 0.0, 0.09],
            [0.5, 0.0, 0.09],
            [0.48, 0.0, 0.16],
            [0.44, 0.0, 0.24],
            [0.4, 0.0, 0.31],
            [0.36, 0.0, 0.35],
            [0.31, 0.0, 0.4],
            [0.24, 0.0, 0.44],
            [0.16, 0.0, 0.48],
            [0.09, 0.0, 0.5],
            [0.09, 0.0, 0.6],
            [0.17, 0.0, 0.6],
            [-0.0, 0.0, 0.77],
            [-0.17, 0.0, 0.6],
            [-0.09, 0.0, 0.6],
            [-0.09, 0.0, 0.5],
            [-0.16, 0.0, 0.48],
            [-0.24, 0.0, 0.44],
            [-0.31, 0.0, 0.4],
            [-0.35, 0.0, 0.36],
            [-0.4, 0.0, 0.31],
            [-0.44, 0.0, 0.24],
            [-0.48, 0.0, 0.16],
            [-0.5, 0.0, 0.09],
            [-0.6, 0.0, 0.09],
            [-0.6, 0.0, 0.17],
            [-0.77, 0.0, 0.0],
            [-0.6, 0.0, -0.17],
            [-0.6, 0.0, -0.09],
            [-0.5, 0.0, -0.09],
            [-0.48, 0.0, -0.16],
            [-0.44, 0.0, -0.24],
            [-0.4, 0.0, -0.31],
            [-0.36, 0.0, -0.35],
            [-0.31, 0.0, -0.4],
            [-0.24, 0.0, -0.44],
            [-0.16, 0.0, -0.48],
            [-0.09, 0.0, -0.5],
            [-0.09, 0.0, -0.6],
            [-0.17, 0.0, -0.6],
            [-0.0, 0.0, -0.77],
            ]
    controlIconLib['arrowCircle']['degree'] = 1
    controlIconLib['arrowCircle']['closed'] = True

    ###
    controlIconLib['arrowBox'] = {}
    controlIconLib['arrowBox']['description'] = '4 directional arrows for the master SRT controller'
    controlIconLib['arrowBox']['points'] = [
            [0.0, 0.0, -0.77],
            [0.17, 0.0, -0.6],
            [0.09, 0.0, -0.6],
            [0.09, 0.0, -0.5],
            [0.5, 0.0, -0.5],
            [0.5, 0.0, -0.09],
            [0.6, 0.0, -0.09],
            [0.6, 0.0, -0.17],
            [0.77, 0.0, -0.0],
            [0.6, 0.0, 0.17],
            [0.6, 0.0, 0.09],
            [0.5, 0.0, 0.09],
            [0.5, 0.0, 0.5],
            [0.09, 0.0, 0.5],
            [0.09, 0.0, 0.6],
            [0.17, 0.0, 0.6],
            [-0.0, 0.0, 0.77],
            [-0.17, 0.0, 0.6],
            [-0.09, 0.0, 0.6],
            [-0.09, 0.0, 0.5],
            [-0.5, 0.0, 0.5],
            [-0.5, 0.0, 0.09],
            [-0.6, 0.0, 0.09],
            [-0.6, 0.0, 0.17],
            [-0.77, 0.0, 0.0],
            [-0.6, 0.0, -0.17],
            [-0.6, 0.0, -0.09],
            [-0.5, 0.0, -0.09],
            [-0.5, 0.0, -0.5],
            [-0.09, 0.0, -0.5],
            [-0.09, 0.0, -0.6],
            [-0.17, 0.0, -0.6],
            [-0.0, 0.0, -0.77],
            ]
    controlIconLib['arrowBox']['degree'] = 1
    controlIconLib['arrowBox']['closed'] = True

    ###
    controlIconLib['linePlusCircle'] = {}
    controlIconLib['linePlusCircle']['description'] = 'A line of a given length, with a circle on the end'
    #TODO: pLen is the length of the line. Find a way to work procedural aspects into the function
    #TODO: Build things more procedurally when possible. For example, it would be nice to scale the circle.
    pLen = 10.0
    controlIconLib['linePlusCircle']['points'] = [
            [pLen + -1.4331, -0.0, 0.0],
            [pLen + -1.0133000000000001, -0.0, -1.0133000000000001],
            [pLen + -0.0, 0.0, -1.4331],
            [pLen + 1.0133000000000001, 0.0, -1.0133000000000001],
            [pLen + 1.4331, 0.0, -0.0],
            [pLen + 1.0133000000000001, 0.0, 1.0133000000000001],
            [pLen + 0.0, -0.0, 1.4331],
            [pLen + -1.0133000000000001, -0.0, 1.0133000000000001],
            [pLen + -1.4331, -0.0, 0.0], [0.00, 0.00, 0.00]
            ]
    controlIconLib['linePlusCircle']['degree'] = 1
    controlIconLib['linePlusCircle']['closed'] = False

    ###
    controlIconLib['segmentedCircle'] = {}
    controlIconLib['segmentedCircle']['points'] = [
            [-10.0, 0.0, 0.0],
            [-7.0, 0.0, -7.0],
            [0.0, 0.0, -10.0],
            [7.0, 0.0, -7.0],
            [10.0, 0.0, 0.0],
            [7.0, 0.0, 7.0],
            [0.0, 0.0, 10.0],
            [-7.0, 0.0, 7.0],
            [-10.0, 0.0, 0.0]
            ]
    controlIconLib['segmentedCircle']['degree'] = 1
    controlIconLib['segmentedCircle']['closed'] = True

    ###
    controlIconLib['box'] = {}
    controlIconLib['box']['description'] = 'a cube, scalable on all axes with a center pivot'
    scaleX = 1
    scaleY = 1
    scaleZ = 1
    controlIconLib['box']['points'] = [
            [ scaleX * 0.5, scaleY * 0.5, scaleZ * 0.5],
            [ scaleX * 0.5, scaleY * 0.5, scaleZ * -0.5],
            [ scaleX * -0.5, scaleY * 0.5, scaleZ * -0.5 ],
            [ scaleX * -0.5, scaleY * -0.5, scaleZ * -0.5 ],
            [ scaleX * 0.5, scaleY * -0.5, scaleZ * -0.5 ],
            [ scaleX * 0.5, scaleY * 0.5, scaleZ * -0.5 ],
            [ scaleX * -0.5, scaleY * 0.5, scaleZ * -0.5 ],
            [ scaleX * -0.5, scaleY * 0.5, scaleZ * 0.5 ],
            [ scaleX * 0.5, scaleY * 0.5, scaleZ * 0.5 ],
            [ scaleX * 0.5, scaleY * -0.5, scaleZ * 0.5 ],
            [ scaleX * 0.5, scaleY * -0.5, scaleZ * -0.5 ],
            [ scaleX * -0.5, scaleY * -0.5, scaleZ * -0.5 ],
            [ scaleX * -0.5, scaleY * -0.5, scaleZ * 0.5 ],
            [ scaleX * 0.5, scaleY * -0.5, scaleZ * 0.5 ],
            [ scaleX * -0.5, scaleY * -0.5, scaleZ * 0.5 ],
            [ scaleX * -0.5, scaleY * 0.5, scaleZ * 0.5 ]
            ]
    controlIconLib['box']['degree'] = 1
    controlIconLib['box']['closed'] = False

    ###
    controlIconLib['arrow'] = {}
    controlIconLib['arrow']['description'] = 'a basic arrow'
    scaleX = 1
    scaleY = 0
    scaleZ = 1
    controlIconLib['arrow']['points'] = [
            [-1.0, 0.0, -1.0],
            [1.0, 0.0, -1.0],
            [1.0, 0.0, 1.0],
            [2.0, 0.0, 1.0],
            [0.0, 0.0, 3.5],
            [-2.0, 0.0, 1.0],
            [-1.0, 0.0, 1.0],
            ]
    controlIconLib['arrow']['degree'] = 1
    controlIconLib['arrow']['closed'] = True

    ###
    controlIconLib['square'] = {}
    controlIconLib['square']['description'] = 'a basic square, scalable on all axes with a center pivot'
    scaleX = 1
    scaleY = 0
    scaleZ = 1
    controlIconLib['square']['points'] = [
            [ scaleX * 0.5, scaleY * 0.5, scaleZ * 0.5],
            [ scaleX * 0.5, scaleY * 0.5, scaleZ * -0.5],
            [ scaleX * -0.5, scaleY * 0.5, scaleZ * -0.5 ],
            [ scaleX * -0.5, scaleY * 0.5, scaleZ * 0.5 ],
            ]
    controlIconLib['square']['degree'] = 1
    controlIconLib['square']['closed'] = True

    ###
    controlIconLib['pivotBox'] = {}
    controlIconLib['pivotBox']['description'] = 'a cube, scalable on all axes with a joint-like pivot'
    scaleX = 6
    scaleY = 1
    scaleZ = 1
    controlIconLib['pivotBox']['points'] = [
            [ scaleX * 1, scaleY * 0.5, scaleZ * 0.5],
            [ scaleX * 1, scaleY * 0.5, scaleZ * -0.5],
            [ scaleX * 0, scaleY * 0.5, scaleZ * -0.5 ],
            [ scaleX * 0, scaleY * -0.5, scaleZ * -0.5 ],
            [ scaleX * 1, scaleY * -0.5, scaleZ * -0.5 ],
            [ scaleX * 1, scaleY * 0.5, scaleZ * -0.5 ],
            [ scaleX * 0, scaleY * 0.5, scaleZ * -0.5 ],
            [ scaleX * 0, scaleY * 0.5, scaleZ * 0.5 ],
            [ scaleX * 1, scaleY * 0.5, scaleZ * 0.5 ],
            [ scaleX * 1, scaleY * -0.5, scaleZ * 0.5 ],
            [ scaleX * 1, scaleY * -0.5, scaleZ * -0.5 ],
            [ scaleX * 0, scaleY * -0.5, scaleZ * -0.5 ],
            [ scaleX * 0, scaleY * -0.5, scaleZ * 0.5 ],
            [ scaleX * 1, scaleY * -0.5, scaleZ * 0.5 ],
            [ scaleX * 0, scaleY * -0.5, scaleZ * 0.5 ],
            [ scaleX * 0, scaleY * 0.5, scaleZ * 0.5 ]
            ]
    controlIconLib['pivotBox']['degree'] = 1
    controlIconLib['pivotBox']['closed'] = False

    ###
    controlIconLib['rings'] = {}
    controlIconLib['rings']['description'] = 'A basic 3-ring controller'
    controlIconLib['rings']['points'] = [
            [0.0, 1.0, 0.0],
            [0.0, 0.9511, -0.309],
            [0.0, 0.809, -0.5878],
            [0.0, 0.5878, -0.809],
            [0.0, 0.309, -0.9511],
            [0.0, 0.0, -1.0],
            [0.5, 0.0, -0.866],
            [0.866, 0.0, -0.5],
            [1.0, 0.0, 0.0],
            [0.866, 0.0, 0.5],
            [0.5, 0.0, 0.866],
            [0.0, 0.0, 1.0],
            [-0.5, 0.0, 0.866],
            [-0.866, 0.0, 0.5],
            [-1.0, 0.0, 0.0],
            [-0.866, 0.0, -0.5],
            [-0.5, 0.0, -0.866],
            [0.0, 0.0, -1.0],
            [0.0, -0.309, -0.9511],
            [0.0, -0.5878, -0.809],
            [0.0, -0.809, -0.5878],
            [0.0, -0.9511, -0.309],
            [0.0, -1.0, 0.0],
            [0.0, -0.9511, 0.309],
            [0.0, -0.809, 0.5878],
            [0.0, -0.5878, 0.809],
            [0.0, -0.309, 0.9511],
            [0.0, 0.0, 1.0],
            [0.0, 0.309, 0.9511],
            [0.0, 0.5878, 0.809],
            [0.0, 0.809, 0.5878],
            [0.0, 0.9511, 0.309],
            [0.0, 1.0, 0.0],
            [0.309, 0.9511, 0.0],
            [0.5878, 0.809, 0.0],
            [0.809, 0.5878, 0.0],
            [0.9511, 0.309, 0.0],
            [1.0, 0.0, 0.0],
            [0.9511, -0.309, 0.0],
            [0.809, -0.5878, 0.0],
            [0.5878, -0.809, 0.0],
            [0.309, -0.9511, 0.0],
            [0.0, -1.0, 0.0],
            [-0.309, -0.9511, 0.0],
            [-0.5878, -0.809, 0.0],
            [-0.809, -0.5878, 0.0],
            [-0.9511, -0.309, 0.0],
            [-1.0, 0.0, 0.0],
            [-0.9511, 0.309, 0.0],
            [-0.809, 0.5878, 0.0],
            [-0.5878, 0.809, 0.0],
            [-0.309, 0.9511, 0.0],
            ]
    controlIconLib['rings']['degree'] = 1
    controlIconLib['rings']['closed'] = True

    ###
    controlIconLib['circle'] = {}
    controlIconLib['circle']['description'] = 'A basic circle'
    controlIconLib['circle']['points'] = [
            [],
            [],
            []
            ]
    controlIconLib['circle']['degree'] = 1
    controlIconLib['circle']['closed'] = True

    ###
    controlIconLib['iconName'] = {}
    controlIconLib['iconName']['description'] = 'description here'
    controlIconLib['iconName']['points'] = [
            [],
            [],
            []
                ]
    controlIconLib['iconName']['degree'] = 1
    controlIconLib['iconName']['closed'] = True

    return controlIconLib[iconKey]


def create_control_icon(iconType, iconName, iconScale, joint=False, offset=False):
    ### Read from a dictionary or JSON or Alembic file that stores point information
    iconLib = icon_library(iconType)
    pPoints = iconLib['points']
    pD = iconLib['degree']

    controlCurve = pm.curve( name=iconName, d=pD, p=pPoints )

    controlCurve.s.set(iconScale)
    pm.makeIdentity(controlCurve, apply=True)

    if iconLib['closed'] == True:
        oName = controlCurve.name()
        pm.closeCurve( controlCurve, ch=False, ps=True, rpo=True )
        controlCurve = pm.PyNode(oName)


    # A hack to make sure the arrows on arrowBox are uniformly scaled, relative to the width:height ratio.
    if iconType == 'arrowBox':
        axes = [iconScale[0], iconScale[2]]
        scaleFactor = min(axes) / max(axes)

        if iconScale[0] > iconScale[2]:
            oPivot = (pnt_ws(controlCurve.cv[21]) + pnt_ws(controlCurve.cv[27])) * 0.5
            pm.scale(controlCurve.cv[21:27], scaleFactor, 1, 1, r=True, p=oPivot)
            oPivot = (pnt_ws(controlCurve.cv[11]) + pnt_ws(controlCurve.cv[5])) * 0.5
            pm.scale(controlCurve.cv[5:11], scaleFactor, 1, 1, r=True, p=oPivot)

            oPivot = (pnt_ws(controlCurve.cv[3]) + pnt_ws(controlCurve.cv[29])) * 0.5
            pm.scale(controlCurve.cv[29:32], scaleFactor, 1, 1, r=True, p=oPivot)
            pm.scale(controlCurve.cv[0:3], scaleFactor, 1, 1, r=True, p=oPivot)

            oPivot = (pnt_ws(controlCurve.cv[13]) + pnt_ws(controlCurve.cv[19])) * 0.5
            pm.scale(controlCurve.cv[13:19], scaleFactor, 1, 1, r=True, p=oPivot)
        else:
            oPivot = (pnt_ws(controlCurve.cv[21]) + pnt_ws(controlCurve.cv[27])) * 0.5
            pm.scale(controlCurve.cv[21:27], 1, 1, scaleFactor, r=True, p=oPivot)
            oPivot = (pnt_ws(controlCurve.cv[11]) + pnt_ws(controlCurve.cv[5])) * 0.5
            pm.scale(controlCurve.cv[5:11], 1, 1, scaleFactor, r=True, p=oPivot)

            oPivot = (pnt_ws(controlCurve.cv[3]) + pnt_ws(controlCurve.cv[29])) * 0.5
            pm.scale(controlCurve.cv[29:32], 1, 1, scaleFactor, r=True, p=oPivot)
            pm.scale(controlCurve.cv[0:3], 1, 1, scaleFactor, r=True, p=oPivot)

            oPivot = (pnt_ws(controlCurve.cv[13]) + pnt_ws(controlCurve.cv[19])) * 0.5
            pm.scale(controlCurve.cv[13:19], 1, 1, scaleFactor, r=True, p=oPivot)

    if offset:
        pm.move(controlCurve.cv, offset, relative=True)

    ### Pick a particular default if not defined (circle?)
    ### scale, rotate and transform appropriately (using placing functions)
    ### color and style the curve
    ### set the icon in proper layers
    ### shape parent as necessary
    if joint:
        controlCurve.rename(controlCurve.name() + 'Shape')
        pm.select(None)
        oJoint = pm.joint(n=iconName, r=0.5)
        pm.select(None)
        pm.parent(controlCurve.getShapes(), oJoint, shape=True, relative=True)
        pm.delete(controlCurve)
        return oJoint

    return controlCurve


def sawtooth_wave_pattern(height, width, segments):
    """ Create a generator of points that make a saw-tooth wave shape |_|-|_|-|_|-| """
    heightPoints = [1.0 * height, -1.0 * height]
    segmentRange = xrange(-segments, segments+1)
    widthPoints = [(x/float(segments) * width) for x in segmentRange]

    for each, each2 in zip(widthPoints[0::2], widthPoints[1::2]):
        # UP
        yield [0.0, heightPoints[0], each]
        yield [0.0, heightPoints[1], each]
        # DOWN
        yield [0.0, heightPoints[1], each2]
        yield [0.0, heightPoints[0], each2]
    # the zips have different lengths, so finish with the last segment manually
    yield [0.0, heightPoints[0], widthPoints[-1]]
    yield [0.0, heightPoints[1], widthPoints[-1]]
        

def swap_shape(oParent, oChild):
    if oParent.getShape():
        shapeName = oParent.getShape().name()
        shapeColor = oParent.getShape().overrideColor.get()
        oChild.getShape().overrideColor.set(shapeColor)
    oChild.getShape().overrideEnabled.set(True)
    pm.delete(oParent.getShapes())
    if oChild.getParent() != oParent:
        pm.parent(oChild, oParent)
    pm.makeIdentity(oChild, apply=True, t=1, r=1, s=1)
    pm.parent(oChild.getShape(), oParent, shape=True, relative=True)
    pm.delete(oChild)


