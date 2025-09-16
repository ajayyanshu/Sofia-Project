import datetime
from bson.objectid import ObjectId

class Database:
    """
    Handles all interactions with the MongoDB database.
    This class separates the database logic from the web server logic in app.py.
    """
    def __init__(self, mongo):
        """
        Initializes the Database class with a connection to MongoDB.

        Args:
            mongo: The Flask-PyMongo instance from the main app.
        """
        self.mongo = mongo
        # Define collections for easier access
        self.users = self.mongo.db.users
        self.chats = self.mongo.db.chats

    def create_user(self, username, hashed_password):
        """
        Inserts a new user into the users collection.

        Args:
            username (str): The username for the new account.
            hashed_password (str): The encrypted password.

        Returns:
            ObjectId: The ID of the newly inserted user, or None on failure.
        """
        try:
            return self.users.insert_one({
                'username': username,
                'password': hashed_password,
                'created_at': datetime.datetime.utcnow()
            }).inserted_id
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    def find_user_by_username(self, username):
        """
        Finds a single user by their username.

        Args:
            username (str): The username to search for.

        Returns:
            dict: The user document if found, otherwise None.
        """
        return self.users.find_one({'username': username})

    def save_chat_message(self, user_id, message_document):
        """
        Saves a new chat message or updates the chat history for a user.
        A chat document is created if one doesn't exist for the user.

        Args:
            user_id (str): The ObjectId of the user as a string.
            message_document (dict): The message to save (e.g., {"role": "user", "parts": [...]})
        """
        # Find the user's chat document or create a new one
        self.chats.update_one(
            {'user_id': ObjectId(user_id)},
            {
                '$push': {'history': message_document},
                '$setOnInsert': {
                    'user_id': ObjectId(user_id),
                    'created_at': datetime.datetime.utcnow()
                },
                '$set': {'last_updated': datetime.datetime.utcnow()}
            },
            upsert=True  # This creates the document if it doesn't exist
        )

    def get_user_chat_history(self, user_id):
        """
        Retrieves the entire chat history for a specific user.

        Args:
            user_id (str): The ObjectId of the user as a string.

        Returns:
            list: A list of chat message documents, or an empty list if not found.
        """
        chat_document = self.chats.find_one({'user_id': ObjectId(user_id)})
        if chat_document and 'history' in chat_document:
            return chat_document['history']
        return []

