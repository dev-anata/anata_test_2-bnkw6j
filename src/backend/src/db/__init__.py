"""
Database package initialization module for the Data Processing Pipeline.

This module configures and exports the database client and repositories with enhanced
security, monitoring, and error handling capabilities. It provides centralized database
access and configuration management for the application.

Version: 1.0.0
"""

import logging  # version: 3.11+
import threading  # version: 3.11+
from contextlib import contextmanager  # version: 3.11+
from typing import Optional, Tuple, Dict, Any  # version: 3.11+

from db.firestore import FirestoreClient
from db.repositories.base import BaseRepository
from core.exceptions import StorageException, ConfigurationException
from core.models import Task, TaskExecution, DataObject

# Global database client instance with thread-safety
_db_client: Optional[FirestoreClient] = None
_lock = threading.Lock()

# Configure module logger
logger = logging.getLogger(__name__)

@contextmanager
def get_db_client() -> FirestoreClient:
    """
    Get or create a thread-safe singleton instance of FirestoreClient.
    
    Implements connection pooling, monitoring, and automatic cleanup with
    context management for safe resource handling.
    
    Returns:
        FirestoreClient: Singleton database client instance
        
    Raises:
        StorageException: If database connection fails
        ConfigurationException: If client configuration is invalid
    """
    global _db_client
    
    try:
        with _lock:
            if _db_client is None:
                logger.info("Initializing new database client instance")
                _db_client = FirestoreClient(
                    pool_size=100,  # Production-grade connection pool
                    timeout=30,     # 30 second connection timeout
                    retry_config={
                        'max_attempts': 3,
                        'initial': 1.0,
                        'maximum': 60.0,
                        'multiplier': 2.0
                    }
                )
            
            # Validate client connection
            if not _db_client.is_connected():
                logger.warning("Database client disconnected, reconnecting...")
                _db_client.connect()
                
            logger.debug("Database client ready")
            yield _db_client
            
    except Exception as e:
        logger.error(f"Database client error: {str(e)}")
        raise StorageException(
            "Failed to initialize database client",
            storage_path="firestore",
            storage_details={"error": str(e)}
        )
    
    finally:
        # Cleanup will be handled by context exit
        pass

def init_repositories() -> Tuple['TaskRepository', 'ExecutionRepository', 'DataObjectRepository']:
    """
    Initialize all database repositories with validation and monitoring.
    
    Creates repository instances with proper configuration and validates
    their readiness for database operations.
    
    Returns:
        Tuple containing initialized repository instances:
        - TaskRepository: For task management
        - ExecutionRepository: For execution tracking
        - DataObjectRepository: For data object storage
        
    Raises:
        StorageException: If repository initialization fails
        ConfigurationException: If repository configuration is invalid
    """
    try:
        with get_db_client() as client:
            # Initialize repositories with lazy loading
            from db.repositories.task import TaskRepository
            from db.repositories.execution import ExecutionRepository
            from db.repositories.data_object import DataObjectRepository
            
            logger.info("Initializing database repositories")
            
            # Create repository instances
            task_repo = TaskRepository(client)
            execution_repo = ExecutionRepository(client)
            data_object_repo = DataObjectRepository(client)
            
            # Validate repository configurations
            repositories = (task_repo, execution_repo, data_object_repo)
            for repo in repositories:
                if not isinstance(repo, BaseRepository):
                    raise ConfigurationException(
                        "Invalid repository configuration",
                        {"repository": repo.__class__.__name__}
                    )
            
            logger.info("Database repositories initialized successfully")
            return repositories
            
    except Exception as e:
        logger.error(f"Failed to initialize repositories: {str(e)}")
        raise ConfigurationException(
            "Repository initialization failed",
            {"error": str(e)}
        )

# Export public interface
__all__ = [
    'get_db_client',
    'init_repositories',
    'FirestoreClient',
    'BaseRepository',
    'Task',
    'TaskExecution',
    'DataObject'
]