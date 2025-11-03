from flask import Flask, request, jsonify, send_from_directory, render_template, send_file, abort
import os
import uuid
from datetime import datetime
import jwt
from functools import wraps
import requests
from dotenv import load_dotenv
from .models import db, PDFBook # 导入更新后的模型
import time # 导入 time 模块用于时间戳
import codecs
from .models import db, PDFBook, Bookmark  # 导入新模型

# 加载环境变量
load_dotenv() 

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 初始化 Flask 应用，指定模板和静态文件目录
app = Flask(
    __name__,
    template_folder=os.path.join(current_dir, 'templates'),
    static_folder=os.path.join(current_dir, 'static')
)
# 配置
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['PDF_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'pdfs')
app.config['IMAGE_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'images')
app.config['SECRET_KEY'] = 'your-secret-key-here' 

# 创建上传目录
os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)
os.makedirs(app.config['IMAGE_FOLDER'], exist_ok=True)

# 初始化数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///freework.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# 上传文档接口 (支持 PDF/TXT)
# 修改上传文档接口
@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未找到文件'})
    
    file = request.files['file']
    title = request.form.get('title', '未命名文档')
    
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'})
    
    file_ext = file.filename.rsplit('.', 1)[-1].lower()
    file_type = file_ext
    
    if file_type not in ['pdf', 'txt']:
        return jsonify({'success': False, 'error': '文件格式错误，仅支持PDF和TXT'})
        
    # 构造文件名（保持不变）
    safe_title = ''.join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    if not safe_title:
        safe_title = 'untitled'
        
    filename = f"{safe_title}_{int(time.time())}.{file_ext}"
    file_path = os.path.join(app.config['PDF_FOLDER'], filename)
    
    try:
        # 针对TXT文件进行编码处理
        if file_type == 'txt':
            # 获取前端传递的编码方式，默认UTF-8
            encoding = request.form.get('encoding', 'utf-8')
            # 读取文件内容并转换为UTF-8编码保存
            content = file.read()
            # 尝试用指定编码解码
            try:
                text = content.decode(encoding)
            except UnicodeDecodeError:
                # 如果解码失败，尝试使用utf-8并忽略错误
                text = content.decode('utf-8', errors='ignore')
            
            # 以UTF-8编码写入文件
            with codecs.open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
        else:
            # PDF文件直接保存
            file.save(file_path)
    except Exception as e:
        app.logger.error(f'文件保存失败: {str(e)}')
        return jsonify({'success': False, 'error': f'文件保存失败: {str(e)}'})
    
    relative_path = filename 
    
    new_book = PDFBook(title=title, file_path=relative_path, file_type=file_type)
    db.session.add(new_book)
    db.session.commit()
    
    return jsonify({'success': True, 'book': new_book.to_dict()})


# 获取文档文件接口
@app.route('/uploads/pdfs/<path:filename>')
def uploaded_pdf(filename):
    # Flask 自动处理 URL 解码，我们只需要提供正确的文件目录
    return send_from_directory(app.config['PDF_FOLDER'], filename)

# 获取所有文档列表
@app.route('/api/get-pdfs', methods=['GET'])
def get_pdfs():
    books = PDFBook.query.all()
    return jsonify({'books': [book.to_dict() for book in books]})

# 删除文档
@app.route('/api/delete-pdf/<int:book_id>', methods=['DELETE'])
def delete_pdf(book_id):
    book = PDFBook.query.get_or_404(book_id)
    file_path = os.path.join(app.config['PDF_FOLDER'], book.file_path) 
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'文件删除失败：{str(e)}'})
    
    db.session.delete(book)
    db.session.commit()
    return jsonify({'success': True})

# 简单的认证装饰器 (保持不变)
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # ... 认证逻辑 ...
        return f(*args, **kwargs)
    return decorated

# 图片上传接口（用于备忘录）
@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '缺少图片文件'}), 400
            
        file = request.files['file']
        
        if file.filename == '' or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            return jsonify({'success': False, 'error': '请上传图片文件（png, jpg, jpeg, gif）'}), 400
            
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(app.config['IMAGE_FOLDER'], filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'image_url': f"/uploads/images/{filename}" 
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 提供上传图片的直接访问路由（备忘录图片等）
@app.route('/uploads/images/<path:filename>')
def uploaded_image(filename):
    return send_from_directory(app.config['IMAGE_FOLDER'], filename)


# 主页路由
@app.route('/')
def index():
    return render_template('index.html')

# 获取所有书签
@app.route('/api/bookmarks', methods=['GET'])
def get_bookmarks():
    bookmarks = Bookmark.query.all()
    return jsonify({
        'bookmarks': [{
            'id': b.id,
            'title': b.title,
            'url': b.url,
            'created_at': b.created_at.strftime('%Y-%m-%d %H:%M')
        } for b in bookmarks]
    })

# 添加书签
@app.route('/api/bookmarks', methods=['POST'])
def add_bookmark():
    data = request.json
    if not data or not data.get('title') or not data.get('url'):
        return jsonify({'success': False, 'error': '标题和网址不能为空'}), 400
    
    new_bookmark = Bookmark(
        title=data['title'],
        url=data['url'],
        created_at=datetime.utcnow()
    )
    db.session.add(new_bookmark)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'bookmark': {
            'id': new_bookmark.id,
            'title': new_bookmark.title,
            'url': new_bookmark.url
        }
    })

# 删除书签
@app.route('/api/bookmarks/<int:bookmark_id>', methods=['DELETE'])
def delete_bookmark(bookmark_id):
    bookmark = Bookmark.query.get_or_404(bookmark_id)
    db.session.delete(bookmark)
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    with app.app_context():
        # 在第一次运行时创建数据库表
        db.create_all() 
        pass
    app.run(host='0.0.0.0', port=5000, debug=True)
