import requests
from bs4 import BeautifulSoup
from datetime import datetime
from config import Config
import time
import urllib.parse

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

def fetch_all_tdnet_pages(target_date=None):
    """Fetches all pages of TDnet announcements for the specified date."""
    all_html_content = ""
    page_num = 1
    
    while True:
        if target_date:
            date_str = target_date.strftime("%Y%m%d")
        else:
            date_str = datetime.now().strftime("%Y%m%d")
        
        # Modify the URL to include the page number
        url = f"{Config.TDNET_BASE_URL}I_list_001_{date_str}.html"
        if page_num > 1:
            url = f"{Config.TDNET_BASE_URL}I_list_001D_{date_str}_{page_num}.html" #Note the D
        
        try:
            print(f"Attempting to fetch TDnet page {page_num}: {url}")
            response = requests.get(url, timeout=10)

            if response.status_code == 404:
                print(f"Page {page_num} not found. Assuming end of pages.")
                break  # No more pages

            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            # Check for no announcements on page
            if "There is no file matching your search conditions" in response.text:
                print(f"No announcements found on page {page_num}. Assuming end of pages.")
                break

            all_html_content += response.text
            page_num += 1

        except requests.exceptions.RequestException as e:
            print(f"Error fetching TDnet page {page_num}: {e}")
            break  # Stop fetching on error

    return all_html_content


    except requests.exceptions.RequestException as e:
        print(f"Error fetching TDnet page: {e}")
        return None

def parse_announcements(html_content, stock_codes, keywords, target_date=None):
    """Parses HTML content to extract announcements."""
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
            # Extract basic info (Adjust indices based on actual TDnet table layout)
            # Usually: 0:Time, 1:Code, 2:Name, 3:Title, 4+:Links
            time_str = cols[0].get_text(strip=True)
            
            if target_date:
                time_str = f"{target_date.strftime('%Y-%m-%d')} {time_str}"

            code_raw = cols[1].get_text(strip=True)
            company_name = cols[2].get_text(strip=True)
            title = cols[3].get_text(strip=True)
            
            # Clean stock code (sometimes has suffix)
            stock_code = code_raw[:4]
            
            # Check filters
            # If stock_codes is empty, we might want to return everything, but usually we filter.
            # If keywords is empty, we ignore keyword filtering.
            is_target_stock = (not stock_codes) or (stock_code in stock_codes)
            is_target_keyword = (not keywords) or any(k in title for k in keywords)
            
            if is_target_stock and is_target_keyword:
                # Extract URLs
                pdf_url = None
                xbrl_url = None
                
                # Look for links in the row
                links = row.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    full_url = Config.TDNET_BASE_URL + href if not href.startswith('http') else href
                    
                    if 'pdf' in href.lower():
                        pdf_url = full_url
                    elif 'xbrl' in href.lower() or 'zip' in href.lower():
                        xbrl_url = full_url

                # Prioritize XBRL if available, else PDF
                target_url = xbrl_url if xbrl_url else pdf_url
                
                if target_url:
                    announcements.append({
                        'time': time_str,
                        'title': title,
                        'url': target_url,
                        'stock_code': stock_code,
                        'company': company_name,
                        'date': datetime.now().isoformat(), # Using fetch time as approx
                        'type': 'XBRL' if xbrl_url else 'PDF'
                    })
                    
        except Exception as e:
            print(f"Error parsing row: {e}")
            continue

    return announcements

if __name__ == '__main__':
    # Example usage (for testing the scraper)
    print("Fetching TDnet page...")
    html = fetch_all_tdnet_pages()
    filtered_announcements = parse_announcements(html, Config.TARGET_STOCK_CODES, Config.ANNOUNCEMENT_KEYWORDS)
    print(f"Found {len(filtered_announcements)} relevant announcements:")
    for ann in filtered_announcements:
        print(ann)