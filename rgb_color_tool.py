import pymel.core as pm
import maya.cmds as cmds

### COLOR RGB TOOL

class ColorToolRGB(object):
    def __init__(self):
        self.name = 'colorToolRGBUI'
        self.title = 'RGB Color Tool'
        self.version = 0.1
        self.author = 'Chris Lesage - https://rigmarolestudio.com'

        self._COLORS = [
            # RGB values from 0.0 to 1.0
            # [name, RGB, fallback index for standard Maya colors]
            [ 'red',          [0.642, 0.108, 0.090],  13 ], #0
            [ 'yellow',       [0.900, 0.850, 0.000],  17 ], #1
            [ 'blue',         [0.050, 0.050, 1.000],   6 ], #2
            [ 'green',        [0.000, 0.242, 0.000],   7 ], #3
            [ 'grey1',        [0.170, 0.193, 0.205],   2 ], #4
         
            [ 'pink',         [1.000, 0.700, 0.700],  20 ], #5
            [ 'lightyellow',  [0.700, 0.700, 0.200],  22 ], #6
            [ 'lightblue',    [0.391, 0.702, 0.909],  18 ], #7
            [ 'lightgreen',   [0.367, 0.631, 0.244],  19 ], #8
            [ 'grey2',        [0.336, 0.376, 0.397],   3 ], #9
         
            [ 'darkred',      [0.360, 0.000, 0.000],   4 ], #10
            [ 'brown',        [0.800, 0.500, 0.200],  24 ], #11
            [ 'darkblue',     [0.000, 0.000, 0.500],   5 ], #12
            [ 'purple',       [0.429, 0.000, 0.800],   8 ], #13
            [ 'grey3',        [0.517, 0.576, 0.608],   3 ], #14
         
            [ 'black',        [0.000, 0.000, 0.000],   1 ], #15
            [ 'darkbrown',    [0.279, 0.184, 0.000],  24 ], #16
            [ 'orange',       [1.000, 0.400, 0.000],  21 ], #17
            [ 'lightpurple',  [0.828, 0.213, 0.949],   9 ], #18
            [ 'grey4',        [0.721, 0.789, 0.825],  16 ], #19
        ]

        self.create_ui()

    
    def create_ui(self):
        if (pm.window(self.name, q=1, exists=1)):
            pm.deleteUI(self.name)
            
        with pm.window(self.name, title=self.title + " v" + str(self.version), width=200, menuBar=True) as win:
            for row in range(4):
                with pm.horizontalLayout() as layout:
                    for i, eachColor in enumerate(self._COLORS[0+(5*row):5+(5*row)]):
                        with pm.verticalLayout() as buttonLayout:
                            colorName, rgbColor, indexColor = eachColor
                            btn = pm.button(
                                    label = str(i+(5*row)),
                                    command = pm.Callback (self.set_color, [], i+(5*row) ),
                                    backgroundColor=(rgbColor),
                                    )
                            txt = pm.text(label=colorName)
                        buttonLayout.redistribute(40,10)
                layout.redistribute()
            
        pm.showWindow()
        

    def set_color_by_index(self, oColl, color):
        if isinstance(color, int):
            colorIndex = color
        if isinstance(color, basestring):
            colorIndex = get_color_index(self, color)

        print('Setting color: {}'.format(color))
        return None
        for each in oColl:
            eachShape = each.getTransform().getShape()
            eachShape.overrideEnabled.set(True)
            eachShape.overrideRGBColors.set(True)
            eachShape.overrideColorRGB.set(self._COLORS[color][1])
            eachShape.overrideColor.set(self._COLORS[color][2])


    def get_color_index(self, oColl, color):
        return None
        #TODO: Get the name from a list of aliases. Find the index.
        colorIndex = 0
        return colorIndex


