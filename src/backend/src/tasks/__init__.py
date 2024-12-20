"""
Package initialization file for the tasks module that exports core task processing components
and provides version information for the task processing system.

This module serves as the main entry point for task management functionality, exposing
a clean interface for task processing, scheduling, and execution through a unified API.

Version: 1.0.0
"""

# Internal imports with version tracking
from tasks.base import BaseTask, BaseTaskExecutor  # version: 1.0.0
from tasks.scheduler import TaskSchedulerImpl  # version: 1.0.0
from tasks.worker import TaskWorker  # version: 1.0.0

# Package version
__version__ = "1.0.0"

# Export core components
__all__ = [
    "BaseTask",
    "BaseTaskExecutor", 
    "TaskSchedulerImpl",
    "TaskWorker"
]