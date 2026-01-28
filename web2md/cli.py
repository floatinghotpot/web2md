import argparse
from urllib.parse import urlparse, urljoin, unquote, urlunparse
from urllib.request import urlretrieve, build_opener, HTTPCookieProcessor, HTTPSHandler
from urllib.error import URLError
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import markdownify
import os
import time
import re
import sys
import hashlib
import socket
import ssl

# ===================== Configurable Params (Adjust as needed) =====================
PLAYWRIGHT_CONFIG = {
    "headless": True,  # Set to True for background crawling (no browser window)
    "timeout": 60000,   # Page load timeout (ms)
    "wait_for_load": "networkidle",  # Wait for page full dynamic render
    "sleep_after_load": 2,  # Sleep after load (s) for JS render completion
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}
MEDIA_CONFIG = {
    "timeout": 30000,  # Media download timeout (s)
    "image_dir": "images",  # Image save subdirectory (same level as MD)
    "video_dir": "videos",  # Video save subdirectory (same level as MD)
    "allowed_img_ext": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "allowed_vid_ext": [".mp4", ".avi", ".mov", ".webm", ".flv", ".mkv", ".mpeg", ".mpg"]
}
# Tags to remove (keep only core content)
REMOVE_TAGS = ["nav", "header", "footer", "aside", "script", "style", "iframe", "sidebar"]
# Core content selectors (match by priority, stop on first match)
CORE_CONTENT_SELECTORS = [
    ("main", {}),
    ("div", {"class_": "article-content"}),
    ("div", {"class_": "article_content"}),
    ("div", {"id": "main-content"}),
    ("div", {"class_": "content"}),
    ("article", {})
]
# Default crawl config
DEFAULT_CRAWL_CONFIG = {
    "max_depth": 5,     # Default max relative crawl depth
    "max_count": 999,     # Default max file count (0 = unlimited)
    "allowed_schemes": ["http", "https"],
    "exclude_patterns": [r"\.pdf$", r"\.zip$", r"\.rar$", r"\.7z$", r"\.tar$", r"\.gz$", r"\.exe$"]
}
# ==================================================================================

# Global variables (initialized once, shared across all functions)
crawled_urls = set()    # Stored crawled URLs to avoid duplication
base_url = None         # Dynamic base URL (parent dir of target URL, core benchmark)
base_parsed = None      # Parsed result of base_url
root_save_dir = None    # Local root save directory (absolute path, no affect on filename)
max_crawl_depth = None  # Max relative crawl depth based on base_url
max_crawl_count = None  # Max crawl file count (0 = unlimited)
crawl_picture = False   # Whether to crawl pictures (--picture)
crawl_video = False     # Whether to crawl videos (--video)
crawled_count = 0       # Current crawled file count (real-time statistics)

# New: Opener that disables SSL certificate verification
def create_ssl_unverified_opener():
    """Create an opener that disables SSL certificate verification to solve the CERTIFICATE_VERIFY_FAILED error"""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    opener = build_opener(HTTPSHandler(context=context), HTTPCookieProcessor())
    return opener

# Initialize global opener
ssl_unverified_opener = create_ssl_unverified_opener()

def validate_url(url):
    """Validate URL legality, must start with http/https"""
    if not re.match(r'^https?://', url, re.IGNORECASE):
        raise argparse.ArgumentTypeError(f"Invalid URL: {url} | Must start with http/https")
    return url

def validate_depth(depth):
    """Validate crawl depth is non-negative integer"""
    try:
        depth_int = int(depth)
        if depth_int < 0:
            raise ValueError("Depth cannot be negative")
        return depth_int
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid depth: {depth} | Must be non-negative integer (0,1,2...)")

def validate_count(count):
    """Validate crawl count is non-negative integer"""
    try:
        count_int = int(count)
        if count_int < 0:
            raise ValueError("Count cannot be negative")
        return count_int
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid count: {count} | Must be non-negative integer (0 = unlimited)")

def get_url_parent_dir(url):
    """Extract parent directory of any URL (core for generating base_url)
    Example: https://company.com/docs/home → https://company.com/docs/
    Example: https://company.com/docs/ → https://company.com/docs/
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    # Set parent path to self if path is empty or only '/'
    if not path or path == '/':
        parent_path = '/'
    else:
        parent_path = os.path.dirname(path)
        if not parent_path.startswith('/'):
            parent_path = f"/{parent_path}"
    # Reassemble parent URL, force end with '/' for easy prefix matching
    parent_parsed = parsed._replace(path=parent_path.rstrip('/') + '/')
    return urlunparse(parent_parsed)

def init_global_config(target_url, save_dir, depth, count, pic, vid):
    """Initialize global config, core: generate dynamic base_url"""
    global base_url, base_parsed, root_save_dir, max_crawl_depth, max_crawl_count, crawl_picture, crawl_video
    base_url = get_url_parent_dir(target_url)
    base_parsed = urlparse(base_url)
    root_save_dir = os.path.abspath(save_dir)
    max_crawl_depth = depth
    max_crawl_count = count
    crawl_picture = pic
    crawl_video = vid
    # Set global socket timeout (fix urlretrieve timeout issue)
    socket.setdefaulttimeout(MEDIA_CONFIG["timeout"])
    # Print init info
    print(f"🔧 Global Config Initialized")
    print(f"   ├─ Target URL: {target_url}")
    print(f"   ├─ Base URL (Benchmark): {base_url} (All operations based on this)")
    print(f"   ├─ Local Save Dir: {root_save_dir}")
    print(f"   ├─ Max Crawl Depth: {max_crawl_depth}")
    print(f"   ├─ Max Crawl Count: {max_crawl_count} (0 = unlimited)")
    print(f"   ├─ Crawl Pictures: {'✅ Enabled' if crawl_picture else '❌ Disabled'} (--picture)")
    print(f"   └─ Crawl Videos: {'✅ Enabled' if crawl_video else '❌ Disabled'} (--video)")

def generate_auto_save_dir():
    """Generate default local save dir name (based on base_url's domain + path)"""
    dir_name = f"{base_parsed.netloc}_{base_parsed.path.strip('/').replace('/', '_')}"
    dir_name = re.sub(r'[^\w\-]', '_', dir_name)  # Filter illegal chars
    dir_name = re.sub(r'_+', '_', dir_name).strip('_')
    return dir_name if dir_name else "web2md_docs"

def get_file_hash(url, length=8):
    """Generate 8-bit MD5 hash of URL for media file renaming (avoid duplication)"""
    return hashlib.md5(url.encode('utf-8')).hexdigest()[:length]

def get_valid_media_filename(url, default_ext=".file"):
    """Generate legal media filename, filter system illegal characters"""
    try:
        parsed = urlparse(unquote(url))
        filename = os.path.basename(parsed.path) or f"media_{get_file_hash(url)}"
        name, ext = os.path.splitext(filename)
        ext = ext.lower() if ext else default_ext
        # Filter cross-platform illegal chars
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        safe_name = re.sub(r'_+', '_', safe_name).strip('_')
        return f"{safe_name}_{get_file_hash(url)}{ext}"
    except Exception:
        return f"fallback_{get_file_hash(url)}{default_ext}"

def download_media_file(media_url, md_file_path, allowed_exts, media_type):
    """Download media file (image/video), save to MD same-level dir, return local relative path
    Optimization 1: Images/videos are not restricted by the base_url parent directory
    Optimization 2: Use an opener that disables SSL verification to solve certificate errors
    :param media_url: Absolute URL of media file
    :param md_file_path: Local path of corresponding MD file
    :param allowed_exts: Allowed media extensions
    :param media_type: Media type (image/video)
    :return: Local relative path / original URL (if download failed)
    """
    if not (crawl_picture or crawl_video) or not media_url or not md_file_path:
        return media_url
    if not media_url.startswith(('http://', 'https://')):
        return media_url
    # Validate media extension
    ext = os.path.splitext(urlparse(unquote(media_url)).path)[1].lower()
    if ext not in allowed_exts:
        return media_url
    # Media save dir: same level as MD → images/ / videos/
    md_dir = os.path.dirname(md_file_path)
    media_dir = os.path.join(md_dir, MEDIA_CONFIG[f"{media_type}_dir"])
    os.makedirs(media_dir, exist_ok=True)
    # Generate legal filename
    filename = get_valid_media_filename(media_url, ext)
    save_path = os.path.join(media_dir, filename)
    # Return relative path if file already exists
    if os.path.exists(save_path):
        rel_path = os.path.relpath(save_path, md_dir).replace(os.sep, '/')
        return rel_path
    # Optimization 2: Use opener with disabled SSL verification to download files
    try:
        print(f"📥 Download {media_type}: {filename} (from: {media_url})")
        # Replace urlretrieve with opener.open, disabling SSL verification
        with ssl_unverified_opener.open(media_url, timeout=MEDIA_CONFIG["timeout"]) as response, open(save_path, 'wb') as f:
            f.write(response.read())
        rel_path = os.path.relpath(save_path, md_dir).replace(os.sep, '/')
        return rel_path
    except socket.timeout:
        print(f"⚠️  {media_type.capitalize()} download failed: Timeout ({MEDIA_CONFIG['timeout']}s) - {media_url}")
        return media_url
    except ssl.SSLError:
        print(f"⚠️  {media_type.capitalize()} download failed: SSL Certificate Verify Failed - {media_url}")
        return media_url
    except Exception as e:
        print(f"⚠️  {media_type.capitalize()} download failed: {str(e)[:50]} - {media_url}")
        return media_url

def crawl_media(soup, md_file_path, current_url):
    """Crawl pictures/videos on demand, replace soup links with local relative paths"""
    if not soup or not md_file_path:
        return soup
    
    def extract_best_url(tag, attrs):
        """Extract best possible URL from a list of attributes (handles lazy-loading and srcset)"""
        for attr in attrs:
            val = tag.get(attr, "").strip()
            if not val:
                continue
            if attr == "srcset":
                # Handle srcset: "url1 size1, url2 size2"
                # Pick the last one (usually highest quality)
                parts = [p.strip() for p in val.split(",") if p.strip()]
                if parts:
                    return parts[-1].split(" ")[0].strip()
            return val
        return None

    # Crawl pictures
    if crawl_picture:
        for img in soup.find_all("img"):
            # Priority: Common lazy-load attrs > srcset > src
            src = extract_best_url(img, ["data-src", "data-original", "data-original-src", "file-src", "srcset", "src"])
            if src:
                abs_src = urljoin(current_url, src)
                img["src"] = download_media_file(abs_src, md_file_path, MEDIA_CONFIG["allowed_img_ext"], "image")
                
    # Crawl videos
    if crawl_video:
        # Process <video> tag
        for video in soup.find_all("video"):
            src = extract_best_url(video, ["src", "data-src"])
            if src:
                abs_src = urljoin(current_url, src)
                video["src"] = download_media_file(abs_src, md_file_path, MEDIA_CONFIG["allowed_vid_ext"], "video")
        
        # Process <source> tag
        for source in soup.find_all("source"):
            src = extract_best_url(source, ["src", "srcset"])
            if src:
                abs_src = urljoin(current_url, src)
                ext = os.path.splitext(urlparse(unquote(abs_src)).path)[1].lower()
                if ext in MEDIA_CONFIG["allowed_vid_ext"]:
                    source["src"] = download_media_file(abs_src, md_file_path, MEDIA_CONFIG["allowed_vid_ext"], "video")
                elif ext in MEDIA_CONFIG["allowed_img_ext"] and crawl_picture:
                    source["src"] = download_media_file(abs_src, md_file_path, MEDIA_CONFIG["allowed_img_ext"], "image")
    return soup

def get_dynamic_html(url):
    """Get dynamically rendered HTML content via Playwright (adapt to JS loaded pages)
    :return: (html, final_url, base_uri) or (None, None, None)
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=PLAYWRIGHT_CONFIG["headless"])
            context = browser.new_context(
                user_agent=PLAYWRIGHT_CONFIG["user_agent"],
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={"Referer": base_url},
                ignore_https_errors=True  # New: Playwright ignores HTTPS errors
            )
            page = context.new_page()
            response = page.goto(
                url,
                timeout=PLAYWRIGHT_CONFIG["timeout"],
                wait_until=PLAYWRIGHT_CONFIG["wait_for_load"]
            )
            time.sleep(PLAYWRIGHT_CONFIG["sleep_after_load"])
            html = page.content()
            final_url = page.url
            # Get the actual base URI used by the browser (handles <base> tags and redirects)
            base_uri = page.evaluate("document.baseURI") or final_url
            context.close()
            browser.close()
            print(f"✅ Page loaded successfully: {url}")
            return html, final_url, base_uri
    except PlaywrightTimeoutError:
        print(f"❌ Page load timeout: Exceed {PLAYWRIGHT_CONFIG['timeout']/1000}s - {url}")
        return None, None, None
    except Exception as e:
        print(f"❌ Page request failed: {str(e)[:80]} - {url}")
        return None, None, None

def calculate_relative_depth(url):
    """Calculate relative crawl depth of URL based on base_url (for max_depth control)
    :return: Relative depth (0 = base_url itself, -1 = invalid)
    """
    if not url or not base_parsed:
        return -1
    parsed = urlparse(url)
    # Filter different domain names
    if parsed.netloc != base_parsed.netloc:
        return -1
    # Extract base path and target path (unified format)
    base_path = base_parsed.path.rstrip('/') + '/'
    target_path = unquote(parsed.path).rstrip('/') + '/'
    if not target_path.startswith(base_path):
        return -1
    # Calculate relative depth
    relative_path = target_path[len(base_path):].rstrip('/')
    if not relative_path:
        return 0  # Exact base_url, depth 0
    depth = len([seg for seg in relative_path.split('/') if seg.strip()])
    return depth

def is_allowed_url(url):
    """Judge if URL is allowed to crawl
    Optimization 1: Strictly restrict page URL to base_url parent directory level, 
    media resources are not subject to this restriction (media logic is in download_media_file)
    Rules: 1. Same domain as base_url 2. Valid relative depth 3. Not crawled 4. Not excluded format
    :return: True (allowed) / False (forbidden)
    """
    global crawled_count
    # Check max crawl count (stop if reach limit, 0 = unlimited)
    if max_crawl_count > 0 and crawled_count >= max_crawl_count:
        return False
    if not url:
        return False
    parsed = urlparse(url)
    # Filter non-http/https schemes
    if parsed.scheme not in DEFAULT_CRAWL_CONFIG["allowed_schemes"]:
        return False
    # Check relative depth (Strictly restrict pages to the base_url parent directory)
    depth = calculate_relative_depth(url)
    if depth < 0 or depth > max_crawl_depth:
        return False
    # Filter excluded file formats
    for pattern in DEFAULT_CRAWL_CONFIG["exclude_patterns"]:
        if re.search(pattern, url, re.IGNORECASE):
            return False
    # Filter crawled URLs
    if url in crawled_urls:
        return False
    return True

def extract_allowed_links(html, base_uri):
    """Extract all legal sublinks from page for recursive crawling"""
    if not html or not base_uri:
        return set()
    allowed_links = set()
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        # Filter mail/tel/JS/anchor links
        if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
            continue
        # Assemble to absolute URL using browser's resolved base URI
        abs_url = urljoin(base_uri, href)
        if is_allowed_url(abs_url):
            allowed_links.add(abs_url)
    return allowed_links

def url_to_md_filename(url):
    """Core: Generate MD filename based on base_url (strictly follow rules)
    Rules: 1. Remove base_url prefix 2. Replace / with _ 3. Filter illegal chars 4. Suffix with .md
    Example: https://company.com/docs/home → home → home.md
    Example: https://company.com/docs/home/sub → home/sub → home_sub.md
    Example: https://company.com/docs/ → index.md
    """
    url_lower = url.lower()
    base_url_lower = base_url.lower()
    # Step 1: Strictly remove base_url prefix
    if url_lower.startswith(base_url_lower):
        name_part = url_lower[len(base_url_lower):].rstrip('/')
    else:
        # Fallback: Get last segment of URL path
        name_part = os.path.basename(urlparse(url).path).rstrip('/') or "unknown"
    # Step 2: Fallback if name_part is empty (URL == base_url)
    if not name_part:
        return "index.md"
    # Step 3: Replace / with _ + filter illegal chars + merge consecutive underscores
    name_part = name_part.replace('/', '_')
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', name_part)
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')
    # Step 4: Suffix with .md
    return f"{safe_name}.md" if safe_name else "index.md"

def get_md_file_path(url):
    """Get local absolute path of MD file (root save dir + legal filename)"""
    if not root_save_dir or not url:
        fallback = os.path.join(root_save_dir, f"unknown_{hash(url) % 10000}.md")
        print(f"⚠️  Config missing, use fallback MD path: {os.path.basename(fallback)}")
        return fallback
    # Core: Only root save dir + legal filename (no other splicing)
    md_filename = url_to_md_filename(url)
    md_file_path = os.path.join(root_save_dir, md_filename)
    # Ensure path is in root save dir (prevent path traversal)
    md_file_path = os.path.abspath(md_file_path)
    if not md_file_path.startswith(root_save_dir):
        md_file_path = os.path.join(root_save_dir, md_filename)
    return md_file_path

def fix_local_links(html, current_url, base_uri):
    """Fix <a> links in page to local MD relative paths"""
    if not html or not current_url or not root_save_dir:
        return html
    soup = BeautifulSoup(html, "lxml")
    current_md_path = get_md_file_path(current_url)
    current_md_dir = os.path.dirname(current_md_path)
    
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
            continue
        # Resolve target URL against base_uri, but identify current path via current_url
        abs_url = urljoin(base_uri, href)
        if is_allowed_url(abs_url):
            target_md_path = get_md_file_path(abs_url)
            rel_link = os.path.relpath(target_md_path, current_md_dir).replace(os.sep, '/')
            a["href"] = rel_link
    return str(soup)

def extract_core_content(html, md_file_path, base_uri):
    """Parse HTML, extract core content, crawl media files on demand"""
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    # Remove useless tags to simplify content
    for tag in REMOVE_TAGS:
        for elem in soup.find_all(tag):
            elem.decompose()
    # Crawl media and replace local links if enabled
    if crawl_picture or crawl_video:
        soup = crawl_media(soup, md_file_path, base_uri)
    # Match core content selectors by priority
    core_content = None
    for tag, attrs in CORE_CONTENT_SELECTORS:
        core_content = soup.find(tag, attrs=attrs)
        if core_content:
            print(f"✅ Core content matched: <{tag} {attrs}>")
            break
    # Fallback: Extract entire body if no selector matched
    if not core_content:
        core_content = soup.find("body")
        if not core_content:
            print(f"❌ No extractable content found")
            return None
        print(f"⚠️  No precise selector matched, extract entire <body> content")
    return str(core_content)

def html2md(html_content):
    """Convert HTML to Markdown, reserve images/videos/tables/codes/lists"""
    if not html_content:
        return None
    try:
        md_content = markdownify.markdownify(
            html_content,
            heading_style="ATX",  # MD heading style: # H1, ## H2
            bullets="-*+",        # Unordered list symbols
            code_language="python",  # Default code block language
            convert_ol=True,      # Convert ordered lists
            convert_ul=True,      # Convert unordered lists
            convert_table=True,   # Convert tables
            convert_image=True,   # Convert images
            convert_video=True,   # Convert videos
            link_style="inlined", # Link style: [text](url)
            convert_br=True       # Convert <br> to line break
        )
        # Clean extra blank lines and trailing spaces
        md_lines = [line.rstrip() for line in md_content.splitlines() if line.strip()]
        return "\n".join(md_lines).strip()
    except Exception as e:
        print(f"❌ HTML to Markdown conversion failed: {str(e)[:80]}")
        return None

def save_md_file(md_content, url):
    """Save MD file to local, return absolute file path
    :return: MD file path (success) / False (failed)
    """
    global crawled_count
    if not md_content or not url:
        print(f"❌ Skip MD save: Empty content or URL - {url}")
        return False
    # Check max crawl count before save
    if max_crawl_count > 0 and crawled_count >= max_crawl_count:
        print(f"❌ Skip MD save: Reach max crawl count ({max_crawl_count}) - {url}")
        return False
    md_file_path = get_md_file_path(url)
    md_filename = os.path.basename(md_file_path)
    try:
        # Write file with utf-8 encoding (support all characters)
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        crawled_count += 1  # Increment crawled count after successful save
        print(f"✅ MD file saved successfully: {md_filename} (Target: {url}) [Count: {crawled_count}]")
        return md_file_path
    except IOError as e:
        print(f"❌ MD file save failed: {str(e)[:80]} - {md_filename}")
        return False

def crawl_page_recursive(url):
    """Recursively crawl page and subpages (core crawl logic)
    Termination conditions: 1. URL not allowed 2. URL crawled 3. Max count reached
    """
    # Global termination: Max crawl count reached
    if max_crawl_count > 0 and crawled_count >= max_crawl_count:
        print(f"🔴 Crawl stopped: Reach max crawl count ({max_crawl_count})")
        return
    # Local termination: URL not allowed or already crawled
    if not url or not is_allowed_url(url) or url in crawled_urls:
        return
    crawled_urls.add(url)
    
    # 1. Get dynamic HTML content (return final_url and browser's base_uri)
    html, final_url, page_base_url = get_dynamic_html(url)
    if not html:
        return
    
    # 2. Extract legal sublinks for recursive crawling (use page_base_url for resolution)
    sub_links = extract_allowed_links(html, page_base_url)
    
    # 3. Fix page internal links to local MD relative paths
    html_fixed = fix_local_links(html, final_url, page_base_url)
    
    # 4. Extract core content and convert to Markdown
    md_file_path_temp = get_md_file_path(url)
    core_html = extract_core_content(html_fixed, md_file_path_temp, page_base_url)
    md_content = html2md(core_html)
    if not md_content:
        return
    
    # 5. Save MD file to local
    md_file_path = save_md_file(md_content, url)
    if not md_file_path:
        return
    
    # 6. Recursively crawl sublinks (depth-first)
    if sub_links and (max_crawl_count == 0 or crawled_count < max_crawl_count):
        current_depth = calculate_relative_depth(url)
        print(f"\n🔍 Found {len(sub_links)} legal subpages, start recursive crawling (Current Depth: {current_depth})")
        for sub_url in sorted(sub_links):
            # Terminate recursion if max count reached
            if max_crawl_count > 0 and crawled_count >= max_crawl_count:
                break
            crawl_page_recursive(sub_url)

def main():
    """Main function: Parse CLI args → Init config → Start crawling"""
    parser = argparse.ArgumentParser(
        prog="web2md",
        description="📄 Dynamic Webpage to Markdown Crawler | Dynamic Base URL | Exact Filename | Media Crawl On Demand",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="===== Core Rules =====\n"
               "1. Auto set parent dir of target URL as base_url (all operations based on this)\n"
               "2. MD Filename: Remove base_url prefix → replace / with _ → filter illegal chars → suffix .md\n"
               "3. Crawl Scope: Same domain as base_url + relative depth ≤ --depth + count ≤ --count\n"
               "4. Media Scope: No parent dir restriction (images/videos can be from any domain)\n"
               "===== Usage Examples =====\n"
               "  1. Unlimited crawl: web2md https://company.com/docs/home company-docs --depth 2\n"
               "  2. Limit 5 files: web2md https://company.com/docs/home company-docs --depth 2 --count 5\n"
               "  3. Crawl MD + pictures (limit 3 files): web2md https://company.com/docs/home --picture --count 3\n"
               "  4. Auto save dir: web2md https://company.com/docs/home --depth 1 --count 10"
    )
    # Mandatory arg: Target URL
    parser.add_argument("web_url", type=validate_url, help="Target webpage URL (must start with http/https)")
    # Optional arg: Local save directory (auto generate if omitted)
    parser.add_argument("save_folder", nargs='?', help="Local root save directory for MD files (optional)")
    # Optional args: Crawl depth, count, picture, video
    parser.add_argument("--depth", type=validate_depth, default=DEFAULT_CRAWL_CONFIG["max_depth"],
                        help=f"Max relative crawl depth based on base_url (default: {DEFAULT_CRAWL_CONFIG['max_depth']})")
    parser.add_argument("--count", type=validate_count, default=DEFAULT_CRAWL_CONFIG["max_count"],
                        help=f"Max crawl file count (0 = unlimited, default: {DEFAULT_CRAWL_CONFIG['max_count']})")
    parser.add_argument("--picture", action="store_true", help="Crawl page pictures, save to MD same-level 'images/' dir")
    parser.add_argument("--video", action="store_true", help="Crawl page videos, save to MD same-level 'videos/' dir")
    
    # Parse CLI arguments
    args = parser.parse_args()
    
    # Determine local save directory (auto generate if omitted)
    save_dir = args.save_folder if args.save_folder else generate_auto_save_dir()
    os.makedirs(save_dir, exist_ok=True)
    print(f"📁 Local save directory created: {os.path.abspath(save_dir)}\n")
    
    # Initialize global config
    init_global_config(args.web_url, save_dir, args.depth, args.count, args.picture, args.video)
    
    # Start crawling
    print(f"\n🚀 Start Crawling (Base URL: {base_url} | Max Depth: {args.depth} | Max Count: {args.count})")
    print("-" * 80)
    try:
        crawl_page_recursive(args.web_url)
    except Exception as e:
        print(f"\n❌ Crawl aborted unexpectedly: {str(e)}")
        sys.exit(1)
    
    # Crawl completion statistics
    print("-" * 80)
    print(f"\n🎉 Crawl Task Completed!")
    print(f"📊 Statistics: Total crawled {crawled_count} valid pages")
    print(f"📂 All files saved to: {root_save_dir}")
    if crawl_picture or crawl_video:
        media_tips = []
        if crawl_picture: media_tips.append("Pictures (images/)")
        if crawl_video: media_tips.append("Videos (videos/)")
        print(f"📌 Crawled {'+'.join(media_tips)}, saved to MD same-level directories (no parent dir restriction)")
    print(f"\n💡 Tip: Open {root_save_dir} to view generated MD files and media resources")

if __name__ == "__main__":
    main()
