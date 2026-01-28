import os
from setuptools import setup, find_packages
from web2md import __version__, __description__, __author__, __author_email__, __url__, __license__

def read_long_description():
    """Read README.md for PyPI long description (rendered as markdown)"""
    if os.path.exists("README.md"):
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    return __description__

# PyPI package setup configuration
# Modify the marked fields (STEP 1/2/3) before publishing to PyPI
setup(
    # -------------------------- STEP 1: BASIC INFO (MANDATORY MODIFY) --------------------------
    # Unique PyPI package name (use web2md-cli if web2md is taken)
    name="web2md",
    version=__version__,
    author=__author__,
    author_email=__author_email__,
    description=__description__,
    long_description=read_long_description(),
    # Declare README as Markdown for PyPI page rendering
    long_description_content_type="text/markdown",
    # Project repo URL (GitHub/Gitee/GitLab)
    url=__url__,
    license=__license__,
    # Search keywords for PyPI (improve discoverability)
    keywords=["crawler", "markdown", "web2md", "scraper", "dynamic website", "html2md"],
    # -------------------------------------------------------------------------------------------

    # -------------------------- STEP 2: PACKAGE STRUCTURE (NO MODIFY NEEDED) --------------------------
    # Auto discover all packages under the project root
    packages=find_packages(),
    # Include non-Python files (e.g., README, LICENSE) in the package
    include_package_data=True,
    # -------------------------------------------------------------------------------------------------

    # -------------------------- STEP 3: DEPENDENCIES (FIXED - MATCH TOOL REQUIREMENTS) --------------------------
    # Dependencies installed automatically with pip install web2md
    # Specify minimum compatible versions for stability
    install_requires=[
        "playwright>=1.40.0",
        "beautifulsoup4>=4.12.0",
        "markdownify>=0.11.6",
        "lxml>=4.9.0",
        "requests>=2.31.0"
    ],
    # -----------------------------------------------------------------------------------------------------------

    # -------------------------- CLI ENTRY POINT (CRITICAL - NO MODIFY) --------------------------
    # Generate global CLI command: `web2md` (instead of python web2md/cli.py)
    # Format: command_name = package_name.file_name:main_function_name
    entry_points={
        "console_scripts": [
            "web2md = web2md.cli:main",
        ]
    },
    # -------------------------------------------------------------------------------------------

    # -------------------------- COMPATIBILITY (NO MODIFY NEEDED) --------------------------
    # Minimum Python version (Playwright requires 3.8+)
    python_requires=">=3.8",
    # Disable zip packaging (ensure Playwright driver loads correctly)
    zip_safe=False,
    # PyPI classification tags (for package categorization)
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Text Processing :: Markup :: HTML",
        "Topic :: Text Processing :: Markup :: Markdown"
    ]
    # ---------------------------------------------------------------------------------------
)
