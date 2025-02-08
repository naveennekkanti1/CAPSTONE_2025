from pymongo import MongoClient

uri = "mongodb+srv://naveennekkanti:naveennekkanti@cluster0.2zvzf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)
print(client.server_info())  # Check connection
