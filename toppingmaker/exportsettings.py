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
from enum import Enum
from typing import Union

from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer


class ExportSettings(object):
    """
    # Layertree:

    The requested export settings of each node in the specific dicts:
    - qmlstyle_setting_nodes
    - definition_setting_nodes
    - source_setting_nodes

    The usual structure is using QgsLayerTreeNode as key and then export True/False
    {
        <QgsLayerTreeNode(Node1)>: { export: False },
        <QgsLayerTreeNode(Node2)>: { export: True, export: True }
    }

    But alternatively the layername can be used as key. In ProjectTopping it first looks up the node and if not available looking up the name.
    Using the node is much more consistent, since one can use layers with the same name, but for nodes you need the project already in advance.
    With name you can use prepared settings to pass (before the project exists) e.g. in automated workflows.
    {
        "Node1": { export: False },
        "Node2": { export: True },
    }

    For some settings we have additional info. Like in qmlstyle_nodes <QgsMapLayer.StyleCategories>. These are Flags, and can be constructed manually as well.
    qmlstyle_nodes =
    {
        <QgsLayerTreeNode(Node1)>: { export: False }
        <QgsLayerTreeNode(Node2)>: { export: True, categories: <QgsMapLayer.StyleCategories> }
    }

    If styles are used as well we create tuples as key. Mutable objects are not alowed in it, so they would be created with the (layer) name and the style (name):
    {
        <QgsLayerTreeNode(Node1)>: { export: False }
        <QgsLayerTreeNode(Node2)>: { export: True, categories: <QgsMapLayer.StyleCategories> }
        ("Node2","french"): { export: True, categories: <QgsMapLayer.StyleCategories> },
        ("Node2","robot"): { export: True, categories: <QgsMapLayer.StyleCategories> }
    }

    # Mapthemes:

    The map themes to export are a simple list of map theme names stored in `mapthemes`.

    # Custom Project Variables:

    The custom variables to export are a simple list of the keys stored in `custom_variables`.

    # Layouts:

    The print layouts to export are a simple list of layout names stored in `layouts`.

    """

    class ToppingType(Enum):
        QMLSTYLE = 1
        DEFINITION = 2
        SOURCE = 3

    def __init__(self):
        # layertree settings per layer / group and type of export
        self.qmlstyle_setting_nodes = {}
        self.definition_setting_nodes = {}
        self.source_setting_nodes = {}
        # names of mapthemes to be exported
        self.mapthemes = []
        # keys of custom variables to be exported
        self.custom_variables = []
        # names of layouts
        self.layouts = []

    def set_setting_values(
        self,
        type: ToppingType,
        node: Union[QgsLayerTreeLayer, QgsLayerTreeGroup] = None,
        name: str = None,
        export=True,
        categories=None,
        style_name: str = None,
    ) -> bool:
        """
        Appends the values (export, categories) to an existing setting
        """
        setting_nodes = self._setting_nodes(type)
        setting = self._get_setting(setting_nodes, node, name, style_name)
        setting["export"] = export
        if categories:
            setting["categories"] = categories
        return self._set_setting(setting_nodes, setting, node, name, style_name)

    def get_setting(
        self,
        type: ToppingType,
        node: Union[QgsLayerTreeLayer, QgsLayerTreeGroup] = None,
        name: str = None,
        style_name: str = None,
    ) -> dict():
        """
        Returns an existing or an empty setting dict
        """
        setting_nodes = self._setting_nodes(type)
        return self._get_setting(setting_nodes, node, name, style_name)

    def _setting_nodes(self, type: ToppingType):
        if type == ExportSettings.ToppingType.QMLSTYLE:
            return self.qmlstyle_setting_nodes
        if type == ExportSettings.ToppingType.DEFINITION:
            return self.definition_setting_nodes
        if type == ExportSettings.ToppingType.SOURCE:
            return self.source_setting_nodes

    def _get_setting(self, setting_nodes, node=None, name=None, style_name=None):
        # check for a setting according to the node if available and if no setting found, do it with the name.
        key = self._node_key(node, style_name)
        setting = setting_nodes.get(key, {})
        if not setting:
            key = self._name_key(name, style_name)
            setting = setting_nodes.get(key, {})
        return setting

    def _set_setting(
        self, setting_nodes, setting, node=None, name=None, style_name=None
    ) -> bool:
        # get a key according to the node if available otherwise do it with the name.
        key = self._node_key(node, style_name) or self._name_key(name, style_name)
        if key:
            setting_nodes[key] = setting
            return True
        return False

    def _node_key(self, node=None, style_name=None):
        # creates a key according to the available node.
        if node:
            if style_name:
                return (node.name(), style_name)
            else:
                return node
        return None

    def _name_key(self, name=None, style_name=None):
        # creates a key according to the available name.
        if name:
            if style_name:
                return (name, style_name)
            else:
                return name
        return None
