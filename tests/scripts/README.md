# Test Scripts Directory

This directory contains development and testing utilities for the IntelliBrowse project.

## Purpose

The `test/scripts/` directory houses temporary scripts and utilities used during development, testing, and debugging. These scripts should not be imported or used in production code.

## Naming Convention

All script files must follow the naming convention:
- **Python scripts**: `tmp_<purpose>_script.py`
- **Shell scripts**: `tmp_<purpose>_script.sh`

Examples:
- `tmp_database_setup_script.py`
- `tmp_api_test_script.py`
- `tmp_cleanup_script.sh`

## Script Guidelines

### Python Scripts
```python
#!/usr/bin/env python3
"""
Temporary script for [purpose]
This script is for development/testing only and should not be used in production.
"""

def main():
    # Script logic here
    pass

if __name__ == "__main__":
    main()
```

### Shell Scripts
```bash
#!/bin/bash
# Temporary script for [purpose]
# This script is for development/testing only and should not be used in production.

set -e  # Exit on any error

main() {
    # Script logic here
    echo "Script completed successfully"
}

main "$@"
```

## Current Scripts

*No scripts have been created yet. This section will be updated as scripts are added.*

## Usage Notes

1. **Temporary Nature**: Scripts in this directory are temporary and may be deleted or modified frequently
2. **No Production Use**: These scripts must never be imported or used in production code
3. **Documentation**: Each script should include a clear description of its purpose
4. **Cleanup**: Remove scripts when they are no longer needed
5. **Permissions**: Ensure shell scripts are executable (`chmod +x script_name.sh`)

## Common Script Types

- **Database Setup**: Scripts for initializing test databases
- **API Testing**: Scripts for testing API endpoints
- **Data Generation**: Scripts for creating test data
- **Environment Setup**: Scripts for setting up development environments
- **Cleanup**: Scripts for cleaning up temporary files or test data
- **Migration**: Scripts for database migrations during development

## Integration with Development Workflow

These scripts can be used for:
- Quick testing of new features
- Setting up development environments
- Automating repetitive development tasks
- Debugging specific issues
- Generating test data
- Performance testing

Remember to update this README when adding new scripts or changing the workflow. 