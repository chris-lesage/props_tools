import pymel.core as pm
import maya.cmds as mc
import pymel.core.datatypes as dt
#import maya.OpenMaya as om
#import maya.OpenMayaUI as omui

'''
Create a ribbon IK.
Options include:
    - Number of skinning segments
    - Number of controls
    - Whether it should have a 2nd layer of offset controls afterwards
    - Whether it should be stretchy or fixed-length.
      (Or add a switch? Could blend between the curves that create the loft.)
    - IK/FK switch?

Input is a curve (read the points) or a selection of objects
Fixed length is great when you have non-stretchy material, or mechanical spines or chain-links, etc.
'''


def add_attr(myObj, oDataType, oParamName, oMin=None, oMax=None, oDefault=0.0):
    """ adds an attribute that shows up in the channel box; returns the newly created attribute """
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


def pin_to_surface(oNurbs, uPos=0.5, vPos=0.5):
    #TODO: Parse whether it is a nurbsSurface shape or transform
    #TODO: Can I support polygons?
    pointOnSurface = pm.createNode('pointOnSurfaceInfo')
    oNurbs.getShape().worldSpace.connect(pointOnSurface.inputSurface)
    # follicles remap from 0-1, but closestPointOnSurface must take minMaxRangeV into account
    paramLengthU = oNurbs.getShape().minMaxRangeU.get()[1]
    paramLengthV = oNurbs.getShape().minMaxRangeV.get()[1]

    pName = '{}_foll#'.format(oNurbs.name())
    result = pm.spaceLocator(n=pName)
    # Future me is going to hate all this multiplication crap.
    # But basically, the paramU100 goes from 0 to 100, and the parameterU goes from 0 to minMaxRangeU.
    paramU = add_attr(result, 'double', 'parameterU', oDefault=uPos*0.1*paramLengthU)
    paramV = add_attr(result, 'double', 'parameterV', oDefault=vPos*0.1*paramLengthV)
    paramU.connect(pointOnSurface.parameterU)
    paramV.connect(pointOnSurface.parameterV)
    paramU100 = add_attr(result, 'double', 'u_param', oDefault=uPos)
    paramV100 = add_attr(result, 'double', 'v_param', oDefault=vPos)
    connect_multiply(result.parameterU, paramU100, 0.01*paramLengthU)
    connect_multiply(result.parameterV, paramV100, 0.01*paramLengthV)

    # Compose a 4x4 matrix
    mtx = pm.createNode('fourByFourMatrix')
    outMatrix = pm.createNode('decomposeMatrix')
    mtx.output.connect(outMatrix.inputMatrix)
    outMatrix.outputTranslate.connect(result.translate)
    outMatrix.outputRotate.connect(result.rotate)

    '''
    Thanks to kiaran at https://forums.cgsociety.org/t/rotations-by-surface-normal/1228039/4
    # Normalize these vectors
    [tanu.x, tanu.y, tanu.z, 0]
    [norm.x, norm.y, norm.z, 0]
    [tanv.x, tanv.y, tanv.z, 0]
    # World space position
    [pos.x, pos.y, pos.z, 1]
    '''

    pointOnSurface.normalizedTangentUX.connect(mtx.in00)
    pointOnSurface.normalizedTangentUY.connect(mtx.in01)
    pointOnSurface.normalizedTangentUZ.connect(mtx.in02)
    mtx.in03.set(0)

    pointOnSurface.normalizedNormalX.connect(mtx.in10)
    pointOnSurface.normalizedNormalY.connect(mtx.in11)
    pointOnSurface.normalizedNormalZ.connect(mtx.in12)
    mtx.in13.set(0)

    pointOnSurface.normalizedTangentVX.connect(mtx.in20)
    pointOnSurface.normalizedTangentVY.connect(mtx.in21)
    pointOnSurface.normalizedTangentVZ.connect(mtx.in22)
    mtx.in23.set(0)

    pointOnSurface.positionX.connect(mtx.in30)
    pointOnSurface.positionY.connect(mtx.in31)
    pointOnSurface.positionZ.connect(mtx.in32)
    mtx.in33.set(1)

    return result


def create_follicle(oNurbs, count, uPos=0.0, vPos=0.0):
    #OVERRIDE with the new technique of using a 4x4 matrix and pointOnSurfaceInfo
    return pin_to_surface(oNurbs, uPos, vPos)

    # manually place and connect a follicle onto a nurbs surface.
    if oNurbs.type() == 'transform':
        oNurbs = oNurbs.getShape()
    elif oNurbs.type() == 'nurbsSurface':
        pass
    else:
        'Warning: Input must be a nurbs surface.'
        return False

    pName = '{}_{}_foll'.format(oNurbs.name(), count)
    oFoll = pm.createNode('follicle', name=pName)
    oFoll.v.set(0) # hide the little red shape of the follicle
    oNurbs.local.connect(oFoll.inputSurface)
    #oMesh.outMesh.connect(oFoll.inMesh)

    oNurbs.worldMatrix[0].connect(oFoll.inputWorldMatrix)
    oFoll.outRotate.connect(oFoll.getParent().rotate)
    oFoll.outTranslate.connect(oFoll.getParent().translate)
    oFoll.parameterU.set(uPos)
    oFoll.parameterV.set(vPos)
    oFoll.getParent().t.lock()
    oFoll.getParent().r.lock()

    return oFoll


def connect_multiply(oDriven, oDriver, oMultiplyBy):
    # re-write this using a unitconversion node instead?
    # benefits: might compute faster, and the connections are hidden from animators in the channel box.
    nodeName = oDriven.replace('.','_') + '_mult'
    try:
        testExists = pm.PyNode(nodeName)
        pm.delete(pm.PyNode(nodeName))
    except: pass
    oMult = pm.shadingNode('unitConversion', asUtility=True, name=nodeName)
    pm.PyNode(oDriver).connect(oMult.input)
    oMult.output.connect( pm.Attribute(oDriven) )
    oMult.conversionFactor.set(oMultiplyBy)
    return oMult


def build_twist_ramp(prefix, controlObj, twistColl, twistAttrs=['rotateX']):
    '''
    Take a collection of objects and twist them. This can drive the attribute of your choice, but it was written with ribbon-IK twist in mind.
    It uses a master remapValue that drives multiple remapValues to simulate a multi-in, multi-out array node.
    '''
    # The master twist profile curve.
    masterRemap = pm.createNode('remapValue', n='{}_master_ribbon_lerp_MAP'.format(prefix))
    masterRemap.inputMax.set(len(twistColl)) # set the range to the count of twist objects.
    masterRemap.value[0].value_Interp.set(2) # set to smooth interpolation. #TODO: Add a parameter to change this on the fly.

    pStart = add_attr(controlObj, 'double', '{}_start'.format(prefix), oMin=None, oMax=None, oDefault=0.0)
    pEnd = add_attr(controlObj, 'double', '{}_end'.format(prefix), oMin=None, oMax=None, oDefault=0.0)
    twistStart = add_attr(controlObj, 'double', '{}_start_position'.format(prefix), oMin=0.0, oMax=1.0, oDefault=0.0)
    twistEnd = add_attr(controlObj, 'double', '{}_end_position'.format(prefix), oMin=0.0, oMax=1.0, oDefault=1.0)
    twistType = add_attr(controlObj, 'long', '{}_interpolation'.format(prefix), oMin=0, oMax=2, oDefault=2) # 0 none 1 linear 2 smooth 3 spline
    twistStart.connect(masterRemap.value[0].value_Position)
    twistEnd.connect(masterRemap.value[1].value_Position)
    twistType.connect(masterRemap.value[0].value_Interp)

    for i, each in enumerate(twistColl):
        # add a start and end twist parameter to the follicles.
        twistMLT = pm.createNode('multiplyDivide', n='{}_lerp_{}_MLT'.format(prefix, i+1))
        twistAdd = pm.createNode('plusMinusAverage', n='{}_lerp_{}_ADD'.format(prefix, i+1))
        pStart.connect(twistMLT.input1X)
        pEnd.connect(twistMLT.input1Y)

        twistProfile = pm.createNode('remapValue', n='{}_lerp_profile_{}_MAP'.format(prefix, i+1))
        # and a reverse node for the end twist. This calculates the complement of the first curve.
        # This technique would fail if you wanted to have different interpolations for Start and End twist.
        # However, I don't. If I run both Start and End the same amount, then the whole interpolation should add up to 1.0
        reverseProfile = pm.createNode('reverse', n='{}_lerp_{}_REVERSE'.format(prefix, i+1))

        # connect masterRemap remapValue curve to the other remapValue nodes. Then you can drive them all with one, faking a multi-in-out node.
        twistProfile.inputMax.set(len(twistColl))
        twistProfile.inputValue.set(i)
        masterRemap.value[0].value_Position.connect(twistProfile.value[0].value_Position)
        masterRemap.value[0].value_FloatValue.connect(twistProfile.value[0].value_FloatValue)
        masterRemap.value[0].value_Interp.connect(twistProfile.value[0].value_Interp)
        
        masterRemap.value[1].value_Position.connect(twistProfile.value[1].value_Position)
        masterRemap.value[1].value_FloatValue.connect(twistProfile.value[1].value_FloatValue)
        masterRemap.value[1].value_Interp.connect(twistProfile.value[1].value_Interp)

        # connect the profile remapValue to the multiplyDivide nodes
        twistProfile.outValue.connect(twistMLT.input2Y)
        twistProfile.outValue.connect(reverseProfile.input.inputX)
        #TODO: If you wanted to get rid of the Reverse nodes, you could just hook up the remapValues in reverse.
        # So the last remapValue would be the first one for the input2X
        # However, that only works if the curves are symmetrical. Ease-in-ease-out or linear. Ease-in-linear-out wouldn't work.
        reverseProfile.output.outputX.connect(twistMLT.input2X)
        
        twistMLT.outputX.connect(twistAdd.input2D[0].input2Dx)
        twistMLT.outputY.connect(twistAdd.input2D[1].input2Dx)
        for twistAttr in twistAttrs:
            twistAdd.output2D.output2Dx.connect(pm.PyNode('{}.{}'.format(each.name(), twistAttr)), force=True)


def many_follicles(obj, uCount, vCount):
    oFolls = []
    pName = obj.name()
    oRoot = pm.group(n=pName.replace('ribbon','follicles'), em=True)

    for j in range(vCount):
        for i in range(uCount):
            pm.select(None)
            if uCount == 1:
                uPos = 0.5
            else:
                uPos = i/(uCount-1.00)
            if vCount == 1:
                vPos = 0.5
            else:
                vPos = j/(vCount-1.00)
            oFoll = create_follicle(obj, i+1, uPos, vPos)
            pm.rename(oFoll.getParent(), pName + '_{}_foll'.format(i+1))
            oLoc = pm.group(n=pName + '_{}_grp'.format(i+1), em=True)
            oLoc.setTranslation(oFoll.getTranslation(space='world'), space='world')
            oJoint = pm.joint(n=pName + '_{}_jnt'.format(i+1))
            oJoint.setTranslation(oFoll.getTranslation(space='world'), space='world')
            pm.parent(oLoc, oFoll)
            pm.parent(oFoll, oRoot)
            oLoc.r.set([0, 0, 0])
            pm.select(None)
            oFolls.append(oFoll)

    return oFolls


def create_skin_shell():
    ''' A function that creates a polygon plane along with the ribbon with 1x or 2x density of the follicles.
    The follicles skin this plane. You can then use this to copy weights to your mesh. '''
    pass


def skin_geometry(oJoints, oGeo, pName):
    '''a simple skinCluster command with my preferred prefs.'''
    oSkin = pm.skinCluster(oJoints, oGeo,
            bindMethod=0, # closest distance
            dropoffRate=1.0,
            maximumInfluences=1,
            normalizeWeights=1, # interactive
            obeyMaxInfluences=False,
            skinMethod=0, # classic linear
            removeUnusedInfluence=0,
            weightDistribution=0, # neighbors
            name=pName,
        )
    return oSkin


def create_a_tangent_curve(inputCurve, tangent='side'):
    '''
    'up' uses -Y as upvector to get a ribbon that is oriented horizontally.
    'side' finds the side tangent then uses that as an upvector, to get a ribbon that is oriented vertically.
    '''
    curveB = pm.duplicate(inputCurve, n=inputCurve.name().replace('crv','tangentcrv'))[0]

    # create a normalized tangent vector to move the new curve sideways.
    curveVector = curveB.cv[1].getPosition(space='world') - curveB.cv[0].getPosition(space='world')
    #TODO: It might make more sense to always move tagentially to the bend in the curve. ie. towards the direction of the planar side. For example, if it bends up and down, tangent to the side. If you had a 180 bend, it could flip.
    if tangent == 'side':
        tangentPos = dt.cross(curveVector.normal(), dt.Vector(0,0,-1))
    else:
        tangentPos = dt.cross(curveVector.normal(), dt.Vector(0,-1,0))
    pm.move(curveB.cv, tangentPos * 2.0, relative=True)

    return curveB


def fixed_length_ik(sparseCurve, denseCurve, namePrefix, sparseCurveB=None, denseCurveB=None, tangent='side'):
    '''
    Creates 2 splineIK chains. Those chains skin 2 more curves. Those curves create a loft which creates a ribbon with follicles.
    This gives you full rotation control like a ribbon IK. But fixed-length like spline-IK. SplineIK twist is start-to-end only. This is more flexible for twisting.
    '''
    rigGroup = pm.group(n='{}_ribbon_rig_grp'.format(namePrefix), em=True)
    sparsePoints = [x.getPosition(space='world') for x in sparseCurve.cv]
    densePoints = [x.getPosition(space='world') for x in denseCurve.cv]

    if not sparseCurveB:
        sparseCurveB = create_a_tangent_curve(sparseCurve, tangent=tangent)
    if not denseCurveB:
        denseCurveB = create_a_tangent_curve(denseCurve, tangent=tangent)

    sparsePointsB = [x.getPosition(space='world') for x in sparseCurveB.cv]
    densePointsB = [x.getPosition(space='world') for x in denseCurveB.cv]

    # build dense joints x 2
    pm.select(None)
    denseJointsA = [pm.joint(n='{}_dense_joint_A{:02d}_jnt'.format(namePrefix, i+1), p=each) for i, each in enumerate(densePoints)]
    pm.joint(denseJointsA, e=True, oj='xyz', secondaryAxisOrient='yup', ch=True, zso=True)
    denseJointsA[-1].jointOrient.set([0,0,0]) # the last joint never orients properly because Autodesk are fundamentally out of touch with their users.

    pm.select(None)
    denseJointsB = [pm.joint(n='{}_dense_joint_B{:02d}_jnt'.format(namePrefix, i+1), p=each) for i, each in enumerate(densePointsB)]
    pm.joint(denseJointsB, e=True, oj='xyz', secondaryAxisOrient='yup', ch=True, zso=True)
    denseJointsB[-1].jointOrient.set([0,0,0]) # the last joint never orients properly because Autodesk are fundamentally out of touch with their users.

    # build sparse control joints x 1
    pm.select(None)
    #TODO: Detect the side and set the prefix.
    rigControlsGrp = pm.group(em=True, n='{}_ribbon_controls_grp'.format(namePrefix))
    controlJoints = [pm.joint(n='{}_{:02d}_ctrl'.format(namePrefix, i+1), p=each, radius=2.0) for i, each in enumerate(sparsePoints)]
    pm.joint(controlJoints, e=True, oj='xyz', secondaryAxisOrient='yup', ch=True, zso=True)
    controlJoints[-1].jointOrient.set([0,0,0]) # the last joint never orients properly because Autodesk are fundamentally out of touch with their users.

    # set up spline IK on dense joints and sparse curve
    splineA = pm.ikHandle(
            sj=denseJointsA[0], ee=denseJointsA[-1], c=sparseCurve, n='{}_splineik_A_ikhandle'.format(namePrefix),
            ccv=False, pcv=False, snc=False, scv=False, rtm=False, twistType='linear', solver='ikSplineSolver'
            )
    
    splineB = pm.ikHandle(
            sj=denseJointsB[0], ee=denseJointsB[-1], c=sparseCurveB, n='{}_splineik_A_ikhandle'.format(namePrefix),
            ccv=False, pcv=False, snc=False, scv=False, rtm=False, twistType='linear', solver='ikSplineSolver'
            )

    # skin dense curves to dense joints, then manually set the weights because the last joint won't have any influence.
    skinCls = skin_geometry(controlJoints, sparseCurve, '{}_splineik_crv_A_skincluster'.format(namePrefix))
    for i, each in enumerate(controlJoints):
        pm.skinPercent( skinCls, sparseCurve.cv[i], transformValue=[(controlJoints[i], 1)])

    skinCls = skin_geometry(controlJoints, sparseCurveB, '{}_splineik_crv_B_skincluster'.format(namePrefix))
    for i, each in enumerate(controlJoints):
        pm.skinPercent( skinCls, sparseCurveB.cv[i], transformValue=[(controlJoints[i], 1)])

    skinCls = skin_geometry(denseJointsA, denseCurve, '{}_ribbon_crv_A_skincluster'.format(namePrefix))
    for i, each in enumerate(denseJointsA):
        pm.skinPercent( skinCls, denseCurve.cv[i], transformValue=[(denseJointsA[i], 1)])

    skinCls = skin_geometry(denseJointsB, denseCurveB, '{}_ribbon_crv_B_skincluster'.format(namePrefix))
    for i, each in enumerate(denseJointsB):
        pm.skinPercent( skinCls, denseCurveB.cv[i], transformValue=[(denseJointsB[i], 1)])
    
    # loft the dense curves
    oRibbon = pm.loft(
        denseCurve, denseCurveB,
        ar=True,
        constructionHistory=True,
        degree=3,
        close=False,
        rn=False,
        polygon=0,
        sectionSpans=1,
        reverseSurfaceNormals=True,
        uniform=True,
        n='{}_ribbon_loft'.format(namePrefix),
        )
    
    # add follicles to the loft surface

    folls = many_follicles(oRibbon[0], len(denseJointsA), 1)
    build_twist_ramp(namePrefix, rigControlsGrp, [x.getChildren(type='transform')[0] for x in folls], twistAttrs=['rotateX'])

    numSpans = oRibbon[0].spansUV.get()[0]
    oNode = pm.createNode('closestPointOnSurface', n='ZZZTEMP')
    oRibbon[0].worldSpace.connect(oNode.inputSurface, force=True)
    for foll, loc in zip(folls, densePoints):
        ### SNIPPET: Move a follicle to closest point near an object
        oNode.inPosition.set(loc)
        foll.u_param.set(oNode.parameterU.get() / oRibbon[0].spansU.get() * 100.0)
        foll.v_param.set(oNode.parameterV.get() / oRibbon[0].spansV.get() * 100.0)
    pm.delete(oNode)

    # parent all the stuff under the rig group
    pm.parent(controlJoints[0], rigControlsGrp)
    pm.parent(sparseCurve, denseCurve, sparseCurveB, denseCurveB, rigGroup)
    pm.parent(denseJointsA[0], denseJointsB[0], rigGroup)
    pm.parent(splineA[0], splineB[0], oRibbon[0], rigGroup)
    pm.parent(folls[0].getParent(), rigGroup)

    # add a zero offset to each control joint.
    for each in controlJoints:
        parentGrp = pm.group(n=each.name() + '_grp', em=True)
        parentGrp.setTranslation(each.getTranslation(space='world'), space='world')
        parentGrp.setRotation(each.getRotation(space='world'), space='world')
        try:
                pm.parent(parentGrp, each.getParent())
        except:
                pass
        pm.parent(each, parentGrp)


    for each in [sparseCurve, denseCurve, sparseCurveB, denseCurveB, denseJointsA[0], denseJointsB[0], splineA[0], splineB[0]]:
        each.v.set(0)

    return folls
    

def ribbon_ik(sparseCurve, denseCurve, namePrefix, sparseCurveB=None, tangent='side'):
    '''
    Creates a stretchy ribbon IK.
    '''
    rigGroup = pm.group(n='{}_ribbon_rig_grp'.format(namePrefix), em=True)

    if not sparseCurveB:
        sparseCurveB = create_a_tangent_curve(sparseCurve, tangent=tangent)

    sparsePoints = [x.getPosition(space='world') for x in sparseCurve.cv]
    sparsePointsB = [x.getPosition(space='world') for x in sparseCurveB.cv]
    densePoints = [x.getPosition(space='world') for x in denseCurve.cv]

    # build sparse control joints x 1
    pm.select(None)
    #TODO: Detect the side and set the prefix.
    rigControlsGrp = pm.group(em=True, n='{}_ribbon_controls_grp'.format(namePrefix))
    controlJoints = [pm.joint(n='{}_{:02d}_ctrl'.format(namePrefix, i+1), p=each, radius=2.0) for i, each in enumerate(sparsePoints)]
    pm.joint(controlJoints, e=True, oj='xyz', secondaryAxisOrient='yup', ch=True, zso=True)
    controlJoints[-1].jointOrient.set([0,0,0]) # the last joint never orients properly because Autodesk are fundamentally out of touch with their users.

    # loft the sparse curves
    oRibbon = pm.loft(
        sparseCurve, sparseCurveB,
        ar=True,
        constructionHistory=False,
        degree=3,
        close=False,
        rn=False,
        polygon=0,
        sectionSpans=1,
        reverseSurfaceNormals=True,
        uniform=True,
        n='{}_ribbon_loft'.format(namePrefix),
        )
    pm.delete(sparseCurveB)
    
    skinCls = skin_geometry(controlJoints, oRibbon[0], '{}_splineik_crv_A_skincluster'.format(namePrefix))
    for i, each in enumerate(controlJoints):
        pm.skinPercent( skinCls, oRibbon[0].cv[i], transformValue=[(controlJoints[i], 1)])

    # add follicles to the loft surface

    folls = many_follicles(oRibbon[0], len(densePoints), 1)
    build_twist_ramp(namePrefix, rigControlsGrp, [x.getParent().getChildren(type='transform')[0] for x in folls], twistAttrs=['rotateX'])

    numSpans = oRibbon[0].spansUV.get()[0]
    oNode = pm.createNode('closestPointOnSurface', n='ZZZTEMP')
    oRibbon[0].worldSpace.connect(oNode.inputSurface, force=True)
    for foll, loc in zip(folls, densePoints):
        ### SNIPPET: Move a follicle to closest point near an object
        oNode.inPosition.set(loc)
        foll.u_param.set(oNode.parameterU.get() / oRibbon[0].spansU.get() * 100.0)
        foll.v_param.set(oNode.parameterV.get() / oRibbon[0].spansV.get() * 100.0)
    pm.delete(oNode)

    # parent all the stuff under the rig group
    pm.parent(controlJoints[0], rigControlsGrp)
    pm.parent(oRibbon[0], rigGroup)
    pm.parent(folls[0].getParent(), rigGroup)

    # add a zero offset to each control joint.
    for each in controlJoints:
        parentGrp = pm.group(n=each.name() + '_grp', em=True)
        parentGrp.setTranslation(each.getTranslation(space='world'), space='world')
        parentGrp.setRotation(each.getRotation(space='world'), space='world')
        try:
                pm.parent(parentGrp, each.getParent())
        except:
                pass
        pm.parent(each, parentGrp)
    #pm.delete(sparseCurve, denseCurve)

    return folls
