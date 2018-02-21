#!/usr/bin/env python

from bson.objectid import ObjectId
from pymongo.collection import ReturnDocument


class MongoDocument(object):
    """Class for Document in MongoDB"""

    # Constants
    _DATABASE = None
    _COLLECTION = None

    def __init__(self, mongo_client):
        """Creates a new MongoDocument object

        Arguments:
            mongo_client {MongoClient} -- Mongo Client connected to the database
        """
        self._client = mongo_client
        self._collection = self._client[self._DATABASE][self._COLLECTION]  # Get Mongo Collection
        self._document = dict()  # Mongo Document

    @property
    def document_id(self):
        """Get ID of the Mongo Document

        Returns:
            ObjectId -- ID of Mongo document
        """
        try:
            return self._document["_id"]
        except KeyError:
            return None

    @document_id.setter
    def document_id(self, value):
        """Set ID of the Mongo Document

        Arguments:
            value {ObjectId} -- ID of Mongo document
        """
        if not isinstance(value, ObjectId):
            raise TypeError
        self._document["_id"] = value

    async def get(self, document_id=None):
        """Get the Mongo document"""
        search = {"_id": self.document_id}
        if document_id:
            search = {"_id": document_id}
        self._document = await self._collection.find_one(search)

    async def save(self):
        """Saves Mongo document"""
        if not self.document_id:
            result = await self._collection.insert_one(self._document)
            self.document_id = result.inserted_id
        else:
            self._document = await self._collection.find_one_and_replace(
                {"_id": self.document_id}, self._document)
        self._document = await self._collection.find_one({"_id": self.document_id})

    async def delete(self):
        """Deletes Mongo document"""
        if self.document_id:
            await self._collection.delete_one({"_id": self.document_id})
