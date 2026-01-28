# web2md

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A powerful, intelligent CLI tool to crawl **dynamic and static websites** with full JavaScript rendering support and convert them to clean, well-formatted Markdown files. Perfect for archiving documentation, creating offline knowledge bases, and preserving web content.

## ✨ Key Features

- 🚀 **Dynamic Site Support**: Full JavaScript rendering via Playwright (Vue/React/Angular/Next.js)
- 🎯 **Smart Content Extraction**: Automatically identifies and extracts core content, removing navigation, ads, and sidebars
- 🔗 **Recursive Crawling**: Intelligently crawls subpages with configurable depth and count limits
- �️ **Media Downloads**: Optional image and video downloading with lazy-loading support
- 📐 **Base URL Intelligence**: Uses browser's `document.baseURI` for accurate relative path resolution
- 🔄 **Local Link Conversion**: Automatically converts HTML links to local Markdown relative paths
- 🧹 **Clean Output**: Preserves tables, code blocks, images, links, and heading hierarchies
- 🔒 **SSL Flexibility**: Handles sites with certificate issues gracefully
- 🌍 **Cross-Platform**: Works on Windows, macOS, and Linux (Python 3.8+)
- 📋 **Universal Compatibility**: Generated Markdown works with Typora, Obsidian, VS Code, and more

## 📦 Installation

### Option 1: Install from PyPI (Recommended)
```bash
pip3 install web2md
```

### Option 2: Install from Source (For Development)
```bash
git clone https://github.com/floatinghotpot/web2md.git
cd web2md
python3 -m pip install -e .
```

### Required: Install Playwright Browser
```bash
# Install Chromium driver (required for JavaScript rendering)
python3 -m playwright install chromium

# Linux only: Install system dependencies
python3 -m playwright install-deps chromium
```

## 🚀 Quick Start

### Basic Usage
```bash
# Crawl a single page (auto-generated save directory)
web2md https://docs.python.org/3/tutorial/

# Specify custom save directory
web2md https://docs.python.org/3/tutorial/ ./python-docs

# Crawl with images
web2md https://example.com/docs --picture

# Limit crawl depth and count
web2md https://example.com/docs --depth 2 --count 10

# Crawl with images and videos
web2md https://example.com/docs --picture --video --depth 3
```

### Show Help
```bash
web2md -h
```

## 📖 Usage

### Command Syntax
```
web2md [URL] [SAVE_DIR] [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `web_url` | ✅ Yes | Target webpage URL (must start with http/https) |
| `save_folder` | ❌ No | Local save directory (auto-generated from URL if omitted) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--depth N` | `5` | Maximum relative crawl depth from base URL |
| `--count N` | `999` | Maximum number of pages to crawl (0 = unlimited) |
| `--picture` | `False` | Download and save images to local `images/` directory |
| `--video` | `False` | Download and save videos to local `videos/` directory |
| `-h, --help` | - | Show help message and exit |

### Examples

#### 1. Unlimited Crawl with Depth Limit
```bash
web2md https://company.com/docs/home company-docs --depth 2
```
- Crawls all pages within 2 levels of `/docs/`
- Saves to `./company-docs/`

#### 2. Limited Page Count
```bash
web2md https://company.com/docs/home company-docs --depth 2 --count 5
```
- Stops after crawling 5 pages
- Useful for testing or sampling large sites

#### 3. Crawl with Images
```bash
web2md https://company.com/docs/home --picture --count 3
```
- Downloads images to `images/` subdirectory
- Converts image URLs to local relative paths in Markdown

#### 4. Auto-Generated Save Directory
```bash
web2md https://company.com/docs/home --depth 1 --count 10
```
- Auto-creates directory: `company_com_docs/`

## 🎯 How It Works

### 1. Base URL Calculation
The tool automatically determines a **base URL** from your target URL:
- Target: `https://company.com/docs/home` → Base: `https://company.com/docs/`
- All crawling is scoped to pages under this base URL

### 2. Intelligent Path Resolution
Uses the browser's `document.baseURI` to correctly resolve relative URLs:
- Handles `<base>` tags in HTML
- Respects redirects and trailing slashes
- Resolves lazy-loaded images with `data-src`, `srcset`, etc.

### 3. Smart Content Extraction
Automatically identifies core content using priority selectors:
1. `<main>` tag
2. `.article-content` or `.article_content`
3. `#main-content`
4. `.content`
5. `<article>` tag
6. Fallback to `<body>` (with cleanup)

### 4. Media Handling
When `--picture` or `--video` is enabled:
- Downloads media files to `images/` or `videos/` subdirectories
- Generates unique filenames with MD5 hash to prevent duplicates
- Converts URLs to local relative paths in Markdown
- Supports lazy-loading attributes: `data-src`, `data-original`, `srcset`

### 5. Filename Generation
MD filenames are generated from URLs:
- Remove base URL prefix
- Replace `/` with `_`
- Filter illegal characters
- Example: `https://company.com/docs/api/auth` → `api_auth.md`

## ⚙️ Configuration

### Built-in Settings (in `web2md/cli.py`)

#### Playwright Configuration
```python
PLAYWRIGHT_CONFIG = {
    "headless": False,           # Set to True for background crawling
    "timeout": 60000,            # Page load timeout (ms)
    "wait_for_load": "networkidle",  # Wait strategy
    "sleep_after_load": 2,       # Additional wait time (seconds)
    "user_agent": "Mozilla/5.0..." # Custom user agent
}
```

#### Media Configuration
```python
MEDIA_CONFIG = {
    "timeout": 30000,            # Media download timeout (ms)
    "image_dir": "images",       # Image save subdirectory
    "video_dir": "videos",       # Video save subdirectory
    "allowed_img_ext": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "allowed_vid_ext": [".mp4", ".avi", ".mov", ".webm", ".flv", ".mkv"]
}
```

#### Content Filtering
```python
REMOVE_TAGS = ["nav", "header", "footer", "aside", "script", "style", "iframe", "sidebar"]

CORE_CONTENT_SELECTORS = [
    ("main", {}),
    ("div", {"class_": "article-content"}),
    ("article", {})
]
```

#### Crawl Defaults
```python
DEFAULT_CRAWL_CONFIG = {
    "max_depth": 5,              # Default max depth
    "max_count": 999,            # Default max pages
    "allowed_schemes": ["http", "https"],
    "exclude_patterns": [r"\.pdf$", r"\.zip$", r"\.exe$"]
}
```

## 🔧 Advanced Usage

### Debug Mode (Show Browser)
Edit `web2md/cli.py` and set:
```python
PLAYWRIGHT_CONFIG = {
    "headless": False,  # Shows browser window
    ...
}
```

### Custom Content Selectors
Add site-specific selectors to `CORE_CONTENT_SELECTORS`:
```python
CORE_CONTENT_SELECTORS = [
    ("main", {}),
    ("div", {"class_": "documentation-content"}),  # Custom selector
    ("article", {})
]
```

### Anti-Bot Detection
Install and use `playwright-stealth`:
```bash
pip3 install playwright-stealth
```

Add to `get_dynamic_html()` in `web2md/cli.py`:
```python
from playwright_stealth import stealth_sync

page = context.new_page()
stealth_sync(page)  # Add this line
page.goto(url, ...)
```

### Authentication
Add login logic in `get_dynamic_html()` before `page.goto()`:
```python
page.goto("https://example.com/login")
page.fill("#username", "your-username")
page.fill("#password", "your-password")
page.click("#login-button")
time.sleep(2)
```

## 🐛 Troubleshooting

### SSL Certificate Errors
The tool automatically disables SSL verification for downloads. If you encounter issues, check your network/firewall settings.

### Timeout Errors
Increase timeout in `PLAYWRIGHT_CONFIG`:
```python
"timeout": 120000,  # 2 minutes
```

### Missing Content
1. Check if content is in `<main>` or common content tags
2. Add custom selectors to `CORE_CONTENT_SELECTORS`
3. Run with `headless: False` to debug visually

### Image Download Failures
- Verify image URLs are accessible
- Check if images require authentication
- Some CDNs may block automated downloads

## 📋 Dependencies

Automatically installed via `pip`:
- **playwright** - Browser automation and JS rendering
- **beautifulsoup4** - HTML parsing and manipulation
- **lxml** - Fast XML/HTML parser
- **markdownify** - HTML to Markdown conversion
- **urllib3** - HTTP client utilities

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (if available)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup
```bash
git clone https://github.com/floatinghotpot/web2md.git
cd web2md
python3 -m pip install -e .
python3 -m playwright install chromium
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Playwright](https://playwright.dev/) for powerful browser automation
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- [markdownify](https://github.com/matthewwithanm/markdownify) for clean Markdown conversion

---

**Made with ❤️ for developers, researchers, and documentation enthusiasts.**

If you find this tool useful, please consider giving it a ⭐ on GitHub!
