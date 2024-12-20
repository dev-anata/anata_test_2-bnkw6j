"""
Setup configuration for the Data Processing Pipeline package.

This setup script enables installation of the Data Processing Pipeline package and its dependencies
across development, staging, and production environments. It defines package metadata, dependencies,
and build requirements following Python packaging best practices.

Version: 1.0.0
"""

import os
from typing import List

from setuptools import find_packages, setup  # version: 68.0+

from src.config.constants import API_VERSION


def read_requirements(filename: str) -> List[str]:
    """
    Read and parse requirements from a requirements file.
    
    Args:
        filename (str): Path to the requirements file
        
    Returns:
        List[str]: List of requirement specifications
        
    Raises:
        FileNotFoundError: If requirements file doesn't exist
    """
    requirements = []
    with open(os.path.join(os.path.dirname(__file__), filename), 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                requirements.append(line)
    return requirements


# Package metadata and configuration
setup(
    name="data-processing-pipeline",
    version=f"1.0.{API_VERSION}",  # Version derived from API version
    description="Cloud-based automation platform for web scraping and OCR data processing",
    long_description=open('README.md', 'r', encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    author="Development Team",
    author_email="team@example.com",
    url="https://github.com/organization/data-processing-pipeline",
    license="MIT",
    
    # Python version requirement
    python_requires=">=3.11",
    
    # Package structure
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    
    # Core dependencies
    install_requires=[
        'fastapi>=0.100.0',          # API framework
        'uvicorn>=0.23.0',           # ASGI server
        'pydantic>=2.1.0',           # Data validation
        'scrapy>=2.9.0',             # Web scraping
        'pytesseract>=0.3.0',        # OCR processing
        
        # Google Cloud dependencies
        'google-cloud-storage>=2.10.0',
        'google-cloud-pubsub>=2.18.0',
        'google-cloud-firestore>=2.11.0',
        'google-cloud-logging>=3.5.0',
        'google-cloud-monitoring>=2.14.0',
        
        # Data processing
        'pandas>=2.0.0',
        'numpy>=1.24.0',
        'pillow>=10.0.0',
        
        # Security
        'python-jose[cryptography]>=3.3.0',
        'passlib[bcrypt]>=1.7.0',
        
        # Monitoring and observability
        'prometheus-client>=0.17.0',
        'opentelemetry-api>=1.19.0',
        'structlog>=23.1.0',
        
        # Utilities
        'pyyaml>=6.0.0',
        'click>=8.1.0',              # CLI framework
    ],
    
    # Development dependencies
    extras_require={
        'dev': [
            # Testing
            'pytest>=7.4.0',
            'pytest-asyncio>=0.21.0',
            'pytest-cov>=4.1.0',
            'pytest-mock>=3.11.0',
            
            # Code quality
            'black>=23.7.0',
            'pylint>=2.17.0',
            'mypy>=1.4.0',
            'isort>=5.12.0',
            
            # Development tools
            'factory-boy>=3.3.0',
            'faker>=19.2.0',
            'debugpy>=1.6.0',
            'ipython>=8.14.0',
            'httpx>=0.24.0',         # Async HTTP client for testing
        ],
    },
    
    # CLI entry point
    entry_points={
        'console_scripts': [
            'pipeline=src.cli.main:main',
        ],
    },
    
    # Package classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.11',
        'Operating System :: OS Independent',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing :: General',
        'Framework :: FastAPI',
        'Framework :: Scrapy',
    ],
    
    # Additional package metadata
    keywords='web-scraping,ocr,data-processing,cloud,automation',
    project_urls={
        'Documentation': 'https://data-processing-pipeline.readthedocs.io/',
        'Source': 'https://github.com/organization/data-processing-pipeline',
        'Issues': 'https://github.com/organization/data-processing-pipeline/issues',
    },
)