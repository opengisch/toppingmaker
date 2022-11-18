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

import os
from typing import Union

import yaml
from qgis.core import (
    Qgis,
    QgsDataSourceUri,
    QgsLayerDefinition,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsMapLayer,
    QgsProject,
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

    class TreeItemProperties(object):
        """
        The properties of a node (tree item)
        """

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

    class LayerTreeItem(object):
        """
        A tree item of the layer tree. Every item contains the properties of a layer and according the ExportSettings passed on parsing the QGIS project.
        """

        def __init__(self):
            self.items = []
            self.name = None
            self.properties = ProjectTopping.TreeItemProperties()
            self.temporary_toppingfile_dir = os.path.expanduser("~/.temp_topping_files")

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
                        item = ProjectTopping.LayerTreeItem()
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

                qml_setting = export_settings.get_setting(
                    ExportSettings.ToppingType.QMLSTYLE, node, node.name()
                )
                if qml_setting.get("export", False):
                    self.properties.qmlstylefile = self._temporary_qmlstylefile(
                        layer,
                        QgsMapLayer.StyleCategory(
                            qml_setting.get(
                                "categories",
                                QgsMapLayer.StyleCategory.AllStyleCategories,
                            )
                        ),
                    )

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
            QgsLayerDefinition.exportLayerDefinition(temporary_toppingfile_path, [node])
            return temporary_toppingfile_path

        def _temporary_qmlstylefile(
            self,
            layer: QgsMapLayer,
            categories: QgsMapLayer.StyleCategories = QgsMapLayer.StyleCategory.AllStyleCategories,
        ):
            filename_slug = f"{slugify(self.name)}.qml"
            os.makedirs(self.temporary_toppingfile_dir, exist_ok=True)
            temporary_toppingfile_path = os.path.join(
                self.temporary_toppingfile_dir, filename_slug
            )
            layer.saveNamedStyle(temporary_toppingfile_path, categories)
            return temporary_toppingfile_path

    def __init__(self):
        QObject.__init__(self)
        self.layertree = self.LayerTreeItem()
        self.layerorder = []

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
            self.layertree.make_item(project, project.layerTreeRoot(), export_settings)
            self.layerorder = (
                root.customLayerOrder() if root.hasCustomLayerOrder() else []
            )
            self.stdout.emit(
                self.tr("QGIS project parsed with export settings."), Qgis.Info
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
        Creates the layertree as a dict.
        Creates the layerorder as a list.
        And it generates and stores the toppingfiles according th the Target.
        """
        projecttopping_dict = {}
        projecttopping_dict["layertree"] = self._item_dict_list(
            target, self.layertree.items
        )
        projecttopping_dict["layerorder"] = [layer.name() for layer in self.layerorder]
        return projecttopping_dict

    def _item_dict_list(self, target: Target, items):
        item_dict_list = []
        print([item.name for item in items])
        for item in items:
            item_dict = self._create_item_dict(target, item)
            item_dict_list.append(item_dict)
        return item_dict_list

    def _create_item_dict(self, target: Target, item: LayerTreeItem):
        item_dict = {}
        item_properties_dict = {}

        if item.properties.group:
            item_properties_dict["group"] = True
            if item.properties.mutually_exclusive:
                item_properties_dict["mutually-exclusive"] = True
                item_properties_dict[
                    "mutually-exclusive-child"
                ] = item.properties.mutually_exclusive_child
        else:
            if item.properties.tablename:
                item_properties_dict["tablename"] = item.properties.tablename
                if item.properties.geometrycolumn:
                    item_properties_dict[
                        "geometrycolumn"
                    ] = item.properties.geometrycolumn
            if item.properties.featurecount:
                item_properties_dict["featurecount"] = True
            if item.properties.qmlstylefile:
                item_properties_dict["qmlstylefile"] = target.toppingfile_link(
                    ProjectTopping.LAYERSTYLE_TYPE, item.properties.qmlstylefile
                )
            if item.properties.provider and item.properties.uri:
                item_properties_dict["provider"] = item.properties.provider
                item_properties_dict["uri"] = item.properties.uri

        item_properties_dict["checked"] = item.properties.checked
        item_properties_dict["expanded"] = item.properties.expanded

        if item.properties.definitionfile:
            item_properties_dict["definitionfile"] = target.toppingfile_link(
                ProjectTopping.LAYERDEFINITION_TYPE,
                item.properties.definitionfile,
            )

        if item.items:
            child_item_dict_list = self._item_dict_list(target, item.items)
            item_properties_dict["child-nodes"] = child_item_dict_list

        item_dict[item.name] = item_properties_dict
        return item_dict
