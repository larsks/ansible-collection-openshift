from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

import openshift_client as oc

DOCUMENTATION = r"""
name: ocnodes
plugin_type: inventory
short_description: Inventory of openshift nodes
options:
    plugin:
        description: Name of the plugin
        required: true
        choices: ['oddbit.openshift.ocnodes']
    group:
        description: Add nodes to named group
        required: false
        default: 'openshift_nodes'
    group_vars:
        description: Arbitrary group variables
        required: false
"""


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "ocnodes"

    def __init__(self):
        super(InventoryModule, self).__init__()

    def verify_file(self, path: str):
        if super(InventoryModule, self).verify_file(path):
            return path.endswith("openshift.yaml")
        return False

    def parse(self, inventory, loader, path, cache: bool = True):
        super(InventoryModule, self).parse(inventory, loader, path, cache)
        self._read_config_data(path)  # This also loads the cache

        self.plugin = self.get_option("plugin")
        if self.plugin != "oddbit.openshift.ocnodes":
            raise AnsibleParserError("invalid plugin configuration")

        group_name = (
            self.get_option("group") if self.has_option("group") else "openshift_nodes"
        )
        self.inventory.add_group(group_name)
        group = self.inventory.groups[group_name]

        if self.has_option("group_vars"):
            for name, value in self.get_option("group_vars").items():
                self.inventory.set_variable(group_name, name, value)

        nodes = {
            node.model.metadata.name: node.model.status.addresses[0].address
            for node in oc.selector("nodes").objects()
        }
        for name, address in nodes.items():
            self.inventory.add_host(name)
            self.inventory.set_variable(name, "ansible_host", address)
            group.add_host(self.inventory.hosts[name])

            node = oc.selector(f"nodes/{name}").object()

            roles = [
                label.split("/")[1]
                for label in node.model.metadata.labels
                if label.startswith("node-role.kubernetes.io")
            ]

            self.inventory.set_variable(
                name,
                "node_roles",
                roles,
            )
            self.inventory.set_variable(
                name,
                "node_labels",
                node.model.metadata.labels,
            )
            self.inventory.set_variable(
                name,
                "node_annotations",
                node.model.metadata.annotations,
            )
            self.inventory.set_variable(
                name,
                "node_info",
                node.model.status.nodeInfo,
            )
            self.inventory.set_variable(
                name,
                "node_addresses",
                node.model.status.addresses,
            )
            self.inventory.set_variable(
                name,
                "node_ready",
                next(
                    (
                        condition["status"] == "True"
                        for condition in node.model.status.conditions
                        if condition["type"] == "Ready"
                    ),
                    False,
                ),
            )
