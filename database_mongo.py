import os
import time
from pymongo import MongoClient, errors
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

class MongoDatabase:
    def __init__(self, uri=MONGO_URI, db_name=DB_NAME):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.is_connected = False
        self._connect()

    def _connect(self):
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=2000)
            # Ping database to confirm connection
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.is_connected = True
            print(f"[MONGODB SUCCESS]: Connected to MongoDB at {self.uri} (Database: '{self.db_name}')")
            self._ensure_indexes()
        except Exception as e:
            self.is_connected = False
            print(f"[MONGODB NOTICE]: Could not connect to MongoDB at {self.uri}: {e}. (Will use SQLite fallback)")

    def _ensure_indexes(self):
        if not self.is_connected:
            return
        try:
            self.db.users.create_index("email", unique=True)
            self.db.settings.create_index("user_email", unique=True)
            self.db.otp_codes.create_index("email")
            self.db.email_history.create_index("user_email")
        except Exception as e:
            print(f"[MONGODB INDEX ERROR]: {e}")

    def get_status(self):
        if not self.is_connected:
            self._connect()
        return {
            "connected": self.is_connected,
            "uri": self.uri,
            "database": self.db_name,
            "collections": self.db.list_collection_names() if self.is_connected else []
        }

    # --- User & Login History Operations (Username, Email & Login Time) ---
    def save_user(self, email, name=None):
        if not self.is_connected:
            return None
        try:
            username = name or email.split('@')[0].capitalize()
            now_ts = int(time.time())
            now_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now_ts))
            user_doc = self.db.users.find_one_and_update(
                {"email": email},
                {"$set": {"email": email, "username": username, "updated_at": now_str}, "$setOnInsert": {"created_at": now_str}},
                upsert=True,
                return_document=True
            )
            return user_doc
        except Exception as e:
            print(f"[MONGODB USER SAVE ERROR]: {e}")
            return None

    def log_user_login(self, email, name=None):
        """Record login event with username, email, and login time into MongoDB."""
        if not self.is_connected:
            return None
        try:
            username = name or email.split('@')[0].capitalize()
            now_ts = int(time.time())
            login_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now_ts))

            # 1. Update user profile document in 'users' collection
            self.db.users.update_one(
                {"email": email},
                {"$set": {
                    "username": username,
                    "email": email,
                    "last_login_time": login_time_str,
                    "last_login_timestamp": now_ts
                }},
                upsert=True
            )

            # 2. Insert login record event into 'login_history' collection
            log_doc = {
                "username": username,
                "email": email,
                "login_time": login_time_str,
                "timestamp": now_ts
            }
            res = self.db.login_history.insert_one(log_doc)
            print(f"[MONGODB LOGIN LOGGED]: User '{username}' ({email}) logged in at {login_time_str}")
            return str(res.inserted_id)
        except Exception as e:
            print(f"[MONGODB LOGIN LOG ERROR]: {e}")
            return None

    def get_login_history(self, limit=50):
        if not self.is_connected:
            return []
        try:
            cursor = self.db.login_history.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            return list(cursor)
        except Exception as e:
            print(f"[MONGODB GET LOGIN HISTORY ERROR]: {e}")
            return []

    def get_user(self, email):
        if not self.is_connected:
            return None
        return self.db.users.find_one({"email": email})

    # --- Settings Operations ---
    def save_settings(self, user_email, settings_dict):
        if not self.is_connected:
            return None
        try:
            settings_dict["user_email"] = user_email
            settings_dict["updated_at"] = int(time.time())
            res = self.db.settings.update_one(
                {"user_email": user_email},
                {"$set": settings_dict},
                upsert=True
            )
            return res.acknowledged
        except Exception as e:
            print(f"[MONGODB SETTINGS SAVE ERROR]: {e}")
            return False

    def get_settings(self, user_email):
        if not self.is_connected:
            return None
        return self.db.settings.find_one({"user_email": user_email})

    # --- OTP Operations ---
    def save_otp(self, email, code, expires_at):
        if not self.is_connected:
            return None
        try:
            self.db.otp_codes.update_many({"email": email}, {"$set": {"used": True}})
            res = self.db.otp_codes.insert_one({
                "email": email,
                "code": code,
                "expires_at": expires_at,
                "used": False,
                "created_at": int(time.time())
            })
            return str(res.inserted_id)
        except Exception as e:
            print(f"[MONGODB OTP SAVE ERROR]: {e}")
            return None

    def verify_otp(self, email, code):
        if not self.is_connected:
            return False
        try:
            now = int(time.time())
            doc = self.db.otp_codes.find_one({
                "email": email,
                "code": code,
                "used": False,
                "expires_at": {"$gte": now}
            })
            if doc:
                self.db.otp_codes.update_one({"_id": doc["_id"]}, {"$set": {"used": True}})
                return True
            return False
        except Exception as e:
            print(f"[MONGODB OTP VERIFY ERROR]: {e}")
            return False

    # --- Saved Emails Operations ---
    def save_saved_email(self, user_email, subject, body, tone="Formal", category="General"):
        if not self.is_connected:
            return None
        try:
            doc = {
                "user_email": user_email,
                "subject": subject,
                "body": body,
                "tone": tone,
                "category": category,
                "created_at": int(time.time()),
                "created_time": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            res = self.db.saved_emails.insert_one(doc)
            doc["_id"] = str(res.inserted_id)
            print(f"[MONGODB SAVED EMAIL]: Saved '{subject}' for {user_email}")
            return doc
        except Exception as e:
            print(f"[MONGODB SAVE EMAIL ERROR]: {e}")
            return None

    def get_saved_emails(self, user_email):
        if not self.is_connected:
            return []
        try:
            cursor = self.db.saved_emails.find({"user_email": user_email}).sort("created_at", -1)
            results = []
            for item in cursor:
                item["id"] = str(item["_id"])
                item["_id"] = str(item["_id"])
                results.append(item)
            return results
        except Exception as e:
            print(f"[MONGODB GET SAVED EMAILS ERROR]: {e}")
            return []

    def delete_saved_email(self, email_id, user_email):
        if not self.is_connected:
            return False
        try:
            from bson.objectid import ObjectId
            try:
                res = self.db.saved_emails.delete_one({"_id": ObjectId(email_id), "user_email": user_email})
                return res.deleted_count > 0
            except Exception:
                res = self.db.saved_emails.delete_one({"user_email": user_email})
                return res.deleted_count > 0
        except Exception as e:
            print(f"[MONGODB DELETE SAVED EMAIL ERROR]: {e}")
            return False

    # --- Chat History & Email History Operations ---
    def save_chat_history(self, user_email, prompt, subject, body, model="llama3", tone="Formal", length="Medium", rag_used=False, ocr_used=False):
        if not self.is_connected:
            return None
        try:
            now_ts = int(time.time())
            now_str = time.strftime('%Y-%m-%d %H:%M:%S')
            doc = {
                "user_email": user_email,
                "prompt": prompt,
                "subject": subject,
                "body": body,
                "model": model,
                "tone": tone,
                "length": length,
                "rag_used": bool(rag_used),
                "ocr_used": bool(ocr_used),
                "created_at": now_ts,
                "created_time": now_str
            }
            res_chat = self.db.chat_history.insert_one(doc.copy())
            res_hist = self.db.email_history.insert_one(doc.copy())
            print(f"[MONGODB CHAT & EMAIL HISTORY]: Saved prompt '{prompt[:30]}...' for {user_email}")
            return str(res_chat.inserted_id)
        except Exception as e:
            print(f"[MONGODB SAVE CHAT HISTORY ERROR]: {e}")
            return None

    def get_chat_history(self, user_email):
        if not self.is_connected:
            return []
        try:
            cursor = self.db.chat_history.find({"user_email": user_email}).sort("created_at", -1)
            results = []
            for item in cursor:
                item["id"] = str(item["_id"])
                item["_id"] = str(item["_id"])
                results.append(item)
            return results
        except Exception as e:
            print(f"[MONGODB GET CHAT HISTORY ERROR]: {e}")
            return []

    def clear_chat_history(self, user_email):
        if not self.is_connected:
            return False
        try:
            res = self.db.chat_history.delete_many({"user_email": user_email})
            return res.deleted_count > 0
        except Exception as e:
            print(f"[MONGODB CLEAR CHAT HISTORY ERROR]: {e}")
            return False

# Global MongoDB instance
mongo_db = MongoDatabase()
