import requests
from bs4 import BeautifulSoup
from datetime import datetime
from config import Config
import time

def fetch_tdnet_search_page(keyword=None, stock_code=None, page=1):
    """
    利用 TDnet 站点的搜索功能获取公告（支持按关键字和股票代码）。
    该方法可以跨日期搜索，而不仅限于当天的列表。
    """
    url = f"{Config.TDNET_BASE_URL}I_list_00.html" # TDnet 搜索和分页通用端点
    
    params = {
        'page': page,
        'Sort': 1 # 1: 按时间倒序（最新优先）
    }
    
    if stock_code:
        params['Sccode'] = stock_code
    if keyword:
        # 依据 TDnet 实际支持的表单字段，这里假定为 keyword（也有可能是 searchWord 或 q）
        params['keyword'] = keyword
        
    print(f"Attempting to fetch TDnet search page: {url} with params {params}")
    try:
        # 某些搜索表单可能严格要求使用 POST 请求。如果发现 GET 拿不到预期的结果，
        # 可修改为: response = requests.post(url, data=params, timeout=10)
        response = requests.get(url, params=params, timeout=10)
        print("response_code=${response.status_code}")
        if response.status_code == 404:
            print("Search page not found.")
            return None
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching TDnet search page: {e}")
        return None

def fetch_tdnet_page(target_date=None):
    """Fetches the TDnet announcement page for the specific date."""
    # TDnet URL format: https://www.release.tdnet.info/inbs/I_list_001_YYYYMMDD.html
    if target_date:
        date_str = target_date.strftime("%Y%m%d")
    else:
        date_str = datetime.now().strftime("%Y%m%d")
        
    url = f"{Config.TDNET_BASE_URL}I_list_001_{date_str}.html"
    try:
        print(f"Attempting to fetch TDnet page: {url}")
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            print("Page not found (might be weekend or holiday).")
            return None
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        response.encoding = response.apparent_encoding
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching TDnet page: {e}")
        return None

def fetch_all_daily_tdnet_pages(target_date=None):
    """
    Fetches all pages of TDnet announcements for a specific date by iterating through page numbers.
    e.g., I_list_001_YYYYMMDD.html, I_list_002_YYYYMMDD.html, ...
    """
    all_html_content = ""
    page_num = 1
    
    if target_date:
        date_str = target_date.strftime("%Y%m%d")
    else:
        date_str = datetime.now().strftime("%Y%m%d")

    while True:
        # URL format for daily list pages: I_list_001_YYYYMMDD.html, I_list_002_YYYYMMDD.html, etc.
        page_str = f"{page_num:03d}" # Formats 1 as 001, 2 as 002
        url = f"{Config.TDNET_BASE_URL}I_list_{page_str}_{date_str}.html"
        
        try:
            print(f"Attempting to fetch TDnet page {page_num}: {url}")
            response = requests.get(url, timeout=10)

            if response.status_code == 404:
                print(f"Page {page_num} not found. Assuming end of pages.")
                break

            response.raise_for_status()
            response.encoding = response.apparent_encoding
            all_html_content += response.text
            page_num += 1
            
            if page_num > 50: # Safety break to avoid infinite loops
                print("Warning: Reached page 50, breaking loop.")
                break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching TDnet page {page_num}: {e}")
            break
    return all_html_content

def parse_announcements(html_content, stock_codes, keywords, target_date=None):
    """Parses HTML content to extract announcements."""
    stock_code_num = len(stock_codes)
    stock_code_has = stock_code_num > 0
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    announcements = []
    
    # TDnet usually has a main table. We look for rows <tr>.
    rows = soup.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 4:
            continue
            
        try:
            # TDnet 的表格结构会因为“当日列表”还是“搜索结果”而有所不同：
            # 当日列表 (5列): 时间 | 代码 | 公司名称 | 标题 | 文档链接
            # 搜索结果 (6列以上): 日期 | 时间 | 代码 | 公司名称 | 标题 | 文档链接
            if len(cols) == 5:
                # continue
                time_str = cols[0].get_text(strip=True)
                if target_date:
                    time_str = f"{target_date.strftime('%Y-%m-%d')} {time_str}"
                code_raw = cols[1].get_text(strip=True)
                company_name = cols[2].get_text(strip=True)
                title = cols[3].get_text(strip=True)
            elif len(cols) >= 6:
                time_str = cols[0].get_text(strip=True)
                # time_str = f"{date_str} {cols[0].get_text(strip=True)}"
                if time_str:
                    time_str = f"{target_date.strftime('%Y-%m-%d')} {time_str}"
                code_raw = cols[1].get_text(strip=True)
                company_name = cols[2].get_text(strip=True)
                title = cols[3].get_text(strip=True)
            else:
                continue
                
            # 彻底过滤掉底部分页导航行（"101～200件 / 全375件前へ1234次へ"）
            if "件 / 全" in title or "次へ" in title or "前へ" in title:
                continue
            
            # Clean stock code (sometimes has suffix)
            stock_code = code_raw[:4]
            
            # 严格校验股票代码：前3位必须是数字 (支持 130A 等新版代码，同时过滤异常字符)
            if len(stock_code) != 4 or not stock_code[:3].isdigit():
                continue
            
            # Check filters
            # If stock_codes is empty, we might want to return everything, but usually we filter.
            # If keywords is empty, we ignore keyword filtering.
            is_target_stock = (not stock_codes) or (stock_code in stock_codes)
            is_target_keyword = (not keywords) or any(k in title for k in keywords)
            
            
            if is_target_stock and is_target_keyword:
                if stock_code_has:
                    print("have code")
                    if stock_code_num <= 0 :
                        break
                    stock_code_num = stock_code_num - 1
                
                # Extract URLs
                pdf_url = None
                xbrl_url = None
                fallback_url = None
                
                # 扩大搜索范围：直接在整行(row)中寻找所有的 <a> 标签，防止漏掉包裹在标题里的链接
                links = row.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    if href.startswith('javascript'):
                        continue
                        
                    full_url = Config.TDNET_BASE_URL + href if not href.startswith('http') else href
                    
                    if 'pdf' in href.lower():
                        pdf_url = full_url
                    elif 'xbrl' in href.lower() or 'zip' in href.lower():
                        xbrl_url = full_url
                    elif not fallback_url:
                        fallback_url = full_url

                # Prioritize XBRL if available, else PDF, 否则使用其他有效链接作为保底
                target_url = xbrl_url or pdf_url or fallback_url
                
                if target_url:
                    announcements.append({
                        'time': time_str,
                        'title': title,
                        'url': target_url,
                        'stock_code': stock_code,
                        'company': company_name,
                        'date': datetime.now().isoformat(), # Using fetch time as approx
                        'type': 'XBRL' if xbrl_url else ('PDF' if pdf_url else 'OTHER')
                    })
                    
        except Exception as e:
            print(f"Error parsing row: {e}")
            continue

    return announcements

if __name__ == '__main__':
    # Example usage (for testing the scraper)
    print("Fetching TDnet search page...")
    
    test_code = Config.TARGET_STOCK_CODES[0] if Config.TARGET_STOCK_CODES else "7203"
    test_keyword = Config.ANNOUNCEMENT_KEYWORDS[0] if Config.ANNOUNCEMENT_KEYWORDS else "上方修正"
    
    html = fetch_tdnet_search_page(keyword=test_keyword, stock_code=test_code)
    filtered_announcements = parse_announcements(html, [test_code], [test_keyword])
    
    print(f"Found {len(filtered_announcements)} relevant announcements:")
    for ann in filtered_announcements:
        print(ann)