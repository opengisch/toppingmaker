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
    """

    class ToppingType(Enum):
        QMLSTYLE = 1
        DEFINITION = 2
        SOURCE = 3

    def __init__(self):
        # layertree settings
        self.qmlstyle_setting_nodes = {}
        self.definition_setting_nodes = {}
        self.source_setting_nodes = {}
        # maptheme settings
        self.mapthemes = []

    def set_setting_values(
        self,
        type: ToppingType,
        node: Union[QgsLayerTreeLayer, QgsLayerTreeGroup] = None,
        name: str = None,
        export=True,
        categories=None,
        style: str = None,
    ) -> bool:
        """
        Appends the values (export, categories) to an existing setting
        """
        setting_nodes = self._setting_nodes(type)
        setting = self._get_setting(setting_nodes, node, name, style)
        setting["export"] = export
        if categories:
            setting["categories"] = categories
        return self._set_setting(setting_nodes, setting, node, name, style)

    def get_setting(
        self,
        type: ToppingType,
        node: Union[QgsLayerTreeLayer, QgsLayerTreeGroup] = None,
        name: str = None,
        style: str = None,
    ) -> dict():
        """
        Returns an existing or an empty setting dict
        """
        setting_nodes = self._setting_nodes(type)
        return self._get_setting(setting_nodes, node, name, style)

    def _setting_nodes(self, type: ToppingType):
        if type == ExportSettings.ToppingType.QMLSTYLE:
            return self.qmlstyle_setting_nodes
        if type == ExportSettings.ToppingType.DEFINITION:
            return self.definition_setting_nodes
        if type == ExportSettings.ToppingType.SOURCE:
            return self.source_setting_nodes

    def _get_setting(self, setting_nodes, node=None, name=None, style=None):
        # check for a setting according to the node if available and if no setting found, do it with the name.
        key = self._node_key(node, style)
        setting = setting_nodes.get(key, {})
        if not setting:
            key = self._name_key(name, style)
            setting = setting = setting_nodes.get(key, {})
        return setting

    def _set_setting(
        self, setting_nodes, setting, node=None, name=None, style=None
    ) -> bool:
        # get a key according to the node if available otherwise do it with the name.
        key = self._node_key(node, style) or self._name_key(name, style)
        if key:
            setting_nodes[key] = setting
            return True
        return False

    def _node_key(self, node=None, style=None):
        # creates a key according to the available node.
        if node:
            if style:
                return (node.name(), style)
            else:
                return node
        return None

    def _name_key(self, name=None, style=None):
        # creates a key according to the available name.
        if name:
            if style:
                return (name, style)
            else:
                return name
        return None
