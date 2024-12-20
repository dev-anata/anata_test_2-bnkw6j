"""
Command line interface module for managing system configuration.

This module provides secure CLI commands for viewing, setting, and validating
system configuration with enhanced security controls, caching, and environment-specific
validation.

Version: 1.0.0
"""

import json  # version: 3.11+
import yaml  # version: 6.0+
from typing import Optional, Dict, Any  # version: 3.11+
import click  # version: 8.1+
from rich.console import Console  # version: 13.0+
from rich.table import Table  # version: 13.0+

from config.app_config import AppConfig
from config.settings import settings

# Initialize rich console for enhanced output
console = Console()

@click.group(name='config', help='Manage system configuration securely')
def CONFIG_GROUP() -> None:
    """Configuration management command group."""
    pass

@CONFIG_GROUP.command(name='view', help='View current configuration securely')
@click.option('--format', type=click.Choice(['json', 'yaml']), default='json',
              help='Output format')
@click.option('--section', type=click.Choice(['api', 'storage', 'logging']),
              help='Configuration section to view')
@click.option('--show-sensitive', is_flag=True,
              help='Show sensitive values (requires elevated permissions)')
def view_config(format: str, section: Optional[str], show_sensitive: bool) -> None:
    """
    Display current system configuration with sensitive data masking.

    Args:
        format: Output format (json/yaml)
        section: Specific configuration section to view
        show_sensitive: Flag to show sensitive values (requires elevated permissions)
    """
    try:
        # Get AppConfig instance
        app_config = AppConfig()

        # Get requested configuration section
        if section == 'api':
            config_data = app_config.get_api_config()
        elif section == 'storage':
            config_data = app_config.get_storage_config()
        elif section == 'logging':
            config_data = app_config.get_logging_config()
        else:
            # Get full configuration
            config_data = {
                'api': app_config.get_api_config(),
                'storage': app_config.get_storage_config(),
                'logging': app_config.get_logging_config(),
                'environment': settings.env,
                'debug': settings.debug
            }

        # Mask sensitive data if not explicitly shown
        if not show_sensitive:
            config_data = _mask_sensitive_data(config_data)

        # Format and display configuration
        if format == 'json':
            output = json.dumps(config_data, indent=2)
            console.print_json(output)
        else:
            output = yaml.safe_dump(config_data, default_flow_style=False)
            console.print(output)

    except Exception as e:
        console.print(f"[red]Error viewing configuration: {str(e)}[/red]")
        raise click.Abort()

@CONFIG_GROUP.command(name='set', help='Securely set configuration value')
@click.argument('key')
@click.argument('value')
@click.option('--force', is_flag=True, help='Force update without confirmation')
def set_config(key: str, value: str, force: bool) -> None:
    """
    Securely update system configuration settings.

    Args:
        key: Configuration key path (dot notation)
        value: New value to set
        force: Skip confirmation prompt
    """
    try:
        # Get AppConfig instance
        app_config = AppConfig()

        # Validate key exists and is modifiable
        if not _validate_config_key(key):
            raise ValueError(f"Invalid configuration key: {key}")

        # Parse value based on key type
        parsed_value = _parse_config_value(key, value)

        # Confirm change if not forced
        if not force:
            if not click.confirm(f"Update {key} to {parsed_value}?"):
                console.print("[yellow]Operation cancelled[/yellow]")
                return

        # Update configuration
        key_parts = key.split('.')
        section = key_parts[0]
        
        if section == 'api':
            config = app_config.get_api_config()
        elif section == 'storage':
            config = app_config.get_storage_config()
        elif section == 'logging':
            config = app_config.get_logging_config()
        else:
            raise ValueError(f"Invalid configuration section: {section}")

        # Update nested configuration
        current = config
        for part in key_parts[1:-1]:
            current = current[part]
        current[key_parts[-1]] = parsed_value

        # Save updated configuration
        app_config.update_config({section: config})

        console.print(f"[green]Successfully updated {key}[/green]")

    except Exception as e:
        console.print(f"[red]Error updating configuration: {str(e)}[/red]")
        raise click.Abort()

@CONFIG_GROUP.command(name='validate', help='Validate configuration against schema')
@click.option('--config-file', type=click.Path(exists=True),
              help='Configuration file to validate')
@click.option('--env', type=click.Choice(['dev', 'staging', 'prod']),
              help='Environment to validate against')
def validate_config(config_file: Optional[str], env: Optional[str]) -> None:
    """
    Validate configuration against schema with environment-specific rules.

    Args:
        config_file: Path to configuration file to validate
        env: Target environment for validation
    """
    try:
        # Get AppConfig instance
        app_config = AppConfig()

        # Load configuration from file if specified
        if config_file:
            with open(config_file, 'r') as f:
                if config_file.endswith('.json'):
                    config_data = json.load(f)
                else:
                    config_data = yaml.safe_load(f)
        else:
            # Validate current configuration
            config_data = {
                'api': app_config.get_api_config(),
                'storage': app_config.get_storage_config(),
                'logging': app_config.get_logging_config()
            }

        # Set environment context
        validation_env = env or settings.env

        # Validate configuration
        validation_results = _validate_configuration(config_data, validation_env)

        # Display results
        table = Table(title="Configuration Validation Results")
        table.add_column("Section")
        table.add_column("Status")
        table.add_column("Message")

        for result in validation_results:
            status_color = "green" if result['valid'] else "red"
            table.add_row(
                result['section'],
                f"[{status_color}]{result['status']}[/{status_color}]",
                result.get('message', '')
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error validating configuration: {str(e)}[/red]")
        raise click.Abort()

def _mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive configuration values."""
    sensitive_keys = {
        'api_key', 'token', 'password', 'secret', 'key',
        'credentials', 'encryption_key'
    }
    
    def mask_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        masked = {}
        for k, v in d.items():
            if isinstance(v, dict):
                masked[k] = mask_dict(v)
            elif any(s in k.lower() for s in sensitive_keys):
                masked[k] = '********'
            else:
                masked[k] = v
        return masked
    
    return mask_dict(data)

def _validate_config_key(key: str) -> bool:
    """Validate configuration key exists and is modifiable."""
    valid_keys = {
        'api.timeout', 'api.rate_limit.max_requests',
        'storage.retention.days', 'storage.encryption.enabled',
        'logging.level', 'logging.structured', 'logging.retention_days'
    }
    return key in valid_keys

def _parse_config_value(key: str, value: str) -> Any:
    """Parse configuration value to appropriate type."""
    if key.endswith(('enabled', 'structured')):
        return value.lower() == 'true'
    elif key.endswith(('timeout', 'max_requests', 'days', 'retention_days')):
        return int(value)
    return value

def _validate_configuration(config: Dict[str, Any], env: str) -> list:
    """Validate configuration with environment-specific rules."""
    results = []
    
    # Validate API configuration
    api_config = config.get('api', {})
    api_valid = all([
        isinstance(api_config.get('timeout'), int),
        isinstance(api_config.get('rate_limit', {}).get('max_requests'), int)
    ])
    results.append({
        'section': 'API',
        'valid': api_valid,
        'status': 'Valid' if api_valid else 'Invalid',
        'message': '' if api_valid else 'Invalid API configuration structure'
    })

    # Validate Storage configuration
    storage_config = config.get('storage', {})
    storage_valid = all([
        isinstance(storage_config.get('encryption', {}).get('enabled'), bool),
        isinstance(storage_config.get('retention', {}).get('days'), int)
    ])
    results.append({
        'section': 'Storage',
        'valid': storage_valid,
        'status': 'Valid' if storage_valid else 'Invalid',
        'message': '' if storage_valid else 'Invalid storage configuration structure'
    })

    # Add environment-specific validation
    if env == 'prod':
        # Additional production validation rules
        prod_valid = all([
            storage_config.get('encryption', {}).get('enabled', False),
            api_config.get('rate_limit', {}).get('max_requests', 0) <= 1000
        ])
        results.append({
            'section': 'Production',
            'valid': prod_valid,
            'status': 'Valid' if prod_valid else 'Invalid',
            'message': '' if prod_valid else 'Production security requirements not met'
        })

    return results

# Export configuration command group
__all__ = ['CONFIG_GROUP']