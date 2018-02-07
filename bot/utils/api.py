#!/bin/env python

"""API related functions"""

from .mongodoc import MongoDocument

class ApiKey(MongoDocument):
    """Class for API Key document"""

    _DATABASE = "discord_against_humanity"
    _COLLECTION = "api_keys"

    def __init__(self, mongo_client, name):
        """Creates a new ApiKey object

        Arguments:
            mongo_client {MongoClient} -- Mongo Client connected to the database
            mongo_session {ClientSession} -- Mongo Client Session

        Keyword Arguments:
            name {str} -- Name of the API Key (default: {None})
        """
        super(ApiKey, self).__init__(mongo_client)
        self._name = name
        self._get(name)

    @property
    def value(self):
        """Returns the value of the API Key"""
        try:
            return self._document[self._name]
        except KeyError:
            return None

    def _get(self, name):
        """Get the document containing the API Key

        Arguments:
            name {str} -- Name of the API Key
        """
        self._document = self._collection.find_one({name: {"$exists": True}})
