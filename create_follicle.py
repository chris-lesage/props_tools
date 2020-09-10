import pymel.core as pm


def pin_to_surface(oNurbs, sourceObj=None, uPos=0.5, vPos=0.5):
    """
    This function replaces what I used to use follicles for.
    It pins an object to a surface's UV coordinates.
    In rare circumstances follicles can flip and jitter. This seems to solve that.
    
    1. oNurbs is the surface you want to pin to.
    Pass a PyNode transform, NurbsSurface or valid string name.
    2. sourceObj is an optional reference transform. If specified the UV coordinates
    will be placed as close as possible. Otherwise, specify U and V coordinates.
    Pass a PyNode transform, shape node or valid string name.
    3. uPos and vPos can be specified, and default to 0.5
    """
    
    #TODO: Can I support polygons?
    # Parse whether it is a nurbsSurface shape or transform
    if type(oNurbs) == str and pm.objExists(oNurbs):
        oNurbs = pm.PyNode(oNurbs)
    if type(oNurbs) == pm.nodetypes.Transform:
        pass
    elif type(oNurbs) == pm.nodetypes.NurbsSurface:
        oNurbs = oNurbs.getTransform()
    elif type(oNurbs) == list:
        pm.warning('Specify a NurbsSurface, not a list.')
        return False
    else:
        pm.warning('Invalid surface object specified.')
        return False
    
    pointOnSurface = pm.createNode('pointOnSurfaceInfo')
    oNurbs.getShape().worldSpace.connect(pointOnSurface.inputSurface)
    # follicles remap from 0-1, but closestPointOnSurface must take minMaxRangeV into account
    paramLengthU = oNurbs.getShape().minMaxRangeU.get()
    paramLengthV = oNurbs.getShape().minMaxRangeV.get()

    if sourceObj:
        # Place the follicle at the position of the sourceObj
        # Otherwise use the UV coordinates passed in the function
        if isinstance(sourceObj, str) and pm.objExists(sourceObj):
            sourceObj = pm.PyNode(sourceObj)
        if isinstance(sourceObj, pm.nodetypes.Transform):
            pass
        elif isinstance(sourceObj, pm.nodetypes.Shape):
            sourceObj = sourceObj.getTransform()
        elif type(sourceObj) == list:
            pm.warning('sourceObj should be a transform, not a list.')
            return False
        else:
            pm.warning('Invalid sourceObj specified.')
            return False        
        oNode = pm.createNode('closestPointOnSurface', n='ZZZTEMP')
        oNurbs.worldSpace.connect(oNode.inputSurface, force=True)
        oNode.inPosition.set(sourceObj.getTranslation(space='world'))
        uPos = oNode.parameterU.get()
        vPos = oNode.parameterV.get()
        pm.delete(oNode)

    pName = '{}_foll#'.format(oNurbs.name())
    result = pm.spaceLocator(n=pName).getShape()
    result.addAttr('parameterU', at='double', keyable=True, dv=uPos)
    result.addAttr('parameterV', at='double', keyable=True, dv=vPos)
    # set min and max ranges for the follicle along the UV limits.
    result.parameterU.setMin(paramLengthU[0])
    result.parameterV.setMin(paramLengthV[0])
    result.parameterU.setMax(paramLengthU[1])
    result.parameterV.setMax(paramLengthV[1])
    result.parameterU.connect(pointOnSurface.parameterU)
    result.parameterV.connect(pointOnSurface.parameterV)
    
    # Compose a 4x4 matrix
    mtx = pm.createNode('fourByFourMatrix')
    outMatrix = pm.createNode('decomposeMatrix')
    mtx.output.connect(outMatrix.inputMatrix)
    outMatrix.outputTranslate.connect(result.getTransform().translate)
    outMatrix.outputRotate.connect(result.getTransform().rotate)

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


def many_follicles(obj, countU, countV, vDir='U', radius=1.0):
    pName = obj.name()
    oRoot = pm.spaceLocator(n=pName.replace('_ribbon','') + '_follicles')
    pm.delete(oRoot.getShape())
    allFolls = []
    for i in range(0,countU):
        for j in range(0, countV):
            pm.select(None)
            if countU == 1:
                uPos = 0.5
            else:
                uPos = (i/(countU-1.00)) * 1.0 #NOTE: I recently changed this to have a range of 0-10
            if countV == 1:
                vPos = 0.5
            else:
                vPos = (j/(countV-1.00)) * 1.0 #NOTE: I recently changed this to have a range of 0-10
            if vDir == 'U':
                oFoll = pin_to_surface(obj, None, uPos, vPos)
            else:
                # reverse the direction of the follicles
                oFoll = pin_to_surface(obj, None, vPos, uPos)
            oLoc = pm.group(em=True, n=pName + '_ROOT#')
            oLoc.setTranslation(oFoll.getTransform().getTranslation(space='world'), space='world')
            oJoint = pm.joint(n=pName + '_joint#', radius=radius)
            oJoint.setTranslation(oFoll.getTransform().getTranslation(space='world'), space='world')
            #pm.parent(oJoint, oLoc)
            pm.parent(oLoc, oFoll.getTransform())
            pm.parent(oFoll.getTransform(), oRoot)
            oLoc.rx.set(0.0)
            oLoc.ry.set(0.0)
            oLoc.rz.set(0.0)
            pm.select(None)
            allFolls.append(oFoll)
    return allFolls

def add_attr(myObj, oDataType, oParamName, oMin=None, oMax=None, oDefault=None):
    '''adds an attribute that shows up in the channel box; returns the newly created attribute'''
    #TODO: Document a list of all possible attribute types. I never remember them all.
    # "double" = float
    oFullName = '.'.join( [str(myObj),oParamName] )
    if pm.objExists(oFullName):
        pm.PyNode(str(FullName)).set(oValue) # if it exists, just set the value
        return pm.PyNode(oFullName)
    else:
        myObj.addAttr(oParamName, at=oDataType, keyable=True, dv=oDefault)
        oParam = pm.PyNode(oFullName)
        if oMin: oParam.setMin(oMin)
        if oMax: oParam.setMax(oMax)
        if oMin == 0: oParam.setMin(0)
        if oMax == 0: oParam.setMax(0)
        pm.setAttr(oParam, e=True, channelBox=True)
        pm.setAttr(oParam, e=True, keyable=True)
        return oParam


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


#for myObject in pm.selected():
#    many_follicles(myObject, 1, 1, 'V', radius=0.25)

oNurbs = pm.selected()[-1]
for each in pm.selected()[:-1]:
    oFoll = pin_to_surface(oNurbs, each, 5, 5)
    pm.parentConstraint(oFoll.getTransform(), each, mo=True)