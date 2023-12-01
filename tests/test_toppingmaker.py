"""
/***************************************************************************
                              -------------------
        begin                : 2022-07-17
        git sha              : :%H$
        copyright            : (C) 2022 by Dave Signer
        email                : david at opengis ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import datetime
import logging
import os
import tempfile

import yaml
from qgis.core import (
    Qgis,
    QgsExpressionContextUtils,
    QgsMapThemeCollection,
    QgsPrintLayout,
    QgsProject,
    QgsVectorLayer,
)
from qgis.testing import start_app, unittest

from toppingmaker import ExportSettings, ProjectTopping, Target

start_app()


class ToppingMakerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Run before all tests."""
        cls.basetestpath = tempfile.mkdtemp()
        cls.projecttopping_test_path = os.path.join(cls.basetestpath, "projecttopping")

    def test_target(self):
        maindir = os.path.join(self.projecttopping_test_path, "freddys_repository")
        subdir = "freddys_projects/this_specific_project"
        filedirs = ["projecttopping", "layerstyle", "layerdefinition", "andanotherone"]
        target = Target("freddys", maindir, subdir)
        count = 0
        for filedir in filedirs:
            # filedir_path should create the dir
            path, _ = target.filedir_path(filedir)
            assert os.path.isdir(path)
            count += 1
        assert count == 4

    def test_parse_project(self):
        """
        Parse it without export settings...

        "Big Group":
            group: True
            child-nodes:
                - "Layer One":
                    checked: True
                - "Medium Group":
                    group: True
                    child-nodes:
                        - "Layer Two":
                        - "Small Group:
                            - "Layer Three":
                            - "Layer Four":
                        - "Layer Five":
        "All of em":
            group: True
            child-nodes:
                - "Layer One":
                    checked: False
                - "Layer Two":
                - "Layer Three":
                    checked: False
                - "Layer Four":
                - "Layer Five":
        """
        project, _ = self._make_project_and_export_settings()
        layers = project.layerTreeRoot().findLayers()
        self.assertEqual(len(layers), 10)

        project_topping = ProjectTopping()
        project_topping.parse_project(project)

        # check layertree
        checked_groups = []
        for item in project_topping.layertree.items:
            if item.name == "Big Group":
                assert len(item.items) == 2
                checked_groups.append("Big Group")
                for item in item.items:
                    if item.name == "Medium Group":
                        assert len(item.items) == 3
                        checked_groups.append("Medium Group")
                        for item in item.items:
                            if item.name == "Small Group":
                                assert len(item.items) == 2
                                checked_groups.append("Small Group")
        assert checked_groups == ["Big Group", "Medium Group", "Small Group"]

    def test_parse_project_with_mapthemes(self):
        """
        Parse it with export settings defining map themes, variables and layouts
        """
        project, export_settings = self._make_project_and_export_settings()

        project_topping = ProjectTopping()
        project_topping.parse_project(project, export_settings)

        # check mapthemes
        mapthemes = project_topping.mapthemes
        assert mapthemes["Robot Theme"]["Layer One"]
        assert mapthemes["Robot Theme"]["Layer One"]["style"] == "robot 1"
        assert mapthemes["Robot Theme"]["Layer Three"]
        assert mapthemes["Robot Theme"]["Layer Three"]["style"] == "robot 3"
        assert mapthemes["Robot Theme"]["Small Group"]
        assert mapthemes["Robot Theme"]["Small Group"]["expanded"]
        assert mapthemes["Robot Theme"]["Big Group"]
        assert mapthemes["Robot Theme"]["Big Group"]["expanded"]
        assert "Medium Group" not in mapthemes["Robot Theme"]

        assert set(mapthemes.keys()) == {"French Theme", "Robot Theme"}
        assert mapthemes["French Theme"]["Layer One"]
        assert mapthemes["French Theme"]["Layer One"]["style"] == "french 1"
        assert mapthemes["French Theme"]["Layer Three"]
        assert mapthemes["French Theme"]["Layer Three"]["style"] == "french 3"
        assert mapthemes["French Theme"]["Medium Group"]
        assert mapthemes["French Theme"]["Medium Group"]["expanded"]
        assert "Small Group" not in mapthemes["French Theme"]
        assert "Big Group" not in mapthemes["French Theme"]

        # check variables
        variables = project_topping.variables
        # Anyway in practice no spaces should be used to be able to access them in the expressions like @first_variable
        assert variables.get("First Variable") == "This is a test value."
        # QGIS is currently (3.29) not able to store structures in the project file. Still...
        assert variables.get("Variable with Structure") == [
            "Not",
            "The",
            "Normal",
            815,
            "Case",
        ]
        # "Another Variable" is in the project but not in the export_settings
        assert "Another Variable" not in variables

        # check layouts
        layouts = project_topping.layouts
        assert layouts.get("Layout One")
        assert layouts.get("Layout Three")
        # "Layout Two" is in the project but not in the export_settings
        assert "Layout Two" not in layouts

    def test_generate_files(self):
        """
        Generate projecttopping file with layertree, map themes, variables and layouts.
        And all the toppingfiles for styles, definition and layouttemplates.
        """
        project, export_settings = self._make_project_and_export_settings()
        layers = project.layerTreeRoot().findLayers()
        self.assertEqual(len(layers), 10)

        project_topping = ProjectTopping()
        project_topping.parse_project(project, export_settings)

        checked_groups = []
        for item in project_topping.layertree.items:
            if item.name == "Big Group":
                assert len(item.items) == 2
                checked_groups.append("Big Group")
                for item in item.items:
                    if item.name == "Medium Group":
                        assert len(item.items) == 3
                        checked_groups.append("Medium Group")
                        for item in item.items:
                            if item.name == "Small Group":
                                assert len(item.items) == 2
                                checked_groups.append("Small Group")
        assert checked_groups == ["Big Group", "Medium Group", "Small Group"]

        maindir = os.path.join(self.projecttopping_test_path, "freddys_repository")
        subdir = "freddys_projects/this_specific_project"

        target = Target("freddys", maindir, subdir)

        projecttopping_file_path = os.path.join(
            target.main_dir, project_topping.generate_files(target)
        )

        # check layertree projecttopping_file

        foundAllofEm = False
        foundLayerOne = False
        foundLayerTwo = False

        with open(projecttopping_file_path) as yamlfile:
            projecttopping_data = yaml.safe_load(yamlfile)
            assert "layertree" in projecttopping_data
            assert projecttopping_data["layertree"]
            for node in projecttopping_data["layertree"]:
                if "All of em" in node:
                    foundAllofEm = True
                    assert "child-nodes" in node["All of em"]
                    for childnode in node["All of em"]["child-nodes"]:
                        if "Layer One" in childnode:
                            foundLayerOne = True
                            assert "checked" in childnode["Layer One"]
                            assert not childnode["Layer One"]["checked"]
                        if "Layer Two" in childnode:
                            foundLayerTwo = True
                            assert "checked" in childnode["Layer Two"]
                            assert childnode["Layer Two"]["checked"]
        assert foundAllofEm
        assert foundLayerOne
        assert foundLayerTwo

        # check mapthemes in projecttopping_file

        foundFrenchTheme = False
        foundRobotTheme = False

        with open(projecttopping_file_path) as yamlfile:
            projecttopping_data = yaml.safe_load(yamlfile)
            assert "mapthemes" in projecttopping_data
            assert projecttopping_data["mapthemes"]
            for theme_name in projecttopping_data["mapthemes"].keys():
                if theme_name == "Robot Theme":
                    foundRobotTheme = True
                    expected_records = {
                        "Layer One",
                        "Layer Three",
                        "Small Group",
                        "Big Group",
                    }
                    assert expected_records == set(
                        projecttopping_data["mapthemes"]["Robot Theme"].keys()
                    )
                    checked_record_count = 0
                    for record_name in projecttopping_data["mapthemes"][
                        "Robot Theme"
                    ].keys():
                        if record_name == "Layer One":
                            assert (
                                "style"
                                in projecttopping_data["mapthemes"]["Robot Theme"][
                                    "Layer One"
                                ]
                            )
                            assert (
                                projecttopping_data["mapthemes"]["Robot Theme"][
                                    "Layer One"
                                ]["style"]
                                == "robot 1"
                            )
                            assert (
                                "visible"
                                in projecttopping_data["mapthemes"]["Robot Theme"][
                                    "Layer One"
                                ]
                            )
                            assert not projecttopping_data["mapthemes"]["Robot Theme"][
                                "Layer One"
                            ]["visible"]
                            checked_record_count += 1
                        if record_name == "Layer Three":
                            assert (
                                "style"
                                in projecttopping_data["mapthemes"]["Robot Theme"][
                                    "Layer Three"
                                ]
                            )
                            assert (
                                projecttopping_data["mapthemes"]["Robot Theme"][
                                    "Layer Three"
                                ]["style"]
                                == "robot 3"
                            )
                            assert (
                                "visible"
                                in projecttopping_data["mapthemes"]["Robot Theme"][
                                    "Layer Three"
                                ]
                            )
                            assert projecttopping_data["mapthemes"]["Robot Theme"][
                                "Layer Three"
                            ]["visible"]
                            checked_record_count += 1
                        if record_name == "Small Group":
                            assert (
                                "expanded"
                                in projecttopping_data["mapthemes"]["Robot Theme"][
                                    "Small Group"
                                ]
                            )
                            assert projecttopping_data["mapthemes"]["Robot Theme"][
                                "Small Group"
                            ]["expanded"]
                            checked_record_count += 1
                        if record_name == "Big Group":
                            assert (
                                "expanded"
                                in projecttopping_data["mapthemes"]["Robot Theme"][
                                    "Big Group"
                                ]
                            )
                            assert projecttopping_data["mapthemes"]["Robot Theme"][
                                "Big Group"
                            ]["expanded"]
                            checked_record_count += 1
                    assert checked_record_count == 4
                if theme_name == "French Theme":
                    foundFrenchTheme = True
                    expected_records = {"Layer One", "Layer Three", "Medium Group"}
                    assert expected_records == set(
                        projecttopping_data["mapthemes"]["French Theme"].keys()
                    )
                    checked_record_count = 0
                    for record_name in projecttopping_data["mapthemes"][
                        "French Theme"
                    ].keys():
                        if record_name == "Layer One":
                            assert (
                                "style"
                                in projecttopping_data["mapthemes"]["French Theme"][
                                    "Layer One"
                                ]
                            )
                            assert (
                                projecttopping_data["mapthemes"]["French Theme"][
                                    "Layer One"
                                ]["style"]
                                == "french 1"
                            )
                            assert (
                                "visible"
                                in projecttopping_data["mapthemes"]["French Theme"][
                                    "Layer One"
                                ]
                            )
                            assert projecttopping_data["mapthemes"]["French Theme"][
                                "Layer One"
                            ]["visible"]
                            checked_record_count += 1
                        if record_name == "Layer Three":
                            assert (
                                "style"
                                in projecttopping_data["mapthemes"]["French Theme"][
                                    "Layer Three"
                                ]
                            )
                            assert (
                                projecttopping_data["mapthemes"]["French Theme"][
                                    "Layer Three"
                                ]["style"]
                                == "french 3"
                            )
                            assert (
                                "visible"
                                in projecttopping_data["mapthemes"]["French Theme"][
                                    "Layer Three"
                                ]
                            )
                            assert not projecttopping_data["mapthemes"]["French Theme"][
                                "Layer Three"
                            ]["visible"]
                            checked_record_count += 1
                        if record_name == "Medium Group":
                            assert (
                                "expanded"
                                in projecttopping_data["mapthemes"]["French Theme"][
                                    "Medium Group"
                                ]
                            )
                            assert projecttopping_data["mapthemes"]["French Theme"][
                                "Medium Group"
                            ]["expanded"]
                            checked_record_count += 1
                    assert checked_record_count == 3

        assert foundFrenchTheme
        assert foundRobotTheme

        # check variables
        variable_count = 0
        foundFirstVariable = False
        foundVariableWithStructure = False

        with open(projecttopping_file_path) as yamlfile:
            projecttopping_data = yaml.safe_load(yamlfile)
            assert "variables" in projecttopping_data
            assert projecttopping_data["variables"]
            for variable_key in projecttopping_data["variables"].keys():
                if variable_key == "First Variable":
                    assert (
                        projecttopping_data["variables"][variable_key]
                        == "This is a test value."
                    )
                    foundFirstVariable = True
                if variable_key == "Variable with Structure":
                    assert projecttopping_data["variables"][variable_key] == [
                        "Not",
                        "The",
                        "Normal",
                        815,
                        "Case",
                    ]
                    foundVariableWithStructure = True
                variable_count += 1

        assert variable_count == 2
        assert foundFirstVariable
        assert foundVariableWithStructure

        # check transaction mode
        with open(projecttopping_file_path) as yamlfile:
            projecttopping_data = yaml.safe_load(yamlfile)
            assert "properties" in projecttopping_data
            if Qgis.QGIS_VERSION_INT < 32600:
                assert projecttopping_data["properties"]["transaction_mode"] == True
            else:
                assert (
                    projecttopping_data["properties"]["transaction_mode"]
                    == "AutomaticGroups"
                )

        # check layouts
        layout_count = 0
        foundLayoutOne = False
        foundLayoutThree = False

        with open(projecttopping_file_path) as yamlfile:
            projecttopping_data = yaml.safe_load(yamlfile)
            assert "layouts" in projecttopping_data
            assert projecttopping_data["layouts"]
            for layout_name in projecttopping_data["layouts"].keys():
                if layout_name == "Layout One":
                    assert "templatefile" in projecttopping_data["layouts"][layout_name]
                    foundLayoutOne = True
                if layout_name == "Layout Three":
                    assert "templatefile" in projecttopping_data["layouts"][layout_name]
                    foundLayoutThree = True
                layout_count += 1

        assert layout_count == 2
        assert foundLayoutOne
        assert foundLayoutThree

        # check toppingfiles

        # there should be exported 6 files (see _make_project_and_export_settings)
        # stylefiles:
        # "Layer One"
        # "Layer Three"
        # "Layer Five"
        #
        # definitionfiles:
        # "Layer Three"
        # "Layer Four"
        # "Layer Five"

        countchecked = 0

        # there should be 21 toppingfiles:
        # - one project topping
        # - 2 x 3 qlr files (two times since the layers are multiple times in the tree)
        # - 2 x 6 qml files (one layers with 3 styles, one layer with 2 styles and one layer with one style - and two times since the layers are multiple times in the tree)
        # - 2 qpt template files
        assert len(target.toppingfileinfo_list) == 21

        for toppingfileinfo in target.toppingfileinfo_list:
            self.print_info(toppingfileinfo["path"])
            assert "path" in toppingfileinfo
            assert "type" in toppingfileinfo

            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerstyle/freddys_layer_one.qml"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerstyle/freddys_layer_one_french_1.qml"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerstyle/freddys_layer_one_robot_1.qml"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerstyle/freddys_layer_three.qml"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerstyle/freddys_layer_three_french_3.qml"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerstyle/freddys_layer_five.qml"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerdefinition/freddys_layer_three.qlr"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerdefinition/freddys_layer_four.qlr"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layerdefinition/freddys_layer_five.qlr"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layouttemplate/freddys_layout_one.qpt"
            ):
                countchecked += 1
            if (
                toppingfileinfo["path"]
                == "freddys_projects/this_specific_project/layouttemplate/freddys_layout_three.qpt"
            ):
                countchecked += 1

        # without the projecttopping file they are 20
        assert countchecked == 20

    def test_custom_path_resolver(self):
        # load QGIS project into structure
        project_topping = ProjectTopping()
        project, export_settings = self._make_project_and_export_settings()
        project_topping.parse_project(project, export_settings)

        # create target with path resolver
        maindir = os.path.join(self.projecttopping_test_path, "freddys_repository")
        subdir = "freddys_projects/this_specific_project"

        target = Target("freddys", maindir, subdir, custom_path_resolver)

        project_topping.generate_files(target)

        # there should be exported 6 files (see _make_project_and_export_settings)
        # stylefiles:
        # "Layer One"
        # "Layer Three"
        # "Layer Five"
        #
        # definitionfiles:
        # "Layer Three"
        # "Layer Four"
        # "Layer Five"

        countchecked = 0
        for toppingfileinfo in target.toppingfileinfo_list:
            assert "id" in toppingfileinfo
            assert "path" in toppingfileinfo
            assert "type" in toppingfileinfo
            assert "version" in toppingfileinfo

            if toppingfileinfo["id"] == "layerstyle_freddys_layer_one.qml_001":
                countchecked += 1
            if toppingfileinfo["id"] == "layerstyle_freddys_layer_three.qml_001":
                countchecked += 1
            if toppingfileinfo["id"] == "layerstyle_freddys_layer_five.qml_001":
                countchecked += 1
            if toppingfileinfo["id"] == "layerdefinition_freddys_layer_three.qlr_001":
                countchecked += 1
            if toppingfileinfo["id"] == "layerdefinition_freddys_layer_four.qlr_001":
                countchecked += 1
            if toppingfileinfo["id"] == "layerdefinition_freddys_layer_five.qlr_001":
                countchecked += 1

        assert countchecked == 6

    def _make_project_and_export_settings(self):
        # ---
        # make the project
        # ---
        project = QgsProject()
        project.removeAllMapLayers()

        l1 = QgsVectorLayer(
            "point?crs=epsg:4326&field=id:integer", "Layer One", "memory"
        )
        assert l1.isValid()
        l2 = QgsVectorLayer(
            "point?crs=epsg:4326&field=id:integer", "Layer Two", "memory"
        )
        assert l2.isValid()
        l3 = QgsVectorLayer(
            "point?crs=epsg:4326&field=id:integer", "Layer Three", "memory"
        )
        assert l3.isValid()
        l4 = QgsVectorLayer(
            "point?crs=epsg:4326&field=id:integer", "Layer Four", "memory"
        )
        assert l4.isValid()
        l5 = QgsVectorLayer(
            "point?crs=epsg:4326&field=id:integer", "Layer Five", "memory"
        )
        assert l5.isValid()

        # append style to layer one and three
        style_manager = l1.styleManager()
        l1.setDisplayExpression("'French:'||'un'")
        style_manager.addStyleFromLayer("french 1")
        l1.setDisplayExpression("'Robot:'||'0001'")
        style_manager.addStyleFromLayer("robot 1")
        style_manager.setCurrentStyle("default")

        style_manager = l3.styleManager()
        l3.setDisplayExpression("'French:'||'trois'")
        style_manager.addStyleFromLayer("french 3")
        l3.setDisplayExpression("'Robot:'||'0011'")
        style_manager.addStyleFromLayer("robot 3")
        style_manager.setCurrentStyle("default")

        project.addMapLayer(l1, False)
        project.addMapLayer(l2, False)
        project.addMapLayer(l3, False)
        project.addMapLayer(l4, False)
        project.addMapLayer(l5, False)

        biggroup = project.layerTreeRoot().addGroup("Big Group")
        biggroup.addLayer(l1)
        mediumgroup = biggroup.addGroup("Medium Group")
        mediumgroup.addLayer(l2)
        smallgroup = mediumgroup.addGroup("Small Group")
        smallgroup.addLayer(l3)
        smallgroup.addLayer(l4)
        mediumgroup.addLayer(l5)
        allofemgroup = project.layerTreeRoot().addGroup("All of em")
        node1 = allofemgroup.addLayer(l1)
        node1.setItemVisibilityChecked(False)
        allofemgroup.addLayer(l2)
        node3 = allofemgroup.addLayer(l3)
        node3.setItemVisibilityChecked(False)
        allofemgroup.addLayer(l4)
        allofemgroup.addLayer(l5)

        # create robot map theme
        # with styles and layer one unchecked
        map_theme_record = QgsMapThemeCollection.MapThemeRecord()
        map_theme_layer_record = QgsMapThemeCollection.MapThemeLayerRecord()
        map_theme_layer_record.setLayer(l1)
        map_theme_layer_record.usingCurrentStyle = True
        map_theme_layer_record.currentStyle = "robot 1"
        map_theme_layer_record.isVisible = False
        map_theme_record.addLayerRecord(map_theme_layer_record)
        map_theme_layer_record = QgsMapThemeCollection.MapThemeLayerRecord()
        map_theme_layer_record.setLayer(l3)
        map_theme_layer_record.usingCurrentStyle = True
        map_theme_layer_record.currentStyle = "robot 3"
        map_theme_layer_record.isVisible = True
        map_theme_record.addLayerRecord(map_theme_layer_record)
        # group Big and Small expanded, Medium not expanded
        map_theme_record.setHasExpandedStateInfo(True)
        map_theme_record.setExpandedGroupNodes(["Small Group", "Big Group"])
        project.mapThemeCollection().insert("Robot Theme", map_theme_record)

        # create french map theme
        # with styles and layer three unchecked
        map_theme_record = QgsMapThemeCollection.MapThemeRecord()
        map_theme_layer_record = QgsMapThemeCollection.MapThemeLayerRecord()
        map_theme_layer_record.setLayer(l1)
        map_theme_layer_record.usingCurrentStyle = True
        map_theme_layer_record.currentStyle = "french 1"
        map_theme_layer_record.isVisible = True
        map_theme_record.addLayerRecord(map_theme_layer_record)
        map_theme_layer_record = QgsMapThemeCollection.MapThemeLayerRecord()
        map_theme_layer_record.setLayer(l3)
        map_theme_layer_record.usingCurrentStyle = True
        map_theme_layer_record.currentStyle = "french 3"
        map_theme_layer_record.isVisible = False
        map_theme_record.addLayerRecord(map_theme_layer_record)
        # group Medium expanded, Big and Small not expanded
        map_theme_record.setHasExpandedStateInfo(True)
        map_theme_record.setExpandedGroupNodes(["Medium Group"])
        project.mapThemeCollection().insert("French Theme", map_theme_record)

        # set the custom project variables
        QgsExpressionContextUtils.setProjectVariable(
            project, "First Variable", "This is a test value."
        )
        QgsExpressionContextUtils.setProjectVariable(project, "Another Variable", "2")
        QgsExpressionContextUtils.setProjectVariable(
            project, "Variable with Structure", ["Not", "The", "Normal", 815, "Case"]
        )

        # create layouts
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName("Layout One")
        project.layoutManager().addLayout(layout)
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName("Layout Two")
        project.layoutManager().addLayout(layout)
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName("Layout Three")
        project.layoutManager().addLayout(layout)

        # set transaction mode
        if Qgis.QGIS_VERSION_INT < 32600:
            project.setAutoTransaction(True)
        else:
            project.setTransactionMode(Qgis.TransactionMode.AutomaticGroups)

        # ---
        # and make the export settings
        # ---
        export_settings = ExportSettings()
        export_settings.set_setting_values(
            ExportSettings.ToppingType.QMLSTYLE, None, "Layer One", True
        )
        # exporting "french" and "robot" style to layer one
        export_settings.set_setting_values(
            ExportSettings.ToppingType.QMLSTYLE,
            None,
            "Layer One",
            True,
            None,
            "french 1",
        )
        export_settings.set_setting_values(
            ExportSettings.ToppingType.QMLSTYLE,
            None,
            "Layer One",
            True,
            None,
            "robot 1",
        )
        # only exporting "french" style to layer three
        export_settings.set_setting_values(
            ExportSettings.ToppingType.QMLSTYLE, None, "Layer Three", True
        )
        export_settings.set_setting_values(
            ExportSettings.ToppingType.QMLSTYLE,
            None,
            "Layer Three",
            True,
            None,
            "french 3",
        )
        export_settings.set_setting_values(
            ExportSettings.ToppingType.QMLSTYLE, None, "Layer Five", True
        )

        export_settings.set_setting_values(
            ExportSettings.ToppingType.DEFINITION, None, "Layer Three", True
        )
        export_settings.set_setting_values(
            ExportSettings.ToppingType.DEFINITION, None, "Layer Four", True
        )
        export_settings.set_setting_values(
            ExportSettings.ToppingType.DEFINITION, None, "Layer Five", True
        )

        export_settings.set_setting_values(
            ExportSettings.ToppingType.SOURCE, None, "Layer One", True
        )
        export_settings.set_setting_values(
            ExportSettings.ToppingType.SOURCE, None, "Layer Two", True
        )
        export_settings.set_setting_values(
            ExportSettings.ToppingType.SOURCE, None, "Layer Three", True
        )

        # define the map themes to export
        export_settings.mapthemes = ["French Theme", "Robot Theme"]

        # define the custom variables to export
        export_settings.variables = ["First Variable", "Variable with Structure"]

        # define the layouts to export
        export_settings.layouts = ["Layout One", "Layout Three"]

        self.print_info(
            f" Layer to style export: {export_settings.qmlstyle_setting_nodes}"
        )
        self.print_info(
            f" Layer to definition export: {export_settings.definition_setting_nodes}"
        )
        self.print_info(
            f" Layer to source export: {export_settings.source_setting_nodes}"
        )
        self.print_info(f" Map Themes to export: {export_settings.mapthemes}")
        return project, export_settings

    def print_info(self, text):
        logging.info(text)

    def print_error(self, text):
        logging.error(text)


def custom_path_resolver(target: Target, name, type):
    _, relative_filedir_path = target.filedir_path(type)
    id = unique_id_in_target_scope(target, f"{type}_{name}_001")
    path = os.path.join(relative_filedir_path, name)
    type = type
    version = datetime.datetime.now().strftime("%Y-%m-%d")
    toppingfile = {"id": id, "path": path, "type": type, "version": version}
    target.toppingfileinfo_list.append(toppingfile)
    return path


def unique_id_in_target_scope(target: Target, id):
    for toppingfileinfo in target.toppingfileinfo_list:
        if "id" in toppingfileinfo and toppingfileinfo["id"] == id:
            iterator = int(id[-3:])
            iterator += 1
            id = f"{id[:-3]}{iterator:03}"
            return unique_id_in_target_scope(target, id)
    return id
