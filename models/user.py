
# A simple in-memory 'database' to store user info
users_db = {}

class User:
    """
    Represents a user with attributes and methods to interact with user data.

    Attributes:
        id_ (str): The unique identifier for the user.
        name (str): The name of the user.
        email (str): The email address of the user.
        profile_pic (str): The URL of the user's profile picture.

    Methods:
        get(user_id):
            Retrieves a User instance based on the given user ID.
            Args:
                user_id (str): The unique identifier of the user to retrieve.
            Returns:
                User: An instance of the User class if the user exists, otherwise None.

        create(id_, name, email, profile_pic):
            Creates a new user and stores their information in the database.
            Args:
                id_ (str): The unique identifier for the new user.
                name (str): The name of the new user.
                email (str): The email address of the new user.
                profile_pic (str): The URL of the new user's profile picture.
    """
    def __init__(self, id_, name, email, profile_pic):
        self.id_ = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic

    @staticmethod
    def get(user_id):
        if user_id in users_db:
            user_info = users_db[user_id]
            return User(id_=user_id, **user_info)
        return None

    @staticmethod
    def create(id_, name, email, profile_pic):
        users_db[id_] = {"name": name, "email": email, "profile_pic": profile_pic}
