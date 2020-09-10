import pymel.core as pm
from mgear.core import attribute
import maya.cmds as cmds


def reset_attributes(oColl):
    for oNode in oColl:
        params = [
                x.attrName() for x in oNode.listAttr(keyable=True)
                if not x.attrName() in ['v','tx','ty','tz','rx','ry','rz','sx','sy','sz']
                ]
        transformAttrs = [
                x.attrName() for x in oNode.listAttr(keyable=True)
                if x.attrName() in ['tx','ty','tz','rx','ry','rz','sx','sy','sz']
                ]
        # mGear smart_reset() only does SRT if you have nothing selected. So hijack the function it calls.
        # You must pass a list to the function, otherwise it will try to iterate over the object's name.
        attributes = attribute.getSelectedChannels()
        if attributes:
            attribute.reset_selected_channels_value([oNode], attributes)
        else:
            reset_srt(oNode)
            if transformAttrs:
                attribute.reset_selected_channels_value([oNode], transformAttrs)
            if params:
                attribute.reset_selected_channels_value([oNode], params)


def reset_srt(oNode):
    defaultValues = {'sx':1, 'sy':1, 'sz':1, 'rx':0, 'ry':0, 'rz':0, 'tx':0, 'ty':0, 'tz':0}
    # o is each object, x is each attribute
    for attr in defaultValues:
        try: oNode.attr(attr).set(defaultValues[attr])
        except: continue
    
    

reset_attributes(pm.selected())