# -*- coding: utf-8 -*-
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

import logging
import os
import tempfile
from typing import Union

import yaml
from qgis.core import (
    Qgis,
    QgsDataSourceUri,
    QgsExpressionContextUtils,
    QgsLayerDefinition,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsMapLayer,
    QgsProject,
    QgsReadWriteContext,
)
from qgis.PyQt.QtCore import QObject, pyqtSignal

from .exportsettings import ExportSettings
from .target import Target
from .utils import slugify


class ProjectTopping(QObject):
    """
    A project configuration resulting in a YAML file that contains:
    - layertree
    - layerorder
    - project variables (future)
    - print layout (future)
    - map themes (future)

    QML style files, QLR layer definition files and the source of a layer can be linked in the YAML file and are exported to the specific folders.
    """

    stdout = pyqtSignal(str, int)

    PROJECTTOPPING_TYPE = "projecttopping"
    LAYERDEFINITION_TYPE = "layerdefinition"
    LAYERSTYLE_TYPE = "layerstyle"
    LAYOUTTEMPLATE_TYPE = "layouttemplate"

    class TreeItemProperties(object):
        """
        The properties of a node (tree item)
        """

        class StyleItemProperties(object):
            """
            The properties of a style item of a node style.
            Currently it's only a qmlstylefile. Maybe in future here a style can be defined.
            """

            def __init__(self):
                # the style file - if None then not requested
                self.qmlstylefile = None

        def __init__(self):
            # if the node is a group
            self.group = False
            # if the node is visible
            self.checked = True
            # if the node is expanded
            self.expanded = True
            # if the (layer) node shows feature count
            self.featurecount = False
            # if the (group) node handles mutually-exclusive
            self.mutually_exclusive = False
            # if the (group) node handles mutually-exclusive, the index of the checked child
            self.mutually_exclusive_child = -1
            # the layers provider to create it from source
            self.provider = None
            # the layers uri to create it from source
            self.uri = None
            # the style file - if None then not requested
            self.qmlstylefile = None
            # the definition file - if None then not requested
            self.definitionfile = None
            # the table name (if no source available)
            self.tablename = None
            # the geometry column (if no source available)
            self.geometrycolumn = None
            # the styles can contain multiple style items with StyleItemProperties
            self.styles = {}

    class LayerTreeItem(object):
        """
        A tree item of the layer tree. Every item contains the properties of a layer and according the ExportSettings passed on parsing the QGIS project.
        """

        def __init__(self, temporary_toppingfile_dir=None):
            self.items = []
            self.name = None
            self.properties = ProjectTopping.TreeItemProperties()
            self.temporary_toppingfile_dir = temporary_toppingfile_dir
            if not self.temporary_toppingfile_dir:
                self.temporary_toppingfile_dir = tempfile.mkdtemp()

        def make_item(
            self,
            project: QgsProject,
            node: Union[QgsLayerTreeLayer, QgsLayerTreeGroup],
            export_settings: ExportSettings,
        ):
            # properties for every kind of nodes
            self.name = node.name()
            self.properties.checked = node.itemVisibilityChecked()
            self.properties.expanded = node.isExpanded()

            definition_setting = export_settings.get_setting(
                ExportSettings.ToppingType.DEFINITION, node, node.name()
            )
            if definition_setting.get("export", False):
                self.properties.definitionfile = self._temporary_definitionfile(node)

            if isinstance(node, QgsLayerTreeGroup):
                # it's a group
                self.properties.group = True
                self.properties.mutually_exclusive = node.isMutuallyExclusive()

                if not definition_setting.get("export", False):
                    # only consider children, when the group is not exported as DEFINITION
                    index = 0
                    for child in node.children():
                        item = ProjectTopping.LayerTreeItem(
                            self.temporary_toppingfile_dir
                        )
                        item.make_item(project, child, export_settings)
                        # set the first checked item as mutually exclusive child
                        if (
                            self.properties.mutually_exclusive
                            and self.properties.mutually_exclusive_child == -1
                        ):
                            if item.properties.checked:
                                self.properties.mutually_exclusive_child = index
                        self.items.append(item)
                        index += 1
            else:
                if isinstance(node, QgsLayerTreeLayer):
                    layer = node.layer()
                else:
                    # must be not recognized as QgsLayerTreeLayer (but QgsLayerTreeNode instead)
                    layer = self._layer_of_node(project, node)
                self.properties.featurecount = node.customProperty("showFeatureCount")
                source_setting = export_settings.get_setting(
                    ExportSettings.ToppingType.SOURCE, node, node.name()
                )
                if source_setting.get("export", False):
                    if layer.dataProvider():
                        self.properties.provider = layer.dataProvider().name()
                        self.properties.uri = (
                            QgsProject.instance()
                            .pathResolver()
                            .writePath(layer.publicSource())
                        )

                # if neither a definition file nor the source should be exported we store the tablename (and the geometry column)
                if not definition_setting.get(
                    "export", False
                ) and not source_setting.get("export", False):
                    provider = layer.dataProvider()
                    if provider:
                        # supported providers are postgres, mssql and GPKG (ogr)
                        if provider.name() == "postgres" or provider.name() == "mssql":
                            self.properties.tablename = QgsDataSourceUri(
                                provider.dataSourceUri()
                            ).table()
                            self.properties.geometry = QgsDataSourceUri(
                                provider.dataSourceUri()
                            ).geometryColumn()
                        elif (
                            provider.name() == "ogr"
                            and provider.storageType() == "GPKG"
                        ):
                            self.properties.tablename = (
                                provider.dataSourceUri().split("layername=")[1].strip()
                            )

                # get the default style
                qml_default_setting = export_settings.get_setting(
                    ExportSettings.ToppingType.QMLSTYLE, node, node.name()
                ) or export_settings.get_setting(
                    ExportSettings.ToppingType.QMLSTYLE, node, node.name(), "default"
                )

                if qml_default_setting.get("export", False):
                    self.properties.qmlstylefile = self._temporary_qmlstylefile(
                        layer,
                        QgsMapLayer.StyleCategory(
                            qml_default_setting.get(
                                "categories",
                                QgsMapLayer.StyleCategory.AllStyleCategories,
                            )
                        ),
                    )

                # get all the other styles
                current_style = layer.styleManager().currentStyle()
                for style_name in layer.styleManager().styles():
                    # we skip the 'default' style because it's handled above
                    if style_name == "default":
                        continue

                    qml_style_setting = export_settings.get_setting(
                        ExportSettings.ToppingType.QMLSTYLE,
                        node,
                        node.name(),
                        style_name,
                    )
                    if qml_style_setting.get("export", False):
                        style_properties = (
                            ProjectTopping.TreeItemProperties.StyleItemProperties()
                        )
                        style_properties.qmlstylefile = self._temporary_qmlstylefile(
                            layer,
                            QgsMapLayer.StyleCategory(
                                qml_style_setting.get(
                                    "categories",
                                    QgsMapLayer.StyleCategory.AllStyleCategories,
                                )
                            ),
                            style_name,
                        )
                        self.properties.styles[style_name] = style_properties
                # reset the style of the project layer
                layer.styleManager().setCurrentStyle(current_style)

        def _layer_of_node(
            self,
            project: QgsProject,
            node: QgsLayerTreeNode,
        ) -> QgsLayerTreeLayer:
            # workaround when layer has not been detected as QgsLayerTreeLayer.
            # See https://github.com/opengisch/QgisModelBaker/pull/514
            return project.mapLayersByName(node.name())[0]

        def _temporary_definitionfile(
            self, node: Union[QgsLayerTreeLayer, QgsLayerTreeGroup]
        ):
            filename_slug = f"{slugify(self.name)}.qlr"
            os.makedirs(self.temporary_toppingfile_dir, exist_ok=True)
            temporary_toppingfile_path = os.path.join(
                self.temporary_toppingfile_dir, filename_slug
            )
            result, result_message = QgsLayerDefinition.exportLayerDefinition(
                temporary_toppingfile_path, [node]
            )
            if not result:
                logging.warning(
                    "Could not export definitionfile of {} to {}: {}".format(
                        node.name(), temporary_toppingfile_path, result_message
                    )
                )
            return temporary_toppingfile_path

        def _temporary_qmlstylefile(
            self,
            layer: QgsMapLayer,
            categories: QgsMapLayer.StyleCategories = QgsMapLayer.StyleCategory.AllStyleCategories,
            style_name: str = None,
        ):
            filename_slug = f"{slugify(self.name)}{f'_{slugify(style_name)}' if style_name else ''}.qml"
            os.makedirs(self.temporary_toppingfile_dir, exist_ok=True)
            temporary_toppingfile_path = os.path.join(
                self.temporary_toppingfile_dir, filename_slug
            )
            if style_name:
                layer.styleManager().setCurrentStyle(style_name)
            result_message, result = layer.saveNamedStyle(
                temporary_toppingfile_path, categories
            )
            if not result:
                logging.warning(
                    "Could not export qmlstylefile of {} ({}) to {}: {}".format(
                        layer.name(),
                        style_name,
                        temporary_toppingfile_path,
                        result_message,
                    )
                )
            return temporary_toppingfile_path

        def item_dict(self, target: Target):
            item_dict = {}
            item_properties_dict = {}

            if self.properties.group:
                item_properties_dict["group"] = True
                if self.properties.mutually_exclusive:
                    item_properties_dict["mutually-exclusive"] = True
                    item_properties_dict[
                        "mutually-exclusive-child"
                    ] = self.properties.mutually_exclusive_child
            else:
                if self.properties.tablename:
                    item_properties_dict["tablename"] = self.properties.tablename
                    if self.properties.geometrycolumn:
                        item_properties_dict[
                            "geometrycolumn"
                        ] = self.properties.geometrycolumn
                if self.properties.featurecount:
                    item_properties_dict["featurecount"] = True
                if self.properties.qmlstylefile:
                    item_properties_dict["qmlstylefile"] = target.toppingfile_link(
                        ProjectTopping.LAYERSTYLE_TYPE, self.properties.qmlstylefile
                    )
                if self.properties.styles:
                    item_properties_dict["styles"] = {}
                    for style_name in self.properties.styles.keys():
                        item_properties_dict["styles"][style_name] = {}
                        item_properties_dict["styles"][style_name][
                            "qmlstylefile"
                        ] = target.toppingfile_link(
                            ProjectTopping.LAYERSTYLE_TYPE,
                            self.properties.styles[style_name].qmlstylefile,
                        )
                if self.properties.provider and self.properties.uri:
                    item_properties_dict["provider"] = self.properties.provider
                    item_properties_dict["uri"] = self.properties.uri

            item_properties_dict["checked"] = self.properties.checked
            item_properties_dict["expanded"] = self.properties.expanded

            if self.properties.definitionfile:
                item_properties_dict["definitionfile"] = target.toppingfile_link(
                    ProjectTopping.LAYERDEFINITION_TYPE,
                    self.properties.definitionfile,
                )

            if self.items:
                child_item_dict_list = self.items_list(target)
                item_properties_dict["child-nodes"] = child_item_dict_list

            item_dict[self.name] = item_properties_dict
            return item_dict

        def items_list(self, target: Target):
            item_list = []
            for item in self.items:
                item_dict = item.item_dict(target)
                item_list.append(item_dict)
            return item_list

    class MapThemes(dict):
        """
        A dict object of dict items describing a MapThemeRecord according to the maptheme names listed in the ExportSettings passed on parsing the QGIS project.
        """

        def make_items(
            self,
            project: QgsProject,
            export_settings: ExportSettings,
        ):
            self.clear()

            maptheme_collection = project.mapThemeCollection()
            for name in export_settings.mapthemes:
                maptheme_item = {}
                maptheme_record = maptheme_collection.mapThemeState(name)
                for layerrecord in maptheme_record.layerRecords():
                    layername = layerrecord.layer().name()
                    maptheme_item[layername] = {}
                    if layerrecord.usingCurrentStyle:
                        maptheme_item[layername]["style"] = layerrecord.currentStyle
                    maptheme_item[layername]["visible"] = layerrecord.isVisible
                    maptheme_item[layername]["expanded"] = layerrecord.expandedLayerNode
                    if layerrecord.expandedLegendItems:
                        maptheme_item[layername][
                            "expanded_items"
                        ] = layerrecord.expandedLegendItems
                    if layerrecord.usingLegendItems:
                        maptheme_item[layername][
                            "checked_items"
                        ] = layerrecord.checkedLegendItems

                if maptheme_record.hasExpandedStateInfo():
                    for expanded_groupnode in maptheme_record.expandedGroupNodes():
                        maptheme_item[expanded_groupnode] = {}
                        maptheme_item[expanded_groupnode]["expanded"] = True
                # setHasCheckedStateInfo(True) is not available in the API, what makes it impossible to control the checked state of a group
                # see https://github.com/SebastienPeillet/QGIS/commit/736e46daa640b8a9c66107b4f05319d6d2534ac5#discussion_r1037225879
                for checked_groupnode in maptheme_record.checkedGroupNodes():
                    maptheme_item[checked_groupnode] = {}
                    maptheme_item[checked_groupnode]["checked"] = True

                self[name] = maptheme_item

    class Variables(dict):
        """
        A dict object of dict items describing a variable according to the variable keys listed in the ExportSettings passed on parsing the QGIS project.
        """

        def make_items(
            self,
            project: QgsProject,
            export_settings: ExportSettings,
        ):
            self.clear()
            for variable_key in export_settings.variables:
                self[variable_key] = QgsExpressionContextUtils.projectScope(
                    project
                ).variable(variable_key)

    class Layouts(dict):
        """
        A dict object of dict items describing a layout with templatefile according to the layout names listed in the ExportSettings passed on parsing the QGIS project.
        Such a dict item contains only one key at the moment: "templatefile"
        """

        def __init__(self, temporary_toppingfile_dir=None):
            self.temporary_toppingfile_dir = temporary_toppingfile_dir
            if not self.temporary_toppingfile_dir:
                self.temporary_toppingfile_dir = tempfile.mkdtemp()

        def make_items(
            self,
            project: QgsProject,
            export_settings: ExportSettings,
        ):
            self.clear()

            # go through all the print layouts in the project and export the requested ones
            for layout in project.layoutManager().printLayouts():
                if layout.name() in export_settings.layouts:
                    self[layout.name()] = {}

                    filename_slug = f"{slugify(layout.name())}.qpt"
                    os.makedirs(self.temporary_toppingfile_dir, exist_ok=True)
                    temporary_toppingfile_path = os.path.join(
                        self.temporary_toppingfile_dir, filename_slug
                    )
                    context = QgsReadWriteContext()
                    result = layout.saveAsTemplate(temporary_toppingfile_path, context)
                    if not result:
                        result_message = ", ".join(
                            [
                                message.message()
                                for message in context.takeMessages()
                                if message.level == Qgis.MessageLevel.Warning
                            ]
                        )
                        logging.warning(
                            "Could not export layout template of {} to {}: {}".format(
                                layout.name(),
                                temporary_toppingfile_path,
                                result_message,
                            )
                        )
                    self[layout.name()]["templatefile"] = temporary_toppingfile_path

        def item_dict(self, target: Target):
            resolved_items = {}
            for layout_name in self.keys():
                resolved_item = {}
                resolved_item["templatefile"] = target.toppingfile_link(
                    ProjectTopping.LAYOUTTEMPLATE_TYPE,
                    self[layout_name]["templatefile"],
                )
                resolved_items[layout_name] = resolved_item
            return resolved_items

    def __init__(self):
        QObject.__init__(self)
        temporary_toppingfile_dir = tempfile.mkdtemp(
            prefix="toppingmaker_temporary_files_"
        )

        self.layertree = self.LayerTreeItem(temporary_toppingfile_dir)
        self.mapthemes = self.MapThemes()
        self.layerorder = []
        self.variables = self.Variables()
        self.layouts = self.Layouts(temporary_toppingfile_dir)

    def parse_project(
        self, project: QgsProject, export_settings: ExportSettings = ExportSettings()
    ):
        """
        Parses a project into the ProjectTopping structure. Means the LayerTreeNodes are loaded into the layertree variable and append the ExportSettings to each node. The CustomLayerOrder is loaded into the layerorder. The project is not keeped as member variable.

        :param QgsProject project: the project to parse.
        :param ExportSettings settings: defining if the node needs a source or style / definitionfiles.
        """
        root = project.layerTreeRoot()
        if root:
            # make layertree
            self.layertree.make_item(project, project.layerTreeRoot(), export_settings)
            self.stdout.emit(
                self.tr("QGIS project layertree parsed with export settings."),
                Qgis.Info,
            )
            # make layerorder
            layerorder_layers = (
                root.customLayerOrder() if root.hasCustomLayerOrder() else []
            )
            if layerorder_layers:
                self.layerorder = [layer.name() for layer in layerorder_layers]
            self.stdout.emit(self.tr("QGIS project layerorder parsed."), Qgis.Info)
            # make mapthemes
            self.mapthemes.make_items(project, export_settings)
            # make variables
            self.variables.make_items(project, export_settings)
            # make print layouts
            self.layouts.make_items(project, export_settings)

            self.stdout.emit(
                self.tr("QGIS project map themes parsed with export settings."),
                Qgis.Info,
            )
        else:
            self.stdout.emit(
                self.tr("Could not parse the QGIS project..."), Qgis.Warning
            )
            return False
        return True

    def generate_files(self, target: Target) -> str:
        """
        Generates all files according to the passed Target.

        :param Target target: the target object containing the paths where to create the files and the path_resolver defining the structure of the link.
        """
        # generate projecttopping as a dict
        projecttopping_dict = self._projecttopping_dict(target)

        # write the yaml
        projecttopping_slug = f"{slugify(target.projectname)}.yaml"
        absolute_filedir_path, relative_filedir_path = target.filedir_path(
            ProjectTopping.PROJECTTOPPING_TYPE
        )
        with open(
            os.path.join(absolute_filedir_path, projecttopping_slug), "w"
        ) as projecttopping_yamlfile:
            yaml.dump(projecttopping_dict, projecttopping_yamlfile)
            self.stdout.emit(
                self.tr("Project Topping written to YAML file: {}").format(
                    projecttopping_yamlfile
                ),
                Qgis.Info,
            )
        return target.path_resolver(
            target, projecttopping_slug, ProjectTopping.PROJECTTOPPING_TYPE
        )

    def load_files(self, target: Target):
        """
        - [ ] Not yet implemented.
        """
        raise NotImplementedError

    def generate_project(self, target: Target) -> QgsProject:
        """
        - [ ] Not yet implemented.
        """
        return QgsProject()

    def _projecttopping_dict(self, target: Target):
        """
        Gets the layertree as a list of dicts.
        Gets the layerorder as a list.
        Gets the mapthemes as a dict.
        Gets the variables as a dict.
        Gets the layouts as a dict.
        And it generates and stores the toppingfiles according th the Target.
        """
        projecttopping_dict = {}
        projecttopping_dict["layertree"] = self.layertree.items_list(target)
        projecttopping_dict["mapthemes"] = dict(self.mapthemes)
        projecttopping_dict["variables"] = dict(self.variables)
        projecttopping_dict["layouts"] = self.layouts.item_dict(target)
        projecttopping_dict["layerorder"] = self.layerorder
        return projecttopping_dict
