
# A simple in-memory 'database' to store user info
users_db = {}

class User:
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
