from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class StockCode(db.Model):
    code = db.Column(db.String(10), primary_key=True)
    added_at = db.Column(db.DateTime, default=datetime.now)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), unique=True, nullable=False)
    time = db.Column(db.String(50))
    stock_code = db.Column(db.String(20))
    company_name = db.Column(db.String(100))
    title = db.Column(db.String(200))
    doc_type = db.Column(db.String(20))
    
    # Processing Status
    fetched_at = db.Column(db.DateTime, default=datetime.now)
    is_downloaded = db.Column(db.Boolean, default=False)
    local_path = db.Column(db.String(500))
    
    # Auto-Grading
    grade = db.Column(db.String(5)) # S, A, C, D, E
    score = db.Column(db.Integer)   # 0-100
    
    # Analysis
    extracted_text = db.Column(db.Text) # Original text for "Intent Battle"
    gemini_analysis = db.Column(db.Text) # Analysis result
    analysis_status = db.Column(db.String(20), default='pending') # pending, success, failed
    analysis_time = db.Column(db.DateTime)
    error_message = db.Column(db.String(500))

    def to_dict(self):
        return {
            'id': self.id,
            'time': self.time,
            'stock_code': self.stock_code,
            'company': self.company_name,
            'title': self.title,
            'url': self.url,
            'type': self.doc_type,
            'is_downloaded': self.is_downloaded,
            'local_path': self.local_path,
            'analysis': self.gemini_analysis,
            'original_text': self.extracted_text,
            'status': self.analysis_status,
            'analysis_time': self.analysis_time.strftime("%Y-%m-%d %H:%M:%S") if self.analysis_time else None,
            'grade': self.grade,
            'score': self.score
        }
