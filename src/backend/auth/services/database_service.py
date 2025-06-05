"""
Database service for user authentication operations.
Provides MongoDB operations using Motor async client for user management.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError, PyMongoError
from bson import ObjectId

from ...config.env import get_settings
from ...config.logging import get_logger
from ...models.user_model import UserModel, UserCreateModel

logger = get_logger(__name__)


class DatabaseService:
    """
    Database service for user authentication operations.
    
    Handles MongoDB connections and user document operations using Motor
    async client for high-performance async operations.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self.users_collection: Optional[AsyncIOMotorCollection] = None
        self._connected = False
    
    async def connect(self) -> None:
        """
        Establish connection to MongoDB.
        
        Raises:
            Exception: If connection fails
        """
        try:
            mongodb_params = self.settings.get_mongodb_connection_params()
            
            self.client = AsyncIOMotorClient(
                mongodb_params["url"],
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                maxPoolSize=100,
                minPoolSize=10,
            )
            
            # Test connection
            await self.client.admin.command('ping')
            
            self.database = self.client[mongodb_params["database"]]
            self.users_collection = self.database[mongodb_params["collection_users"]]
            
            # Ensure indexes
            await self._ensure_indexes()
            
            self._connected = True
            
            logger.info(
                f"Connected to MongoDB: {mongodb_params['database']}",
                extra={
                    "database": mongodb_params["database"],
                    "collection": mongodb_params["collection_users"],
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to connect to MongoDB: {str(e)}",
                extra={
                    "error": str(e),
                    "mongodb_url": self.settings.mongodb_url,
                }
            )
            raise Exception(f"Database connection failed: {str(e)}")
    
    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Disconnected from MongoDB")
    
    async def _ensure_indexes(self) -> None:
        """
        Ensure required indexes exist on users collection.
        
        Raises:
            Exception: If index creation fails
        """
        try:
            indexes = [
                {"key": [("email", 1)], "unique": True, "background": True},
                {"key": [("created_at", -1)], "background": True},
                {"key": [("is_active", 1)], "background": True},
                {"key": [("last_login", -1)], "background": True},
            ]
            
            for index_spec in indexes:
                await self.users_collection.create_index(**index_spec)
            
            logger.info(
                f"Database indexes ensured for users collection",
                extra={"indexes_count": len(indexes)}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to create database indexes: {str(e)}",
                extra={"error": str(e)}
            )
            raise Exception(f"Index creation failed: {str(e)}")
    
    async def user_exists_by_email(self, email: str) -> bool:
        """
        Check if user exists by email address.
        
        Args:
            email: User email address
            
        Returns:
            True if user exists, False otherwise
            
        Raises:
            Exception: If database operation fails
        """
        try:
            if not self._connected:
                await self.connect()
            
            count = await self.users_collection.count_documents(
                {"email": email.lower()}, 
                limit=1
            )
            
            exists = count > 0
            
            logger.debug(
                f"User existence check for {email}: {'exists' if exists else 'not found'}",
                extra={
                    "email": email.lower(),
                    "exists": exists,
                }
            )
            
            return exists
            
        except Exception as e:
            logger.error(
                f"Failed to check user existence for {email}: {str(e)}",
                extra={
                    "email": email,
                    "error": str(e),
                }
            )
            raise Exception(f"User existence check failed: {str(e)}")
    
    async def create_user(self, user_data: UserCreateModel, hashed_password: str) -> UserModel:
        """
        Create new user in database.
        
        Args:
            user_data: User creation data
            hashed_password: Bcrypt hashed password
            
        Returns:
            Created user model
            
        Raises:
            ValueError: If user already exists
            Exception: If database operation fails
        """
        try:
            if not self._connected:
                await self.connect()
            
            # Check if user already exists
            if await self.user_exists_by_email(user_data.email):
                raise ValueError(f"User with email {user_data.email} already exists")
            
            # Create user document
            now = datetime.utcnow()
            user_doc = {
                "email": user_data.email.lower(),
                "hashed_password": hashed_password,
                "created_at": now,
                "updated_at": None,
                "is_active": True,
                "login_count": 0,
                "last_login": None,
            }
            
            result = await self.users_collection.insert_one(user_doc)
            
            # Add the generated ID to the document
            user_doc["_id"] = str(result.inserted_id)
            
            user_model = UserModel.from_mongo(user_doc)
            
            logger.info(
                f"User created successfully: {user_data.email}",
                extra={
                    "user_id": str(result.inserted_id),
                    "email": user_data.email.lower(),
                    "created_at": now.isoformat(),
                }
            )
            
            return user_model
            
        except DuplicateKeyError:
            error_msg = f"User with email {user_data.email} already exists"
            logger.warning(
                error_msg,
                extra={"email": user_data.email}
            )
            raise ValueError(error_msg)
            
        except ValueError:
            # Re-raise validation errors
            raise
            
        except Exception as e:
            logger.error(
                f"Failed to create user {user_data.email}: {str(e)}",
                extra={
                    "email": user_data.email,
                    "error": str(e),
                }
            )
            raise Exception(f"User creation failed: {str(e)}")
    
    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """
        Get user by email address.
        
        Args:
            email: User email address
            
        Returns:
            User model if found, None otherwise
            
        Raises:
            Exception: If database operation fails
        """
        try:
            if not self._connected:
                await self.connect()
            
            user_doc = await self.users_collection.find_one(
                {"email": email.lower()}
            )
            
            if not user_doc:
                logger.debug(
                    f"User not found: {email}",
                    extra={"email": email.lower()}
                )
                return None
            
            user_model = UserModel.from_mongo(user_doc)
            
            logger.debug(
                f"User retrieved: {email}",
                extra={
                    "user_id": str(user_doc.get("_id")),
                    "email": email.lower(),
                    "is_active": user_doc.get("is_active", True),
                }
            )
            
            return user_model
            
        except Exception as e:
            logger.error(
                f"Failed to get user {email}: {str(e)}",
                extra={
                    "email": email,
                    "error": str(e),
                }
            )
            raise Exception(f"User retrieval failed: {str(e)}")
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        """
        Get user by ID.
        
        Args:
            user_id: User unique identifier
            
        Returns:
            User model if found, None otherwise
            
        Raises:
            Exception: If database operation fails
        """
        try:
            if not self._connected:
                await self.connect()
            
            # Convert string ID to ObjectId
            try:
                object_id = ObjectId(user_id)
            except Exception:
                logger.warning(
                    f"Invalid user ID format: {user_id}",
                    extra={"user_id": user_id}
                )
                return None
            
            user_doc = await self.users_collection.find_one(
                {"_id": object_id}
            )
            
            if not user_doc:
                logger.debug(
                    f"User not found by ID: {user_id}",
                    extra={"user_id": user_id}
                )
                return None
            
            user_model = UserModel.from_mongo(user_doc)
            
            logger.debug(
                f"User retrieved by ID: {user_id}",
                extra={
                    "user_id": user_id,
                    "email": user_doc.get("email"),
                    "is_active": user_doc.get("is_active", True),
                }
            )
            
            return user_model
            
        except Exception as e:
            logger.error(
                f"Failed to get user by ID {user_id}: {str(e)}",
                extra={
                    "user_id": user_id,
                    "error": str(e),
                }
            )
            raise Exception(f"User retrieval by ID failed: {str(e)}")
    
    async def update_user_login_info(self, user_id: str) -> bool:
        """
        Update user login information (last_login, login_count).
        
        Args:
            user_id: User unique identifier
            
        Returns:
            True if update successful, False otherwise
            
        Raises:
            Exception: If database operation fails
        """
        try:
            if not self._connected:
                await self.connect()
            
            try:
                object_id = ObjectId(user_id)
            except Exception:
                logger.warning(
                    f"Invalid user ID format for login update: {user_id}",
                    extra={"user_id": user_id}
                )
                return False
            
            now = datetime.utcnow()
            
            result = await self.users_collection.update_one(
                {"_id": object_id},
                {
                    "$inc": {"login_count": 1},
                    "$set": {
                        "last_login": now,
                        "updated_at": now,
                    }
                }
            )
            
            success = result.modified_count > 0
            
            if success:
                logger.info(
                    f"User login info updated: {user_id}",
                    extra={
                        "user_id": user_id,
                        "last_login": now.isoformat(),
                    }
                )
            else:
                logger.warning(
                    f"No user found to update login info: {user_id}",
                    extra={"user_id": user_id}
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Failed to update login info for user {user_id}: {str(e)}",
                extra={
                    "user_id": user_id,
                    "error": str(e),
                }
            )
            raise Exception(f"Login info update failed: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform database health check.
        
        Returns:
            Health check results
        """
        try:
            if not self._connected:
                await self.connect()
            
            # Test connection with ping
            start_time = datetime.utcnow()
            await self.client.admin.command('ping')
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Get collection stats
            stats = await self.database.command("collStats", self.settings.mongodb_collection_users)
            user_count = stats.get("count", 0)
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "user_count": user_count,
                "connected": self._connected,
            }
            
        except Exception as e:
            logger.error(
                f"Database health check failed: {str(e)}",
                extra={"error": str(e)}
            )
            return {
                "status": "unhealthy",
                "error": str(e),
                "connected": self._connected,
            }


# Global database service instance
_database_service: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """
    Get the global database service instance.
    Uses singleton pattern for connection pooling efficiency.
    
    Returns:
        DatabaseService instance
    """
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
    return _database_service 