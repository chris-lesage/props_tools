import pymel.core as pm

# SNIPPET: Find non-unique Geo nodes
geoGroup = pm.PyNode('Geo')
for each in [x.getTransform() for x in geoGroup.getChildren(ad=True, type='mesh', noIntermediate=True)]:
    if len(pm.ls(each.name().split('|')[-1])) > 1:
        print pm.ls(each.name())