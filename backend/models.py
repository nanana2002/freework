from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class PDFBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)  # 存储后端实际的文件名
    file_type = db.Column(db.String(10), default='pdf')   # ✅ 新增：文件类型 (pdf/txt)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'date': self.upload_date.strftime('%Y-%m-%d'),
            'file_path': self.file_path,
            'file_type': self.file_type  # ✅ 返回 file_type
        }

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }