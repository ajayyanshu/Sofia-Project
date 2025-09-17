import os
import traceback
import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

# Load environment variables for local development
load_dotenv()

def init_db():
    """
    Initializes and returns a connection to the MongoDB database.
    Returns the database object on success, or None on failure.
    """
    db = None
    mongo_uri = os.environ.get("MONGO_URI")

    if not mongo_uri:
        print("⚠️ WARNING: MONGO_URI environment variable not found. Database features will be disabled.")
        return None
    
    try:
        print("Attempting to connect to MongoDB...")
        client = MongoClient(mongo_uri)
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        
        # Connect to the specific database
        db = client['collegeproject']
        
        print(f"✅ MongoDB connection successful. Connected to database: '{db.name}'")

        # Ensure the chat_history collection exists
        if 'chat_history' not in db.list_collection_names():
            db.create_collection('chat_history')
            print("Created 'chat_history' collection.")
            
        return db

    except ConnectionFailure as e:
        print(f"❌ CRITICAL ERROR: Could not connect to MongoDB. Check your MONGO_URI and network settings.")
        print(f"   Detailed Error: {e}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred during MongoDB setup: {e}")
        traceback.print_exc()
        return None

def save_chat_history(db, user_msg, ai_msg):
    """
    Saves a chat record to the 'chat_history' collection in MongoDB.
    """
    if not db:
        print("⚠️ Database connection is not available. Cannot save chat history.")
        return

    print("Attempting to save chat history to MongoDB...")
    try:
        chat_history_collection = db.chat_history
        chat_record = {
            'user_message': user_msg,
            'ai_response': ai_msg,
            'timestamp': datetime.datetime.utcnow()
        }
        result = chat_history_collection.insert_one(chat_record)
        
        if result.inserted_id:
            print(f"📝 Chat history saved successfully with ID: {result.inserted_id}")
        else:
            print("⚠️ Chat history insert operation failed or was not acknowledged.")
            
    except Exception as e:
        print(f"⚠️ Could not save chat history to MongoDB. Error: {e}")
        traceback.print_exc()
