import os
import requests
import zipfile
from bs4 import BeautifulSoup
from config import Config
from google import genai
from google.genai import types
import html2text # New import
import pymupdf4llm # New import
import shutil # New import

# Configure OpenAI API
gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)

def download_file(url, stock_code):
    """Downloads a file (PDF/XBRL) to the data/downloads directory."""
    if not url:
        print("URL is empty, skipping download.")
        return None

    os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
    
    filename = os.path.basename(url)
    file_name = f"{stock_code}_{filename}"
    file_path = os.path.join(Config.DOWNLOAD_DIR, file_name)

    try:
        print(f"Attempting to download {url} to {file_path}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully downloaded {file_name}")
        return file_path
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return None



def extract_html_from_xbrl_zip(zip_path, dest_dir):
    """Extracts the main HTML file from an XBRL zip and returns its path."""
    try:
        # Create a unique subdirectory for extraction
        zip_filename_base = os.path.splitext(os.path.basename(zip_path))[0]
        extract_path = os.path.join(dest_dir, f"{zip_filename_base}_xbrl")
        os.makedirs(extract_path, exist_ok=True)

        main_html_file = None
        html_files = []

        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_path)
            
            # Find all HTML files
            for root, _, files in os.walk(extract_path):
                for file in files:
                    if file.lower().endswith(('.htm', '.html')):
                        html_files.append(os.path.join(root, file))

        if not html_files:
            print(f"No HTML files found in XBRL zip: {zip_path}")
            return None

        # Heuristic to find the main HTML file (e.g., _all.htm or largest)
        # Sort by size (descending) then by name (to prefer _all.htm/html)
        html_files.sort(key=lambda f: (os.path.getsize(f), f.lower().find('_all.htm')), reverse=True)
        
        main_html_file = html_files[0]
        print(f"Identified main HTML file: {main_html_file}")
        return main_html_file

    except Exception as e:
        print(f"XBRL HTML extraction failed: {e}")
        return None

def convert_pdf_to_markdown(pdf_path):
    """Converts PDF to Markdown using pymupdf4llm."""
    try:
        from pymupdf4llm import to_markdown
        md_content = to_markdown(pdf_path)
        return md_content
    except Exception as e:
        print(f"PDF to Markdown conversion failed: {e}")
        return None

def analyze_with_gemini(text_content, stock_code, title):
    """Sends extracted text to Gemini for analysis and returns the analysis result."""
    if not text_content:
        return "No content to analyze."

    prompt = f"""
    你是一位专业的金融分析师。请分析股票代码 {stock_code} 的公告："{title}"。
    
    请利用 Google Search 搜索该股票的最新新闻或未来即将发生的事件，结合以下公告文本进行综合分析。
    
    **要求：回答必须简短精炼，不要长篇大论。**
    
    请按以下格式回答：
    1. **核心结论**：[利好 / 利空 / 中性]
    2. **关键原因**：简述判断原因（结合公告内容和市场新闻）。
    3. **潜在风险**：一句话提示潜在风险。

    公告文本：
    {text_content}
    """

    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
            contents=prompt
        )
        return response.text if response.text else "Gemini analysis failed to return content."
    except Exception as e:
        print(f"Error during Gemini analysis: {e}")
        return f"Gemini analysis failed: {e}"

def download_and_parse(announcement):
    """Step 2: Downloads and processes the announcement file, converting to Markdown."""
    print(f"Downloading and processing: {announcement['title']}")
    
    # 1. Download
    file_path = download_file(announcement['url'], announcement['stock_code'])
    if not file_path:
        return {'status': 'failed', 'reason': 'Download error'}

    # Determine output Markdown file path
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    md_filename = f"{base_filename}.md"
    md_path = os.path.join(Config.DOWNLOAD_DIR, md_filename)

    # 2. Process based on file type and convert to Markdown
    markdown_content = None
    extracted_html_dir = None # To keep track of XBRL extraction directory for cleanup

    if file_path.lower().endswith('.zip') or 'xbrl' in announcement['url'].lower():
        # Handle XBRL: Extract HTML, then convert HTML to Markdown
        html_file_path = extract_html_from_xbrl_zip(file_path, Config.DOWNLOAD_DIR)
        if not html_file_path:
            return {'status': 'failed', 'reason': 'XBRL HTML extraction error'}
        
        extracted_html_dir = os.path.dirname(html_file_path) # Store dir for cleanup
        
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            markdown_content = html2text.html2text(html_content)
        except Exception as e:
            print(f"HTML to Markdown conversion failed for XBRL: {e}")
            return {'status': 'failed', 'reason': f"XBRL HTML to Markdown conversion error: {e}"}
            
    elif file_path.lower().endswith('.pdf'):
        # Handle PDF: Convert PDF to Markdown
        try:
            markdown_content = convert_pdf_to_markdown(file_path)
        except Exception as e:
            print(f"PDF to Markdown conversion failed: {e}")
            return {'status': 'failed', 'reason': f"PDF to Markdown conversion error: {e}"}
    else:
        return {'status': 'failed', 'reason': 'Unsupported file type for Markdown conversion'}

    if not markdown_content:
        return {'status': 'failed', 'reason': 'Markdown conversion yielded empty content.'}

    # 3. Save Markdown Locally
    os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    # Optional: Clean up temporary extracted HTML directory for XBRL
    if extracted_html_dir and os.path.exists(extracted_html_dir):
        try:
            shutil.rmtree(extracted_html_dir)
            print(f"Cleaned up temporary XBRL HTML directory: {extracted_html_dir}")
        except Exception as e:
            print(f"Error cleaning up XBRL HTML directory {extracted_html_dir}: {e}")
            
    return {'status': 'success', 'text_path': md_path, 'preview': markdown_content[:500]}

def analyze_saved_text(text_path, stock_code, title, provider='openai'):
    """Step 3: Reads local text file and sends to Gemini."""
    try:
        with open(text_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        # Check for empty or very short text (parsing failure)
        if len(text_content.strip()) < 50:
            return {'status': 'failed', 'reason': 'Parsed text is empty or too short. Please view original file.'}
            
        # Check for garbled text (heuristic: high percentage of replacement characters)
        if text_content.count('\ufffd') > len(text_content) * 0.05:
            return {'status': 'failed', 'reason': 'Parsed text appears garbled. Please view original file.'}
            
        analysis = analyze_with_gemini(text_content, stock_code, title)
        return {'status': 'success', 'analysis': analysis}
    except Exception as e:
        return {'status': 'failed', 'reason': str(e)}
