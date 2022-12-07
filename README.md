# toppingmaker
Package to create parameterized QGIS projects and dump it into a YAML structure.

## Installation
```
pip install toppingmaker
```

## Structure

```
toppingmaker
├── exportsettings.py
├── projecttopping.py
├── target.py
└── utils.py
```

## User Manual

Having a QGIS Project with some layers:

![QGIS Project Layertree](assets/qgis_project_layertree.png)

### Import the modules

```py
from qgis.core import QgsProject()
from toppingmaker import ProjectTopping, ExportSettings, Target
```

### Create a `ProjectTopping` and parse the QGIS Project

```py
project = QgsProject()
project_topping = ProjectTopping()
project_topping.parse_project(project)
```

This parses the project, but does not yet write the files (only the style and definition file to a temp folder). The QgsProject object is not used anymore.

### Create the `Target`
To write the files we need to define a `Target` object. The target defines where to store the topping files (YAML, style, definition etc.).

```py
target = Target(projectname="freddys_qgis_project", main_dir="/home/fred/repo/", sub_dir="freddys_qgis_topping", pathresover = None)
```

### Generate the Files
```py
project_topping.generate_files(target)
```

The structure looks like this:

```
repo
└── freddys_qgis_topping
    └── projecttopping
        └── freddys_qgis_project.yaml
```

And the YAML looks like this:

```yaml
layerorder: []
layertree:
- Street:
    checked: true
    expanded: true
- Park:
    checked: false
    expanded: true
- Building:
    checked: true
    expanded: true
- Info Layers:
    checked: true
    child-nodes:
    - AssetItem:
        checked: true
        expanded: true
    - InternalProject:
        checked: true
        expanded: true
    expanded: true
    group: true
- Background:
    checked: true
    child-nodes:
    - Landeskarten (grau):
        checked: true
        expanded: true
    expanded: true
    group: true
```

The structure is exported. But not any additional files. For that, we need to parse the `ExportSettings` to the `ProjectTopping`.

### Create the `ExportSettings`:

#### Layer Tree Settings

We can decide for every layer (group) if we want to:

- Use `QMLSTYLE` for the export of the qml stylefile.
- Use `DEFINITION` to export the qlr definition file.
- USE `SOURCE` to store the source in the YAML tree.

The `QgsLayerTreeNode` or the layername can be used as key.

```py
export_settings = ExportSettings()
export_settings.set_setting_values(
    type = ExportSettings.ToppingType.QMLSTYLE, node = None, name = "Street", export = True
)
export_settings.set_setting_values(
    type = ExportSettings.ToppingType.SOURCE, node = None, name = "Park", export = True
)
export_settings.set_setting_values(
    type = ExportSettings.ToppingType.DEFINITION, node = None, name = "Info Layers", export = True
)
export_settings.set_setting_values(
    type = ExportSettings.ToppingType.SOURCE, node = None, name = "Landeskarten (grau)", export = True
)
```

Additionally you can pass category flags `QgsMapLayer.StyleCategories` to define what categories needs to be included in the QML Stylefile:

```py
category_flags = QgsMapLayer.StyleCategory.AllStyleCategories

export_settings.set_setting_values(
    type = ExportSettings.ToppingType.QMLSTYLE, node = None, name = "Street", export = True, categories = category_flags
)
```

Without an additional setting, only the default style is considered. To export the style of multiple style add them as seperate setting entries:

```py
# default style (if style_name "default" is added, it makes no difference)
export_settings.set_setting_values(
    type = ExportSettings.ToppingType.QMLSTYLE, node = None, name = "Street", export = True )
)
# french style (e.g. french aliases)
export_settings.set_setting_values(
    type = ExportSettings.ToppingType.QMLSTYLE, node = None, name = "Street", export = True, categories = category_flags, style_name = "french" )
)
# robot style (e.g. technical look)
export_settings.set_setting_values(
    type = ExportSettings.ToppingType.QMLSTYLE, node = None, name = "Street", export = True, categories = category_flags, style_name = "robot" )
)
```

#### Map Themes Settings

Set the names of the map themes that should be considered as a list:
```py
export_settings.mapthemes = ["Robot Theme", "French Theme"]
```

#### Custom Project Variables Settings

Set the keys of custom variables that should be considered as a list:
```py
export_settings.variables = ["first_variable", "Another_Variable"]
```

#### Print Layout Settings

Set the names of layouts that should be considered (exported as template files) as a list:
```py
export_settings.layouts = ["Layout One", "Layout Three"]
```

### Generate the Files for a `ProjectTopping` containing `ExportSetting`
When parsing the QgsProject we need to pass the `ExportSettings`:
```py
project_topping.parse_project(project, export_settings)
project_topping.generate_files(target)
```

The structure looks like this:

```
repo
└── freddys_qgis_topping
    ├── layerdefinition
    │   └── freddys_qgis_project_info_layers.qlr
    └── projecttopping
        └── freddys_qgis_project.yaml
    └── layerstyle
        ├── freddys_qgis_project_street.qml
        ├── freddys_qgis_project_street_french.qml
        └── freddys_qgis_project_street_robot.qml
    └── layouttemplate
        ├── freddys_qgis_project_layout_one.qpt
        └── freddys_qgis_project_layout_three.qpt
```

And the YAML looks like this:

```yaml
layertree:
  - Street:
      tablename: street
      geometrycolumn: geometry
      checked: true
      expanded: true
      qmlstylefile: freddys_qgis_topping/layerstyle/freddys_qgis_project_street.qml
      styles:
        french:
          qmlstylefile: freddys_qgis_topping/layerstyle/freddys_qgis_project_street_french.qml
        robot:
          qmlstylefile: freddys_qgis_topping/layerstyle/freddys_qgis_project_street_robot.qml
  - Park:
      tablename: park
      geometrycolumn: geometry
      checked: false
      expanded: true
      provider: ogr
      uri: /home/freddy/qgis_projects/bakery/cityandcity.gpkg|layername=park
  - Building:
      tablename: building_2
      geometrycolumn: geometry
      checked: true
      expanded: true
  - Info Layers:
      checked: true
      definitionfile: freddys_qgis_topping/layerdefinition/freddys_qgis_project_info_layers.qlr
      expanded: true
      group: true
  - Background:
      checked: true
      expanded: true
      group: true
      child-nodes:
        - Landeskarten (grau):
            checked: true
            expanded: true
            provider: wms
            uri: contextualWMSLegend=0&crs=EPSG:2056&dpiMode=7&featureCount=10&format=image/jpeg&layers=ch.swisstopo.pixelkarte-grau&styles&url=https://wms.geo.admin.ch/?%0ASERVICE%3DWMS%0A%26VERSION%3D1.3.0%0A%26REQUEST%3DGetCapabilities

mapthemes:
  "French Theme":
    Street:
      style: french
      visible: true
      expanded: true
    Buildings:
      style: default
      visible: false
      expanded: true
  "Robot Theme":
    Street:
      style: robot
      expanded_items:
        [
          "{f6c29bf7-af28-4d88-8092-ee9568ac731f}",
          "{fc48a8d7-d774-46c7-97c7-74ecde13a3ec}",
        ]
      checked_items:
        [
          "{f6c29bf7-af28-4d88-8092-ee9568ac731f}",
          "{dc726dd5-d0d7-4275-be02-f6916df4fa29}",
        ]
    Buildings:
      style: default
      visible: true
      expanded: false
    Other_Layers_Group:
      group: true
      checked: true
      expanded: false
    Other_Layers_Group/SubGroup:
      group: true
      checked: true
      expanded: false

layerorder: []

variables:
  "first_variable": "This is a test value."
  "Another_Variable": "2"

layouts:
  "Layout One":
    templatefile: "../layouttemplate/freddys_qgis_project_layout_one.qpt"
  "Layout Three":
    templatefile: "../layouttemplate/freddys_qgis_project_layout_three.qpt"

```

## Most important functions
### projecttopping.ProjectTopping
A project configuration resulting in a YAML file that contains:
- layertree
- layerorder
- layer styles
- map themes
- project variables
- print layouts

QML style files, QLR layer definition files and the source of a layer can be linked in the YAML file and are exported to the specific folders.

#### `parse_project( project: QgsProject, export_settings: ExportSettings = ExportSettings()`
Parses a project into the ProjectTopping structure. Means the LayerTreeNodes are loaded into the layertree variable and append the ExportSettings to each node. The CustomLayerOrder is loaded into the layerorder. The project is not kept as member variable.

#### `generate_files(self, target: Target) -> str`
Generates all files according to the passed Target.
The target object containing the paths where to create the files and the path_resolver defining the structure of the link.

#### `load_files(self, target: Target)`
not yet implemented

#### `generate_project(self, target: Target) -> QgsProject`
not yet implemented

### target.Target
If there is no subdir it will look like:
```
    <maindir>
    ├── projecttopping
    │  └── <projectname>.yaml
    ├── layerstyle
    │  ├── <projectname>_<layername>.qml
    │  └── <projectname>_<layername>.qml
    └── layerdefinition
       └── <projectname>_<layername>.qlr
```
With subdir:
```
    <maindir>
    └── <subdir>
       ├── projecttopping
       │  └── <projectname>.yaml
       ├── layerstyle
       │  ├── <projectname>_<layername>.qml
       │  └── <projectname>_<layername>.qml
       └── layerdefinition
          └── <projectname>_<layername>.qlr
```

The `path_resolver` can be passed as a function. The default implementation lists the created toppingfiles (including the YAML) in the dict `Target.toppingfileinfo_list` with the `"path": <relative_filepath>, "type": <filetype>`.

#### `Target( projectname: str = "project", main_dir: str = None, sub_dir: str = None, path_resolver=None)`
The constructor of the target class to set up a target.
A member variable `toppingfileinfo_list = []` is defined, to store all the information according the `path_resolver`.

### exportsettings.ExportSettings

#### Layertree Settings
The requested export settings of each node in the specific dicts:
- qmlstyle_setting_nodes
- definition_setting_nodes
- source_setting_nodes


The usual structure is using QgsLayerTreeNode as key and then export True/False

```py
qmlstyle_nodes =
{
    <QgsLayerTreeNode(Node1)>: { export: False }
    <QgsLayerTreeNode(Node2)>: { export: True }
}
```

Alternatively the layername can be used as key. In ProjectTopping it first looks up the node and if not available the name.
Using the node is much more consistent, since one can use layers with the same name, but for nodes you need the project already in advance.
With name you can use prepared settings to pass (before the project exists) e.g. in automated workflows.
```py
qmlstyle_nodes =
{
    "Node1": { export: False }
    "Node2": { export: True }
}
```

For some settings we have additional info. Like in qmlstyle_nodes <QgsMapLayer.StyleCategories>. These are Flags, and can be constructed manually as well.
```py
qmlstyle_nodes =
{
    <QgsLayerTreeNode(Node1)>: { export: False }
    <QgsLayerTreeNode(Node2)>: { export: True, categories: <QgsMapLayer.StyleCategories> }
}
```

If styles are used as well we create tuples as key. Mutable objects are not alowed in it, so they would be created with the (layer) name and the style (name):
```py
qmlstyle_nodes =
{
    <QgsLayerTreeNode(Node1)>: { export: False }
    <QgsLayerTreeNode(Node2)>: { export: True, categories: <QgsMapLayer.StyleCategories> }
    ("Node2","french"): { export: True, categories: <QgsMapLayer.StyleCategories> },
    ("Node2","robot"): { export: True, categories: <QgsMapLayer.StyleCategories> }
}
```

##### `set_setting_values( type: ToppingType, node: Union[QgsLayerTreeLayer, QgsLayerTreeGroup] = None, name: str = None, export=True categories=None, style_name: str = None) -> bool`

Set the specific types concerning the enumerations:
```py
class ToppingType(Enum):
    QMLSTYLE = 1
    DEFINITION = 2
    SOURCE = 3

```
#### Map Themes Settings

The export setting of the map themes is a simple list of maptheme names: `mapthemes = []`

#### Custom Project Variables:

The export setting of the custom variables is simple list of the keys stored in `variables = []`.

#### Layouts:

The export setting of the print layouts is simple list of the layout names stored in `layouts = []`.

## Infos for Devs

### Code style

Is enforced with pre-commit. To use, make:
```
pip install pre-commit
pre-commit install
```
And to run it over all the files (with infile changes):
```
pre-commit run --color=always --all-file
```
