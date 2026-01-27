import os
import requests
import zipfile
from bs4 import BeautifulSoup
from config import Config
from google import genai
from google.genai import types

# Configure Gemini API
client = genai.Client(api_key=Config.GEMINI_API_KEY)

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

def extract_text_from_xbrl_zip(zip_path):
    """Extracts text from XBRL zip file (TDnet format)."""
    try:
        text_content = ""
        with zipfile.ZipFile(zip_path, 'r') as z:
            # TDnet XBRL zips usually contain .xbrl or .htm files in a folder
            target_files = [f for f in z.namelist() if f.endswith('.htm') or f.endswith('.xbrl')]
            target_files.sort(key=lambda x: len(x)) 
            
            for filename in target_files:
                with z.open(filename) as f:
                    content = f.read()
                    soup = BeautifulSoup(content, 'lxml') 
                    text_content += soup.get_text(separator='\n', strip=True) + "\n\n"
                    
        return text_content[:50000] 
    except Exception as e:
        print(f"XBRL extraction failed: {e}")
        return None

def extract_text_from_pdf(pdf_path):
    """Extracts text from PDF using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text[:50000]
    except Exception as e:
        print(f"PDF extraction failed: {e}")
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
        response = client.models.generate_content(
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
    """Step 2: Downloads and extracts text, saving it locally."""
    print(f"Downloading and parsing: {announcement['title']}")
    
    # 1. Download
    file_path = download_file(announcement['url'], announcement['stock_code'])
    if not file_path:
        return {'status': 'failed', 'reason': 'Download error'}

    # 2. Extract Text
    extracted_text = ""
    if file_path.lower().endswith('.zip') or 'xbrl' in announcement['url'].lower():
        extracted_text = extract_text_from_xbrl_zip(file_path)
    elif file_path.lower().endswith('.pdf'):
        extracted_text = extract_text_from_pdf(file_path)
    
    if not extracted_text:
        return {'status': 'failed', 'reason': 'Text extraction error'}

    # 3. Save Text Locally
    os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
    text_filename = f"{os.path.basename(file_path)}.txt"
    text_path = os.path.join(Config.DOWNLOAD_DIR, text_filename)
    
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(extracted_text)
        
    return {'status': 'success', 'text_path': text_path, 'preview': extracted_text[:500]}

def analyze_saved_text(text_path, stock_code, title):
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
