# coding=utf-8

__author__ = "Gareth Coles"

import logging
import inspect

from twisted.internet import reactor

from system.command_manager import CommandManager
from system.constants import *
from system.decorators import Singleton
from system.event_manager import EventManager
from system.factory import Factory
from system.plugin_manager import YamlPluginManagerSingleton
from utils.config import Config
from utils.log import getLogger
from utils.misc import output_exception


@Singleton
class Manager(object):
    """
    Manager for keeping track of multiple factories - one per protocol.

    This is so that the bot can connect to multiple services at once, and have
    them communicate with each other.

    It is currently not planned to have multiple instances of a single factory.
    """

    factories = {}
    configs = {}

    main_config = None

    all_plugins = {}
    loaded_plugins = {}
    plugins_with_dependencies = {}

    def __init__(self):
        # Set up the logger
        self.logger = getLogger("Manager")
        self.main_config = Config("settings.yml")

        self.commands = CommandManager.instance()
        self.commands.set_factory_manager(self)

        self.event_manager = EventManager.instance()

        self.plugman = YamlPluginManagerSingleton.instance()
        self.plugman.setPluginPlaces(["plugins"])
        self.plugman.setPluginInfoExtension("plug")

        self.load_config()  # Load the configuration
        self.collect_plugins()  # Collect the plugins
        self.load_plugins()  # Load the configured plugins
        self.load_protocols()  # Load and set up the protocols

        if not len(self.factories):
            self.logger.info("It seems like no protocols are active. Shutting "
                             "down..")
            return

        reactor.run()

    @staticmethod
    def instance(self=None):
        """
        This only exists to help developers using decent IDEs.
        Don't actually use it.
        """
        if self is None:
            self = Manager
        return self

    # Load stuff

    def load_config(self):
        try:
            self.logger.info("Loading global configuration..")
            if not self.main_config.exists:
                self.logger.error(
                    "Main configuration not found! Please correct this and try"
                    " again.")
                return False
        except IOError:
            self.logger.error(
                "Unable to load main configuration at config/settings.yml")
            self.logger.error("Please check that this file exists.")
            return False
        except Exception:
            self.logger.error(
                "Unable to load main configuration at config/settings.yml")
            output_exception(self.logger, logging.ERROR)
            return False
        return True

    def load_plugins(self):
        self.logger.info("Loading plugins..")

        self.logger.debug("Configured plugins: %s"
                          % ", ".join(self.main_config["plugins"]))

        self.logger.debug("Collecting plugins..")

        if self.main_config["plugins"]:
            todo = []
            for info in self.plugman.getAllPlugins():
                name = info.name
                if info.dependencies:
                    self.plugins_with_dependencies[name] = info
                else:
                    todo.append(info)

            self.logger.debug("Loading plugins that have no dependencies "
                              "first.")

            for info in todo:
                name = info.name
                self.logger.debug("Checking if plugin '%s' is configured to "
                                  "load.." % name)
                if name in self.main_config["plugins"]:
                    self.logger.info("Attempting to load plugin: %s" % name)
                    result = self.load_plugin(name)
                    if not result is PLUGIN_LOADED:
                        if result is PLUGIN_LOAD_ERROR:
                            self.logger.warn("Error detected while loading "
                                             "plugin.")
                        elif result is PLUGIN_ALREADY_LOADED:
                            self.logger.warn("Plugin already loaded.")
                        elif result is PLUGIN_NOT_EXISTS:
                            self.logger.warn("Plugin doesn't exist.")
                        elif result is PLUGIN_DEPENDENCY_MISSING:
                            # THIS SHOULD NEVER HAPPEN!
                            self.logger.warn("Plugin dependency is missing.")

            self.logger.debug("Loading plugins that have dependencies.")

            for name, info in self.plugins_with_dependencies.items():
                self.logger.debug("Checking if plugin '%s' is configured to "
                                  "load.." % name)
                if name in self.main_config["plugins"]:
                    self.logger.info("Attempting to load plugin: %s" % name)
                    try:
                        result = self.load_plugin(name)
                    except RuntimeError as e:
                        message = e.message
                        if message == "maximum recursion depth exceeded " \
                                      "while calling a Python object":
                            self.logger.error("Dependency loop detected while "
                                              "loading: %s" % name)
                            self.logger.error("This plugin will not be "
                                              "available.")
                        elif message == "maximum recursion depth exceeded":
                            self.logger.error("Dependency loop detected while "
                                              "loading: %s" % name)
                            self.logger.error("This plugin will not be "
                                              "available.")
                        else:
                            raise e
                    except Exception as e:
                        raise e
                    if not result is PLUGIN_LOADED:
                        if result is PLUGIN_LOAD_ERROR:
                            self.logger.warn("Error detected while loading "
                                             "plugin.")
                        elif result is PLUGIN_ALREADY_LOADED:
                            self.logger.warn("Plugin already loaded.")
                        elif result is PLUGIN_NOT_EXISTS:
                            self.logger.warn("Plugin doesn't exist.")
                        elif result is PLUGIN_DEPENDENCY_MISSING:
                            self.logger.warn("Plugin dependency is missing.")
        else:
            self.logger.info("No plugins are configured to load.")

    def load_plugin(self, name, unload=False):
        if name in self.all_plugins:
            if name in self.loaded_plugins:
                if unload:
                    self.unload_plugin(name)
                else:
                    return PLUGIN_ALREADY_LOADED

            info = self.plugman.getPluginByName(name)
            if info.dependencies:
                depends = info.dependencies
                self.logger.debug("Dependencies for %s: %s" % (name, depends))
                for d_name in depends:
                    if d_name not in self.all_plugins:
                        self.logger.error("Error loading plugin %s: the plugin"
                                          " relies on another plugin (%s), but"
                                          " it is not present."
                                          % (name, d_name))
                        return PLUGIN_DEPENDENCY_MISSING
                for d_name in depends:
                    result = self.load_plugin(d_name)
                    if not result is PLUGIN_LOADED:
                        if result is PLUGIN_ALREADY_LOADED:
                            continue

                        self.logger.warn("Unable to load dependency: %s"
                                         % d_name)
                        return result

            try:
                self.plugman.activatePluginByName(info.name)
                self.logger.debug("Loading plugin: %s"
                                  % info.plugin_object)
                self.logger.debug("Location: %s" % inspect.getfile
                                  (info.plugin_object.__class__))
                info.plugin_object.add_variables(info, self)
                info.plugin_object.logger = getLogger(name)
                self.logger.debug("Running setup method..")
                info.plugin_object.setup()
            except Exception:
                self.logger.exception("Unable to load plugin: %s v%s"
                                      % (name, info.version))
                self.plugman.deactivatePluginByName(name)
                return PLUGIN_LOAD_ERROR
            else:
                self.loaded_plugins[name] = info
                self.logger.info("Loaded plugin: %s v%s"
                                 % (name, info.version))
                if info.copyright:
                    self.logger.info("Licensing: %s" % info.copyright)
                return PLUGIN_LOADED
        return PLUGIN_NOT_EXISTS

    def collect_plugins(self):
        self.all_plugins = {}
        self.plugman.collectPlugins()
        for info in self.plugman.getAllPlugins():
            self.all_plugins[info.name] = info

    def load_protocols(self):
        self.logger.info("Setting up protocols..")

        for protocol in self.main_config["protocols"]:
            self.logger.info("Setting up protocol: %s" % protocol)
            conf_location = "protocols/%s.yml" % protocol
            result = self.load_protocol(protocol, conf_location)

            if not result is PROTOCOL_LOADED:
                if result is PROTOCOL_ALREADY_LOADED:
                    self.logger.warn("Protocol is already loaded.")
                elif result is PROTOCOL_CONFIG_NOT_EXISTS:
                    self.logger.warn("Unable to find protocol configuration.")
                elif result is PROTOCOL_LOAD_ERROR:
                    self.logger.warn("Error detected while loading "
                                     "protocol.")
                elif result is PROTOCOL_SETUP_ERROR:
                    self.logger.warn("Error detected while setting up "
                                     "protocol.")

    def load_protocol(self, name, conf_location):
        if name in self.factories:
            return PROTOCOL_ALREADY_LOADED

        config = conf_location
        if not isinstance(conf_location, Config):
            # TODO: Prevent upward directory traversal properly
            conf_location = conf_location.replace("..", "")
            try:
                config = Config(conf_location)
                if not config.exists:
                    return PROTOCOL_CONFIG_NOT_EXISTS
            except Exception:
                self.logger.error(
                    "Unable to load configuration for the '%s' protocol."
                    % name)
                output_exception(self.logger, logging.ERROR)
                return PROTOCOL_LOAD_ERROR
        try:
            self.factories[name] = Factory(name, config, self)
            self.factories[name].setup()
            return PROTOCOL_LOADED
        except Exception:
            if name in self.factories:
                del self.factories[name]
            self.logger.error(
                "Unable to create factory for the '%s' protocol!"
                % name)
            output_exception(self.logger, logging.ERROR)
            return PROTOCOL_SETUP_ERROR

    # Unload stuff

    def unload_plugin(self, name):
        if name in self.loaded_plugins:
            try:
                self.plugman.deactivatePluginByName(name)
            except Exception:
                self.logger.error("Error disabling plugin: %s" % name)
                output_exception(self.logger, logging.ERROR)
            self.commands.unregister_commands_for_owner(name)
            self.event_manager.remove_callbacks_for_plugin(name)
            del self.loaded_plugins[name]
            return PLUGIN_UNLOADED
        return PLUGIN_NOT_EXISTS

    def unload_protocol(self, name):  # Removes with a shutdown
        if name in self.factories:
            proto = self.factories[name].protocol
            try:
                proto.shutdown()
            except Exception:
                self.logger.error("Error shutting down protocol %s")
                output_exception(self.logger, logging.ERROR)
            del self.factories[name]
            return True
        return False

    def unload(self):
        # Shut down!
        for name in self.factories.keys():
            self.unload_protocol(name)
        for name in self.loaded_plugins.keys():
            self.unload_plugin(name)

    # Grab stuff

    def get_protocol(self, name):
        if name in self.factories:
            return self.factories[name].protocol
        return None

    def get_factory(self, name):
        if name in self.factories:
            return self.factories[name]
        return None

    def remove_protocol(self, protocol):  # Removes without shutdown
        if protocol in self.factories:
            del self.factories[protocol]
            return True
        return False
