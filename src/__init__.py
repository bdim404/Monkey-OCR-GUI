"""
Monkey OCR for Windows - Source Package

This package contains the core source code for the application, including the GUI, API client, and utility modules.
"""

import logging
import sys

# --- Basic Logging Configuration ---
# Configure logging for the entire application package.
# This ensures consistent logging format and level.

# Define a format that is clear and informative
log_format = "%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s"

# Create a handler to output to the console
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter(log_format))

# Get the root logger for the 'src' package and add the handler
package_logger = logging.getLogger(__name__)
package_logger.addHandler(stream_handler)
package_logger.setLevel(logging.INFO) # Default level, can be overridden by settings

# --- Convenience Imports ---
# Make key classes available at the package level for easier access.

try:
    from .config.settings import settings
    from .api.monkey_ocr_client import MonkeyOCRClient
    from .utils.i18n import t, set_locale, get_locale, get_available_locales
except ImportError as e:
    # This can happen during initial setup or if the structure is changed.
    # Log an error to make debugging easier.
    package_logger.error(f"Failed to import core components in src/__init__.py: {e}")

# --- Package Metadata ---
# Define package-level metadata.

__version__ = "1.2.0"  # Corresponds to the latest version
__author__ = "Monkey OCR Team"
__email__ = ""


# Optional: A function to initialize the application environment
def initialize_app():
    """Initializes the application environment, e.g., loading settings."""
    package_logger.info(f"Initializing Monkey OCR for Windows v{__version__}")
    # The settings are already initialized upon import, but we could add more here.
    # For example, setting the locale from the config.
    try:
        set_locale(settings.get("ui.language", "zh_CN"))
        package_logger.info(f"Application locale set to: {get_locale()}")
    except Exception as e:
        package_logger.error(f"Failed to set initial locale: {e}")

