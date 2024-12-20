"""
Database models initialization module for the data processing pipeline.

This module exports all Firestore-specific data models and their collection names,
providing a centralized access point for database models used throughout the application.
The models implement the schema design specified in the technical specifications.

Version: 1.0.0
"""

# Import Firestore data models and collection names
from db.models.data_object import FirestoreDataObject
from db.models.data_source import DataSource
from db.models.task import TaskModel, COLLECTION_NAME as TASKS_COLLECTION
from db.models.task_execution import TaskExecutionModel, COLLECTION_NAME as TASK_EXECUTIONS_COLLECTION

# Export all models and collection names
__all__ = [
    # Data Models
    "FirestoreDataObject",  # Firestore-specific data object model
    "DataSource",          # Data source configuration model
    "TaskModel",          # Task management model
    "TaskExecutionModel",  # Task execution tracking model
    
    # Collection Names
    "TASKS_COLLECTION",         # Tasks collection name constant
    "TASK_EXECUTIONS_COLLECTION" # Task executions collection name constant
]