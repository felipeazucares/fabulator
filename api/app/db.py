from pymongo import MongoClient
client = MongoClient("mongodb://localhost:27017/")


def db_connect():
    print("here")
