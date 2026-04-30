from flask import Flask, jsonify, request, send_from_directory, render_template
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import time
import threading
import logging
from flask_apscheduler import APScheduler
from sqlalchemy import text, inspect

from config import Config # fixed
from models import db, Announcement, StockCode
from tdnet_scraper import fetch_tdnet_page, parse_announcements,fetch_all_daily_tdnet_pages
import announcement_processor # fixed
from grading_system import grader # Import the new module

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Extensions
db.init_app(app)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with app.app_context():
    db.create_all()

    # 自动迁移：检查并添加缺失的列 (analysis_time, grade, score)
    inspector = inspect(db.engine)
    if 'announcement' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('announcement')]
        with db.engine.connect() as conn:
            if 'analysis_time' not in existing_columns:
                logger.info("Migrating database: Adding analysis_time column...")
                conn.execute(text("ALTER TABLE announcement ADD COLUMN analysis_time DATETIME"))
            if 'grade' not in existing_columns:
                logger.info("Migrating database: Adding grade and score columns...")
                conn.execute(text("ALTER TABLE announcement ADD COLUMN grade VARCHAR(5)"))
                conn.execute(text("ALTER TABLE announcement ADD COLUMN score INTEGER"))
            if 'reason' not in existing_columns:
                logger.info("Migrating database: Adding reason column...")
                conn.execute(text("ALTER TABLE announcement ADD COLUMN reason VARCHAR(500)"))
            conn.commit()

# --- Scheduled Task ---
@scheduler.task('cron', id='scrape_tdnet', hour='8-22', minute='*/5')
def scheduled_scraping_job():
    """Runs every 5 minutes between 08:00 and 22:00."""
    with app.app_context():
        logger.info("Starting scheduled scraping job...")
        
        # 1. Get Stock Codes
        stocks = StockCode.query.all()
        if not stocks:
            logger.info("No stock codes to monitor.")
            return
        stock_codes = [s.code for s in stocks]
        
        # 2. Scrape (Today)
        current_date = datetime.now()
        # html_content = fetch_all_tdnet_pages(current_date)
        html_content = fetch_tdnet_page(current_date)
        
        
        # html_content = tdnet_scraper.fetch_all_tdnet_pages(current_date)
        if not html_content:
            return
            
        found_announcements = parse_announcements(html_content, stock_codes, Config.ANNOUNCEMENT_KEYWORDS, current_date)
        
        # 3. Process New Announcements
        for ann_data in found_announcements:
            # Check if exists
            exists = Announcement.query.filter_by(url=ann_data['url']).first()
            if not exists:
                logger.info(f"New announcement found: {ann_data['title']}")
                
                # Apply Auto-Grading
                grading_result = grader.calculate_grade(ann_data['stock_code'], ann_data['title'])
                
                new_ann = Announcement(
                    url=ann_data['url'],
                    time=ann_data['time'],
                    stock_code=ann_data['stock_code'],
                    company_name=ann_data['company'],
                    title=ann_data['title'],
                    doc_type=ann_data['type'],
                    grade=grading_result['grade'],
                    score=grading_result['score'],
                    reason=grading_result['reason']
                )
                db.session.add(new_ann)
                db.session.commit()
                
                # Auto-Process (Download & Analyze)
                process_announcement(new_ann.id)

def process_announcement(ann_id):
    """Downloads and analyzes a specific announcement."""
    ann = Announcement.query.get(ann_id)
    if not ann:
        return
    
    # Mock dictionary for existing processor function
    ann_dict = {
        'url': ann.url,
        'stock_code': ann.stock_code,
        'title': ann.title
    }
    
    # 1. Download & Parse
    dl_result = announcement_processor.download_and_parse(ann_dict)
    if dl_result['status'] == 'success':
        ann.is_downloaded = True
        ann.local_path = dl_result['text_path'] # Renamed 'text_path' to be generic file path

        # Read Markdown content for DB storage
        if ann.local_path.lower().endswith('.md'): # Expecting a .md file now
            try:
                with open(ann.local_path, 'r', encoding='utf-8') as f:
                    ann.extracted_text = f.read()
                
                # Noise Filtering (Text Content)
                if grader.check_noise(ann.extracted_text):
                    ann.grade = 'D'
                    ann.score = 30
                    logger.info(f"Downgraded announcement {ann.id} to D due to noise keywords in text.")
            except Exception as e:
                ann.extracted_text = f"Error reading local Markdown file: {e}"
                logger.error(f"Error reading local Markdown file for ann {ann.id}: {e}")
        else:
            ann.extracted_text = "Unsupported file type for extracted_text storage."
            logger.warning(f"Unsupported file type for extracted_text storage for ann {ann.id}: {ann.local_path}")

        # 2. Analyze
        an_result = announcement_processor.analyze_saved_text(ann.local_path, ann.stock_code, ann.title)
        if an_result['status'] == 'success':
            ann.gemini_analysis = an_result['analysis']
            ann.analysis_time = datetime.now()
            ann.analysis_status = 'success'
        else:
            ann.analysis_status = 'failed'
            ann.error_message = an_result.get('reason')
    else:
        ann.analysis_status = 'failed'
        ann.error_message = dl_result.get('reason')
    
    db.session.commit()

# 1. Search Endpoint
@app.route('/api/announcements', methods=['GET'])
def get_announcements():
    # Simple fetch all for now, can add pagination/filtering
    anns = Announcement.query.order_by(Announcement.time.desc()).all()
    return jsonify({'status': 'success', 'announcements': [a.to_dict() for a in anns]})

# 2. Stock Management Endpoints
@app.route('/api/stocks', methods=['GET', 'POST', 'DELETE'])
def manage_stocks():
    if request.method == 'GET':
        stocks = StockCode.query.all()
        return jsonify([s.code for s in stocks])
    
    elif request.method == 'POST':
        data = request.json
        codes = data.get('codes', [])
        added = 0
        for code in codes:
            if not StockCode.query.get(code):
                db.session.add(StockCode(code=code))
                added += 1
        db.session.commit()
        return jsonify({'status': 'success', 'added': added})
        
    elif request.method == 'DELETE':
        data = request.json
        codes = data.get('codes', [])
        for code in codes:
            stock = StockCode.query.get(code)
            if stock:
                db.session.delete(stock)
        db.session.commit()
        return jsonify({'status': 'success'})

# 3. Manual Trigger (Optional)
@app.route('/api/trigger_scrape', methods=['POST'])
def trigger_scrape():
    scheduled_scraping_job()
    return jsonify({'status': 'triggered'})

# 4. Search Endpoint
@app.route('/api/search', methods=['POST'])
def search_announcements():
    data = request.json
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    codes_str = data.get('codes', '')
    target_codes = [c.strip() for c in codes_str.split(',') if c.strip()]
    
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return jsonify({'status': 'failed', 'message': 'Invalid date format'}), 400

    found_announcements = []
    current_date = start_date
    while current_date <= end_date:
        # html_content = fetch_all_tdnet_pages(current_date)
        # html_content = fetch_tdnet_page(current_date)
        html_content = fetch_all_daily_tdnet_pages(current_date)
        if html_content:
            anns = parse_announcements(html_content, target_codes, Config.ANNOUNCEMENT_KEYWORDS, current_date)
            # 如果没有按照code搜索，去掉第一行
            if len(target_codes) <= 0:
                anns.pop(0);
                
            for ann_data in anns:
                existing = Announcement.query.filter_by(url=ann_data['url']).first()
                if not existing:
                    # Apply Auto-Grading for manual search results too
                    grading_result = grader.calculate_grade(ann_data['stock_code'], ann_data['title'])
                    
                    new_ann = Announcement(
                        url=ann_data['url'],
                        time=ann_data['time'],
                        stock_code = ann_data['stock_code'],
                        company_name=ann_data['company'],
                        title=ann_data['title'],
                        doc_type=ann_data['type'],
                        grade=grading_result['grade'],
                        score=grading_result['score']
                    )
                    db.session.add(new_ann)
                    db.session.flush()
                    found_announcements.append(new_ann.to_dict())
                else:
                    found_announcements.append(existing.to_dict())    
        current_date += timedelta(days=1)

    return jsonify({'status': 'success', 'announcements': found_announcements})

# 5. Download Endpoint
@app.route('/api/download', methods=['POST'])
def download_endpoint():
    ann_data = request.json
    result = announcement_processor.download_and_parse(ann_data)
    if result['status'] == 'success':
        ann = Announcement.query.filter_by(url=ann_data['url']).first()
        if ann:
            ann.is_downloaded = True
            ann.local_path = result['text_path'] # Renamed from text_path to generic file_path
            # Read Markdown content for DB storage
            if ann.local_path.lower().endswith('.md'): # Expecting a .md file now
                try:
                    with open(ann.local_path, 'r', encoding='utf-8') as f:
                        ann.extracted_text = f.read()
                    
                    # Noise Filtering (Text Content)
                    if grader.check_noise(ann.extracted_text):
                        ann.grade = 'D'
                        ann.score = 30
                except Exception as e:
                    ann.extracted_text = f"Error reading local Markdown file: {e}"
                    logger.error(f"Error reading local Markdown file for ann {ann.url}: {e}")
            else:
                ann.extracted_text = "Unsupported file type for extracted_text storage."
                logger.warning(f"Unsupported file type for extracted_text storage for ann {ann.url}: {ann.local_path}")
            db.session.commit()
    return jsonify(result)

# 6. Analyze Endpoint
@app.route('/api/analyze', methods=['POST'])
def analyze_endpoint():
    data = request.json
    url = data.get('url')
    force_refresh = data.get('force', False)
    provider = data.get('provider', 'gemini') # Default to gemini if not provided
    # Check DB for existing analysis. If no force_refresh, use cached result.
    ann = Announcement.query.filter_by(url=url).first()
    
    # For now, we'll store all AI analysis in ann.gemini_analysis for simplicity,
    # and reuse if force_refresh is False. A more robust solution might use
    # separate fields or a JSON field to track analysis per provider.
    if ann and ann.gemini_analysis and ann.analysis_status == 'success' and not force_refresh:
        return jsonify({
            'status': 'success', 
            'analysis': ann.gemini_analysis,
            'analysis_time': ann.analysis_time.strftime("%Y-%m-%d %H:%M:%S") if ann.analysis_time else None,
            'cached': True,
            'provider_used': 'cached' # Indicate cached analysis
        })

    # Perform Analysis
    result = announcement_processor.analyze_saved_text(data.get('text_path'), data.get('stock_code'), data.get('title'))
    
    if result['status'] == 'success' and ann:
        ann.gemini_analysis = result['analysis'] # Store analysis, regardless of provider
        ann.analysis_time = datetime.now()
        ann.analysis_status = 'success'
        db.session.commit()
        result['analysis_time'] = ann.analysis_time.strftime("%Y-%m-%d %H:%M:%S")
        result['provider_used'] = provider # Indicate which provider was used for fresh analysis
        
    return jsonify(result)

# 7. Get File Endpoint (for opening in new tab)
@app.route('/api/get_file', methods=['GET'])
def get_file_endpoint():
    file_path = request.args.get('file_path')
    
    if not file_path:
        return jsonify({'status': 'failed', 'message': 'file_path is required'}), 400

    # Ensure the path is within the allowed download directory for security
    absolute_path = os.path.abspath(file_path)
    download_dir_abs = os.path.abspath(Config.DOWNLOAD_DIR)

    if not absolute_path.startswith(download_dir_abs):
        return jsonify({'status': 'failed', 'message': 'Access denied: Path outside allowed directory'}), 403

    try:
        # Extract directory and filename for send_from_directory
        directory = os.path.dirname(absolute_path)
        filename = os.path.basename(absolute_path)
        # send_from_directory will automatically infer mimetype
        return send_from_directory(directory, filename, as_attachment=False)
    except FileNotFoundError:
        return jsonify({'status': 'failed', 'message': 'File not found'}), 404
    except Exception as e:
        return jsonify({'status': 'failed', 'message': f'Error serving file: {str(e)}'}), 500

@app.route('/')
def index():
    anns = Announcement.query.order_by(Announcement.time.desc()).all()
    return render_template('index.html', announcements=[a.to_dict() for a in anns])

if __name__ == '__main__':
    if threading.current_thread() is threading.main_thread():
        # 移除这行
        # app.run(debug=True, port=5000)
        app.run(debug=True, port=5000)