import pymel.core as pm
import maya.cmds as cmds

### COLOR RGB TOOL

'''
Tool ideas:
    - A button to convert existing controllers to their rgb counter-parts.
    - A button to turn off RGB and revert to index.
    - Finish a way to call the colors by alias names.
    - Have some empty palette slots to add your own custom colors.
    - Add a get function too, so you can match colors from source objects.
    - Some functionality for dealing with transforms vs. shapes? Right click for transforms?
    - A connected-palette system, where editing the swatch updates all connected shapes.
'''

class ColorToolRGB(object):
    def __init__(self):
        self.name = 'rgbColorToolGUI'
        self.title = 'RGB Color Tool'
        self.version = 0.2
        self.author = 'Chris Lesage - https://rigmarolestudio.com'

        #TODO: Some of the colors should be closer to original. Cyan, pink. I made them too faded.
        #TODO: Can I restructure the color data as a class? Would that help? Conversions become methods.
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
            [ 'orange',       [1.000, 0.200, 0.000],  21 ], #17
            [ 'lightpurple',  [0.828, 0.213, 0.949],   9 ], #18
            [ 'grey4',        [0.721, 0.789, 0.825],  16 ], #19
        ]

        # Which color to choose when translating existing index colors to RGB
        self.indexToName = {
            0: None,
            1: 15, # black
            2: 4, # grey1
            3: 14, # grey3
            4: 10, # darkred
            5: 5, # darkblue
            6: 2, # blue
            7: 3, # green
            8: 13, # purple,
            9: 18, # lightpurple
            10: 10, # darkred
            11: 16, # darkbrown
            12: 10, # darkred
            13: 0, # red
            14: 8, # lightgreen
            15: 2, # blue
            16: 19, # grey4
            17: 1, # yellow
            18: 7, # lightblue
            19: 8, # lightgreen
            20: 5, # pink
            21: 11, # brown
            22: 6, # lightyellow
            23: 8, # lightgreen
            24: 16, # darkbrown
            25: 6, # lightyellow
            26: 8, # lightgreen
            27: 3, # green
            28: 7, # lightblue
            29: 2, # blue
            30: 13, # purple
            31: 10, # darkred
            }

        self.create_ui()

    
    def create_ui(self):
        if (pm.window(self.name, q=1, exists=1)):
            pm.deleteUI(self.name)
            
        with pm.window(self.name, title=self.title + " v" + str(self.version), width=200, menuBar=True) as win:
            with pm.verticalLayout() as mainLayout:
                for row in range(4):
                    with pm.horizontalLayout() as layout:
                        for i, eachColor in enumerate(self._COLORS[0+(5*row):5+(5*row)]):
                            with pm.verticalLayout() as buttonLayout:
                                colorName, rgbColor, indexOverride = eachColor
                                btn = pm.button(
                                        label = str(i+(5*row)),
                                        command = pm.Callback (self.set_color_button, i+(5*row) ),
                                        backgroundColor=(rgbColor),
                                        )
                                txt = pm.text(label=colorName)
                            buttonLayout.redistribute(40,10)
                    layout.redistribute()
                with pm.horizontalLayout() as bottomButtons:
                    pm.button(label='Switch to RGB', command = pm.Callback(self.switch_to_rgb))
                    pm.button(label='Turn OFF RGB', command = pm.Callback(self.turn_off_rgb))
            mainLayout.redistribute(20, 20, 20, 20, 10)
            
        pm.showWindow()
        

    def set_color_button(self, color):
        self.set_color(pm.selected(), color)


    def set_color(self, oColl, color):
        # Add error handling for numbers out of range, or missing name keys.
        if isinstance(color, int):
            colorNumber = color
        if isinstance(color, basestring):
            colorNumber = color_index_from_name(self, color)

        print('Setting color: {}'.format(colorNumber))
        colorName, rgbColor, indexOverride = self._COLORS[colorNumber]
        print(colorName, rgbColor, indexOverride)

        for each in oColl:
            if isinstance(each, pm.nodetypes.Transform):
                for eachShape in each.getShapes():
                    eachShape.overrideEnabled.set(True)
                    eachShape.overrideColor.set(indexOverride)
                    eachShape.overrideRGBColors.set(True)
                    eachShape.overrideColorRGB.set(rgbColor)
            #TODO: I'll have to check BOTH the transform and the shape for overrides.
            if isinstance(each, pm.nodetypes.Shape):
                each.overrideEnabled.set(True)
                each.overrideColor.set(indexOverride)
                each.overrideRGBColors.set(True)
                each.overrideColorRGB.set(rgbColor)


    def switch_to_rgb(self):
        for each in pm.selected():
            trx = each.getTransform()
            for eachShape in trx.getShapes():
                # If override is off, skip this
                if eachShape.overrideEnabled.get() == False:
                    continue
                # Get the rgb name from the indexOverride of the index color
                rgbEquivalent = self.indexToName[eachShape.overrideColor.get()]
                if rgbEquivalent != None:
                    self.set_color([eachShape], rgbEquivalent)
    
    def turn_off_rgb(self):
        pass


    def color_index_from_name(self, oColl, color):
        return None
        #TODO: Get the color number from a list of aliases. Allow 'darkred', 'Dark Red', 'dark red', etc.
        colorNumber = 0
        return colorNumber


