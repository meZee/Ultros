# coding=utf-8

"""
An unused module
"""

__author__ = "Gareth Coles"

from system.translations import Translations
_ = Translations().get()


class BaseSupport(object):
    """
    An unused class
    """

    plugin = None
    logger = None
    events = None

    def __init__(self, plugin, logger, event_manager):
        self.plugin = plugin
        self.logger = logger
        self.events = event_manager

    def setup(self):
        raise NotImplementedError(_("Setup method needs to be implemented!"))
