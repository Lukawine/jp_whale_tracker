

import dashscope
from dashscope.api_entities.dashscope_response import Message # Specific import for Message object


import os
import requests
import zipfile
from bs4 import BeautifulSoup
from config import Config
import html2text # New import
import pymupdf4llm # New import
import shutil # New import

from dashscope.api_entities.dashscope_response import Message # Specific import for Message object

# dashscope.api_key = config.QWEN_API_KEY


# Configure AI API Keys
_dashscope_initialized = False # Initialize lazily


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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1', # Do Not Track
            'Connection': 'close', # 关键：阿里云上建议设为 close，防止连接池被封锁
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.release.tdnet.info/inbs/I_main_00.html' # 必须带上来源页
        }
        response = requests.get(url,headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                f.write(chunk)
        print(f"Successfully downloaded {file_name}")
        return file_path
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 还是断开连接? 尝试换成单次请求模式...")
        # 如果 Session 模式还是不行，改用单次调用
        resp = requests.get(url, headers=headers, timeout=20)
        with open(file_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024*1024):
                f.write(chunk)
        print(f"Successfully downloaded {file_name}")
        return file_path



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


def analyze_with_ai(text_content, stock_code, title):
    """Sends extracted text to AI (Qwen) for analysis and returns the analysis result."""
    global _dashscope_initialized
    if not _dashscope_initialized:
        dashscope.api_key = Config.QWEN_API_KEY
        _dashscope_initialized = True
    
    if not text_content:
        return "No content to analyze."
    
    print(f"DEBUG: text_content length for Qwen: {len(text_content)}")
    print(f"DEBUG: Using detailed analysis prompt for Qwen.")

    prompt = f"""
    你是一位专业的金融分析师。请对股票代码 {stock_code} 的公告："{title}" 进行深入分析。
    
    请充分利用你的知识和对市场数据的理解，结合以下公告文本进行综合分析。
    
    **要求：回答必须专业、客观，结构清晰，简明扼要，避免长篇大论。**
    
    请严格按照以下维度和格式进行分析，每个维度使用Markdown标题，并在每个维度下进行简洁的总结和判断：
    
    ### 核心结论
    [利好 / 利空 / 中性]
    
    ### 业绩质量
    - 净利润增长中有多少比例来自主营业务，有多少来自非经常性损益（如卖资产）？
    - 请根据公告内容，量化或定性说明其构成。
    
    ### 预期差
    - 分析市场是否已经消化了这份利好？请基于你可获取到的信息，评估市场对公告的反应是超预期，符合预期，还是不及预期？
    
    ### 风险预警
    - 文中是否有关于‘现金流’或‘成本增加’的负面措辞？请具体指出并评估其潜在影响。
    - 还有其他值得关注的潜在风险点吗？
    
    ### 未来预测
    - 根据管理层的描述（若有），下一季度的核心增长点在哪里？
    - 还有其他可以预期的发展方向吗？
    
    ---
    
    公告文本：
    {text_content[:4000]} # Increase limit for more detailed analysis
    """
    
    try:
        messages = [
            Message(role='system', content='You are a helpful assistant.'),
            Message(role='user', content=prompt)
        ]
        
        # Use Qwen-turbo as a general purpose model. Adjust as needed.
        response = dashscope.Generation.call(
            model='qwen-turbo', 
            messages=messages,
            # tool_choice='auto' # Enable tool calling if Qwen model supports it and prompt is updated
            # tools=[{'type': 'function', 'function': {'name': 'google_search', 'description': 'Searches Google for information', 'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}}}}}]
        )

        if response.status_code == 200:
            if response.output and len(response.output) > 0:
                return response.output.text
            else:
                print(f"Qwen analysis failed: No choices in response. Full response: {response}")
                return f"Qwen analysis failed: No content or choices in response. Status: {response.status_code}"
        else:
            print(f"Qwen API call failed. Status: {response.status_code}, Code: {response.code}, Message: {response.message}. Full response: {response}")
            return f"Qwen analysis failed: {response.code} - {response.message}"
    except Exception as e:
        print(f"Error during Qwen analysis: {e}")
        return f"Qwen analysis failed: {e}"



def analyze_saved_text(text_path, stock_code, title):
    """Step 3: Reads local text file and sends to specified AI for analysis."""
    try:
        with open(text_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
            
        
        # Check for empty or very short text (parsing failure)
        if len(text_content.strip()) < 50:
            return {'status': 'failed', 'reason': 'Parsed text is empty or too short. Please view original file.'}
            
        # Check for garbled text (heuristic: high percentage of replacement characters)
        if text_content.count('\ufffd') > len(text_content) * 0.05:
            return {'status': 'failed', 'reason': 'Parsed text appears garbled. Please view original file.'}
        
        print("====text_content:",text_content);
        analysis_result = analyze_with_ai(text_content, stock_code, title)
        # analyze_with_ai returns a string directly, so wrap it in success status
        if isinstance(analysis_result, str) and not analysis_result.startswith("Error"):
             return {'status': 'success', 'analysis': analysis_result}
        else: # Handle cases where analyze_with_ai returns an error string or dict
            if isinstance(analysis_result, dict) and analysis_result.get('status') == 'failed':
                return analysis_result
            return {'status': 'failed', 'reason': analysis_result} # Default error if string
    except Exception as e:
        return {'status': 'failed', 'reason': str(e)}
