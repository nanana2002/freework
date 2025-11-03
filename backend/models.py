from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# 直接创建db实例，而不是从其他模块导入
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

class Conversation(db.Model):
    """对话列表模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # 对话标题（可从首条消息生成）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联的消息
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M'),
            'message_count': len(self.messages)
        }

class Message(db.Model):
    """单条消息模型"""
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' 或 'ai'
    content = db.Column(db.Text, nullable=False)     # 消息内容
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }