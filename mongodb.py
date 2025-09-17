import os
import sys
import traceback
import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

# --- NEW: Diagnostic check for common import issue ---
# This checks if a file named 'pymongo.py' exists in the project, which would cause conflicts.
try:
    if 'pymongo.py' in os.listdir(os.path.dirname(__file__)):
        print("\n" + "="*60)
        print("CRITICAL ERROR: A file named 'pymongo.py' was found in your project directory.")
        print("This conflicts with the official pymongo library. Please rename your local file.")
        print("="*60 + "\n")
        sys.exit(1) # Stop the application immediately
except FileNotFoundError:
    pass # This can happen in some environments, it's safe to ignore.

print("--- Module 'mongodb.py' loaded ---")

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
        client.admin.command('ismaster')
        db = client['collegeproject']
        print(f"✅ MongoDB connection successful. Connected to database: '{db.name}'")

        if 'chat_history' not in db.list_collection_names():
            db.create_collection('chat_history')
            print("Created 'chat_history' collection.")
        return db

    except ConnectionFailure as e:
        print("\n" + "="*60)
        print("❌ DATABASE CONNECTION FAILED: Could not connect to MongoDB.")
        print("   REASON: The server could not be reached. This is often a network issue.")
        print("   CHECK: 1. Your MONGO_URI in the .env file or Render environment variables.")
        print("          2. Your IP Access List settings in MongoDB Atlas.")
        print(f"   DETAILS: {e}")
        print("="*60 + "\n")
        return None
    except Exception as e:
        # Check for authentication error specifically for a more helpful message
        if "bad auth" in str(e).lower() or "authentication failed" in str(e).lower():
             print("\n" + "="*60)
             print("❌ DATABASE AUTHENTICATION FAILED: The username or password is incorrect.")
             print("   CHECK: 1. The credentials in your MONGO_URI.")
             print("          2. The user exists under 'Database Access' in MongoDB Atlas.")
             print(f"   DETAILS: {e}")
             print("="*60 + "\n")
        else:
             print("\n" + "="*60)
             print(f"❌ An unexpected error occurred during MongoDB setup.")
             print(f"   DETAILS: {e}")
             print("="*60 + "\n")
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
            print("⚠️ Chat history insert operation failed or was not acknowledged by the server.")
            
    except Exception as e:
        print("\n" + "="*60)
        print(f"⚠️ DATABASE SAVE FAILED: Could not save chat history.")
        print("   REASON: An error occurred during the database write operation.")
        print("   CHECK:  1. The database user has 'readWrite' permissions in MongoDB Atlas.")
        print(f"   DETAILS: {e}")
        print("="*60 + "\n")
        traceback.print_exc()

