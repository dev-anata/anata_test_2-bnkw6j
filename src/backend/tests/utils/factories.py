"""
Test data factories for generating test instances of core models.

This module provides factory classes for consistent test data generation using factory_boy.
It supports creating test instances of Task, TaskExecution, and DataObject models with
proper relationships and validation.

Version: 1.0.0
"""

import factory  # version: 3.2.1
from faker import Faker  # version: 18.9.0
from datetime import datetime  # version: 3.11+
from uuid import uuid4  # version: 3.11+

from core.models import Task, TaskExecution, DataObject
from core.types import TaskType, TaskStatus, TaskConfig, TaskResult

# Initialize Faker for generating realistic test data
fake = Faker()

class TaskFactory(factory.Factory):
    """
    Factory for generating Task model instances for testing.
    
    Provides methods for creating individual and batch Task instances with
    configurable properties and valid relationships.
    """
    
    class Meta:
        model = Task
        strategy = factory.BUILD_STRATEGY
    
    # Basic fields with default values
    id = factory.LazyFunction(uuid4)
    type = factory.LazyFunction(lambda: TaskType.scrape)
    status = factory.LazyFunction(lambda: TaskStatus.pending)
    configuration = factory.LazyFunction(
        lambda: {
            "source": fake.url(),
            "parameters": {
                "depth": fake.random_int(min=1, max=3),
                "timeout": fake.random_int(min=30, max=300)
            }
        }
    )
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = None
    scheduled_at = None
    execution_history = factory.LazyFunction(list)

    @classmethod
    def create_batch(cls, size: int, **defaults) -> list[Task]:
        """
        Create multiple Task instances with optional custom configuration.
        
        Args:
            size: Number of instances to create
            **defaults: Default values to apply to all instances
            
        Returns:
            List of generated Task instances
            
        Raises:
            ValueError: If size is less than 1 or greater than 100
        """
        if not 1 <= size <= 100:
            raise ValueError("Batch size must be between 1 and 100")
            
        return [cls.create(**defaults) for _ in range(size)]

    @classmethod
    def with_executions(cls, execution_count: int = 1, **defaults) -> Task:
        """
        Create a Task instance with related TaskExecution instances.
        
        Args:
            execution_count: Number of executions to create
            **defaults: Default values for the Task instance
            
        Returns:
            Task instance with populated execution history
        """
        task = cls.create(**defaults)
        executions = TaskExecutionFactory.create_batch(
            execution_count, task_id=task.id
        )
        task.execution_history = [execution.id for execution in executions]
        return task


class TaskExecutionFactory(factory.Factory):
    """
    Factory for generating TaskExecution model instances for testing.
    
    Supports creation of TaskExecution instances with proper Task relationships
    and execution states.
    """
    
    class Meta:
        model = TaskExecution
        strategy = factory.BUILD_STRATEGY
    
    id = factory.LazyFunction(uuid4)
    task_id = factory.SubFactory(TaskFactory)
    status = factory.LazyFunction(lambda: TaskStatus.running)
    start_time = factory.LazyFunction(datetime.utcnow)
    end_time = None
    result = None
    error_message = None
    output_objects = factory.LazyFunction(list)

    @classmethod
    def completed(cls, **defaults) -> TaskExecution:
        """
        Create a completed TaskExecution instance.
        
        Args:
            **defaults: Default values for the instance
            
        Returns:
            Completed TaskExecution instance with results
        """
        execution = cls.create(
            status=TaskStatus.completed,
            end_time=datetime.utcnow(),
            result={
                "status": "success",
                "data": {"items_processed": fake.random_int(min=1, max=100)},
                "error": None
            },
            **defaults
        )
        return execution

    @classmethod
    def failed(cls, error_message: str = None, **defaults) -> TaskExecution:
        """
        Create a failed TaskExecution instance.
        
        Args:
            error_message: Optional custom error message
            **defaults: Default values for the instance
            
        Returns:
            Failed TaskExecution instance with error details
        """
        execution = cls.create(
            status=TaskStatus.failed,
            end_time=datetime.utcnow(),
            error_message=error_message or fake.sentence(),
            result={
                "status": "error",
                "data": None,
                "error": error_message or fake.sentence()
            },
            **defaults
        )
        return execution


class DataObjectFactory(factory.Factory):
    """
    Factory for generating DataObject model instances for testing.
    
    Supports creation of DataObject instances with proper TaskExecution
    relationships and storage metadata.
    """
    
    class Meta:
        model = DataObject
        strategy = factory.BUILD_STRATEGY
    
    id = factory.LazyFunction(uuid4)
    execution_id = factory.SubFactory(TaskExecutionFactory)
    storage_path = factory.Sequence(lambda n: f"test/data/object_{n}.json")
    content_type = factory.LazyFunction(lambda: "application/json")
    metadata = factory.LazyFunction(
        lambda: {
            "source": fake.url(),
            "timestamp": datetime.utcnow().isoformat(),
            "size_bytes": fake.random_int(min=100, max=10000),
            "attributes": {
                "type": "scraped_data",
                "format": "json",
                "items": fake.random_int(min=1, max=50)
            }
        }
    )
    created_at = factory.LazyFunction(datetime.utcnow)

    @classmethod
    def with_content_type(cls, content_type: str, **defaults) -> DataObject:
        """
        Create a DataObject instance with specific content type.
        
        Args:
            content_type: MIME type for the data object
            **defaults: Default values for the instance
            
        Returns:
            DataObject instance with specified content type
        """
        return cls.create(
            content_type=content_type,
            storage_path=f"test/data/object_{uuid4()}.{content_type.split('/')[-1]}",
            **defaults
        )


__all__ = [
    'TaskFactory',
    'TaskExecutionFactory',
    'DataObjectFactory'
]