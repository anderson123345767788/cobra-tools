import re
import sys
import time
import logging
import subprocess
from pkg_resources import packaging  # type: ignore
from importlib import import_module
from importlib.metadata import distribution, PackageNotFoundError, packages_distributions

from ovl_util.logs import ANSI

MISSING: dict[str, str] = {}
OUTDATED: dict[str, str]  = {}

INSTALLED: list[str] = []
UPDATED: list[str] = []

MODULES: list[str] = []

"""
    Deals with missing packages and tries to install them from the tool itself.
"""

# raw_input returns the empty string for "enter"
def install_prompt(question) -> bool:
    print(question)
    print(f"{ANSI.LIGHT_YELLOW}[Type y and hit Enter]{ANSI.END}{ANSI.LIGHT_GREEN}")
    yes = {'yes', 'y', 'ye'}
    choice = input().lower()
    if choice in yes:
        return True
    else:
        return False

# use pip to install a package
def pip_install(package) -> int:
    logging.info(f"Installing {package}")
    return subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# use pip to install --update a package
def pip_upgrade(package) -> int:
    logging.info(f"Updating {package}")
    return subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", package])


with open("requirements.txt") as requirements:
    lines = requirements.read().splitlines()
    pkg_dist = packages_distributions()
    for line in lines:
        lib, op, version = re.split("(~=|==|>|<|>=|<=)", line)
        try:
            lib_dist = distribution(lib)
            # Get import name from package name
            for module, pkgs in pkg_dist.items():
                if lib in pkgs:
                    MODULES.append(module)
            # Check version
            if packaging.version.parse(lib_dist.metadata['Version']) < packaging.version.parse(version):
                logging.warning(f"{lib} is out of date.")
                OUTDATED[lib] = line # Need full line including ~= for pip install command
        except PackageNotFoundError:
            logging.error(f"{lib} not found.")
            MISSING[lib] = line # Need full line including ~= for pip install command

ASK_INSTALL = f"{ANSI.LIGHT_WHITE}Install the missing dependencies?{ANSI.END} (y/N)"
ASK_UPGRADE = f"{ANSI.LIGHT_WHITE}Update the outdated dependencies?{ANSI.END} (y/N)"

if len(MISSING) and install_prompt(ASK_INSTALL) == True:
    # upgrade pip then try installing the rest of packages
    pip_upgrade('pip')
    for key, package in MISSING.items():
        if pip_install(package) == 0:
            INSTALLED.append(key)

if len(OUTDATED) and install_prompt(ASK_UPGRADE) == True:
    # upgrade pip then try updating the outdated packages
    pip_upgrade('pip')
    for key, package in OUTDATED.items():
        if pip_upgrade(package) == 0:
            UPDATED.append(key)

if hasattr(logging, "success"):
    if len(INSTALLED):
        logging.success(f"Installed: {INSTALLED}")

    if len(UPDATED):
        logging.success(f"Updated: {UPDATED}")

# Test all required modules can be imported
try:
    for module in MODULES:
        import_module(module)
except:
	logging.exception("Some modules could not be imported; make sure you install the required dependencies with pip!")
	time.sleep(15)
