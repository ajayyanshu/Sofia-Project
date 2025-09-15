from flask_bcrypt import Bcrypt
from bson import ObjectId

# Initialize Bcrypt here or pass it from the app
bcrypt = Bcrypt()

class Database:
    """
    This class handles all database operations for the application.
    It centralizes the logic for interacting with MongoDB collections.
    """
    def __init__(self, mongo):
        """
        Initializes the Database class with the Flask-PyMongo instance.
        
        :param mongo: The initialized PyMongo instance from the Flask app.
        """
        self.mongo = mongo

    # --- User Collection Methods ---

    def find_user_by_username(self, username):
        """Finds a single user by their username."""
        return self.mongo.db.users.find_one({"username": username})

    def create_user(self, username, password):
        """Hashes a password and creates a new user in the database."""
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        return self.mongo.db.users.insert_one({
            'username': username,
            'password': hashed_password
        })

    def check_user_password(self, user_password_hash, password):
        """Checks if the provided password matches the stored hash."""
        return bcrypt.check_password_hash(user_password_hash, password)

    # --- Chat Collection Methods ---

    def get_user_chat_history(self, user_id):
        """Retrieves the full chat history for a given user ID."""
        return self.mongo.db.chats.find_one({'user_id': ObjectId(user_id)})

    def save_chat_messages(self, user_id, user_message, ai_message):
        """
        Saves a pair of user and AI messages to the user's chat history.
        Uses 'upsert=True' to create a chat document if one doesn't exist.
        """
        self.mongo.db.chats.update_one(
            {'user_id': ObjectId(user_id)},
            {'$push': {'messages': {'$each': [user_message, ai_message]}}},
            upsert=True
        )

    def delete_chat_history(self, user_id):
        """
        Deletes the entire chat history document for a given user.
        This is a new function to provide more control over the chat history feature.
        """
        return self.mongo.db.chats.delete_one({'user_id': ObjectId(user_id)})

