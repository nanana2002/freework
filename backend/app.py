from flask import Flask, request, jsonify, send_from_directory, render_template, send_file, abort
import os
import uuid
from datetime import datetime
import jwt
from functools import wraps
import requests
from dotenv import load_dotenv
import time  # 导入 time 模块用于时间戳
import codecs
import json
from .models import db, PDFBook, Conversation, Message, Bookmark, Note, WorkRecord, Game, AIConfig  # 更新导入
from flask_migrate import Migrate  # 新增导入

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
app.config['GAME_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'games')
app.config['SECRET_KEY'] = 'your-secret-key-here' 

# 创建上传目录
os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)
os.makedirs(app.config['IMAGE_FOLDER'], exist_ok=True)
os.makedirs(app.config['GAME_FOLDER'], exist_ok=True)

# 初始化数据库（只需要一次）
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///freework.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 初始化迁移工具
migrate = Migrate(app, db)

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
            
            # 根据编码类型尝试不同的解码方式
            text = ""
            decode_success = False
            
            # 如果是中文编码类型，尝试常用的中文编码
            if encoding in ['gbk', 'gb2312', 'gb18030']:
                encodings_to_try = [encoding, 'gb18030', 'gbk', 'gb2312', 'utf-8']
            else:
                encodings_to_try = [encoding, 'utf-8', 'gbk', 'gb2312', 'gb18030']
            
            for enc in encodings_to_try:
                try:
                    text = content.decode(enc)
                    decode_success = True
                    break
                except UnicodeDecodeError:
                    continue
            
            if not decode_success:
                # 如果所有编码都失败，使用utf-8并忽略错误
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



# Qwen API 调用接口（后端代理，避免前端跨域）
@app.route('/api/call-qwen', methods=['POST'])
def call_qwen():
    try:
        data = request.json
        if not data or not data.get('message') or not data.get('api_key'):
            return jsonify({'success': False, 'error': '缺少参数：message或api_key'}), 400
        
        # 构建Qwen API请求参数
        qwen_api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {data['api_key']}"
        }
        
        payload = {
            "model": "qwen-turbo",  # 可根据需要更换为其他Qwen模型
            "messages": [
                {"role": "user", "content": data['message']}
            ],
            "temperature": 0.7
        }
        
        # 调用Qwen API
        response = requests.post(
            qwen_api_url,
            headers=headers,
            data=json.dumps(payload)
        )
        
        # 处理API响应
        if response.status_code == 200:
            result = response.json()
            if result.get('choices') and len(result['choices']) > 0:
                return jsonify({
                    'success': True,
                    'response': result['choices'][0]['message']['content']
                })
            else:
                return jsonify({'success': False, 'error': 'API返回格式异常'})
        else:
            return jsonify({
                'success': False,
                'error': f'API调用失败：{response.status_code}，{response.text}'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'服务器错误：{str(e)}'}), 500
    
   

# 获取所有对话列表
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    conversations = Conversation.query.order_by(Conversation.updated_at.desc()).all()
    return jsonify({
        'conversations': [c.to_dict() for c in conversations]
    })

# 创建新对话
@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    data = request.json
    title = data.get('title', '新对话')
    
    new_conv = Conversation(title=title)
    db.session.add(new_conv)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'conversation': new_conv.to_dict()
    })

# 获取单个对话的消息记录
@app.route('/api/conversations/<int:conv_id>/messages', methods=['GET'])
def get_conversation_messages(conv_id):
    conversation = Conversation.query.get_or_404(conv_id)
    messages = Message.query.filter_by(conversation_id=conv_id).order_by(Message.created_at).all()
    
    return jsonify({
        'conversation': conversation.to_dict(),
        'messages': [m.to_dict() for m in messages]
    })

# 保存新消息到对话
@app.route('/api/conversations/<int:conv_id>/messages', methods=['POST'])
def add_message(conv_id):
    data = request.json
    if not data or not data.get('role') or not data.get('content'):
        return jsonify({'success': False, 'error': '缺少角色或内容'}), 400
    
    # 验证对话存在
    conv = Conversation.query.get_or_404(conv_id)
    
    # 创建消息
    new_msg = Message(
        conversation_id=conv_id,
        role=data['role'],
        content=data['content']
    )
    db.session.add(new_msg)
    
    # 如果是第一条消息，用消息内容生成对话标题
    if len(conv.messages) == 0:
        conv.title = data['content'][:30]  # 取前30字作为标题
        conv.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': new_msg.to_dict(),
        'conversation': conv.to_dict()
    })

# 删除对话
@app.route('/api/conversations/<int:conv_id>', methods=['DELETE'])
def delete_conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    db.session.delete(conv)
    db.session.commit()
    return jsonify({'success': True})


# 新增备忘录
@app.route('/api/notes', methods=['POST'])
def create_note():
    data = request.json
    if not data or not data.get('title'):
        return jsonify({'success': False, 'error': '标题不能为空'}), 400
    
    new_note = Note(
        id=str(uuid.uuid4()),  # 使用UUID作为唯一标识
        title=data['title'],
        content=data.get('content', ''),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.session.add(new_note)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'note': new_note.to_dict()
    })

# 获取所有备忘录
@app.route('/api/notes', methods=['GET'])
def get_notes():
    notes = Note.query.order_by(Note.updated_at.desc()).all()
    return jsonify({
        'success': True,
        'notes': [note.to_dict() for note in notes]
    })

# 更新备忘录
@app.route('/api/notes/<string:note_id>', methods=['PUT'])
def update_note(note_id):
    note = Note.query.get_or_404(note_id)
    data = request.json
    
    if 'title' in data:
        note.title = data['title']
    if 'content' in data:
        note.content = data['content']
    note.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'success': True, 'note': note.to_dict()})

# 删除备忘录
@app.route('/api/notes/<string:note_id>', methods=['DELETE'])
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    db.session.delete(note)
    db.session.commit()
    return jsonify({'success': True})

# 工作记录接口 - 获取所有记录
@app.route('/api/work-records', methods=['GET'])
def get_work_records():
    records = WorkRecord.query.order_by(
        WorkRecord.date.desc(), 
        WorkRecord.time.desc()
    ).all()
    return jsonify({
        'success': True,
        'records': [record.to_dict() for record in records]
    })

# 工作记录接口 - 添加新记录
@app.route('/api/work-records', methods=['POST'])
def add_work_record():
    data = request.json
    if not data or 'date' not in data or 'time' not in data or 'hours' not in data:
        return jsonify({'success': False, 'error': '缺少必要参数'}), 400
    
    new_record = WorkRecord(
        date=data['date'],
        time=data['time'],
        hours=float(data['hours']),
        manual=data.get('manual', False)
    )
    db.session.add(new_record)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'record': new_record.to_dict()
    })


@app.route('/api/work-records/<int:record_id>', methods=['DELETE'])
def delete_work_record(record_id):
    try:
        record = WorkRecord.query.get(record_id)
        if record is None:
            return jsonify({'success': False, 'error': '记录不存在'}), 404
        
        db.session.delete(record)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# 扫雷游戏页面路由
@app.route('/games/minesweeper')
def minesweeper():
    return render_template('games/minesweeper.html')

# 游戏上传接口
@app.route('/api/upload-game', methods=['POST'])
def upload_game():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未找到文件'})
    
    file = request.files['file']
    name = request.form.get('name', '未命名游戏')
    
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'})
    
    # 验证文件类型（仅HTML/JS/CSS等）
    allowed_extensions = ['.html', '.htm', '.js', '.css', '.zip']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return jsonify({'success': False, 'error': '文件格式错误，仅支持HTML、JS、CSS或ZIP文件'})
        
    # 构造文件名
    safe_name = ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    if not safe_name:
        safe_name = 'untitled'
        
    filename = f"{safe_name}_{int(time.time())}{file_ext}"
    file_path = os.path.join(app.config['GAME_FOLDER'], filename)
    
    try:
        file.save(file_path)
    except Exception as e:
        app.logger.error(f'游戏文件保存失败: {str(e)}')
        return jsonify({'success': False, 'error': f'文件保存失败: {str(e)}'})
    
    relative_path = filename 
    
    new_game = Game(name=name, file_path=relative_path, game_type='custom')
    db.session.add(new_game)
    db.session.commit()
    
    return jsonify({'success': True, 'game': new_game.to_dict()})

# 获取所有游戏列表
@app.route('/api/get-games', methods=['GET'])
def get_games():
    games = Game.query.all()
    return jsonify({'games': [game.to_dict() for game in games]})

# 删除游戏
@app.route('/api/delete-game/<int:game_id>', methods=['DELETE'])
def delete_game(game_id):
    game = Game.query.get_or_404(game_id)
    file_path = os.path.join(app.config['GAME_FOLDER'], game.file_path) 
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'文件删除失败：{str(e)}'})
    
    db.session.delete(game)
    db.session.commit()
    return jsonify({'success': True})

# 获取/保存AI配置
@app.route('/api/ai-config', methods=['GET', 'POST'])
def ai_config():
    if request.method == 'POST':
        data = request.json
        api_key = data.get('api_key')
        model_type = data.get('model_type', 'qwen-turbo')
        
        if not api_key:
            return jsonify({'success': False, 'error': 'API密钥不能为空'}), 400
        
        # 检查是否已有配置，如果有则更新，否则创建新配置
        config = AIConfig.query.first()
        if config:
            config.api_key = api_key
            config.model_type = model_type
        else:
            config = AIConfig(api_key=api_key, model_type=model_type)
            db.session.add(config)
        
        db.session.commit()
        return jsonify({'success': True, 'config': config.to_dict()})
    
    else:  # GET请求
        config = AIConfig.query.first()
        if config:
            return jsonify({'success': True, 'config': config.to_dict()})
        else:
            return jsonify({'success': True, 'config': None})
            
# 1. 定义好您的基础上传目录
UPLOADS_BASE_DIR = os.path.join(app.root_path, 'uploads')

@app.route('/api/notes/upload-image', methods=['POST'])
def upload_image_route():
    try:
        if 'image' not in request.files:
            return jsonify({"success": False, "error": "No image part"}), 400
            
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({"success": False, "error": "No selected file"}), 400
        
        filename = file.filename 
        
        # 2. 定义您想保存的具体子目录
        # (这应该与您前端请求的路径 /uploads/notes/images/ 一致)
        target_directory = os.path.join(UPLOADS_BASE_DIR, 'notes', 'images')
        
        # 3. ✅ 关键修复：在保存前，确保这个目录存在
        os.makedirs(target_directory, exist_ok=True)
        
        # 4. 定义完整的文件保存路径
        save_path = os.path.join(target_directory, filename)
        
        # 5. 保存文件
        file.save(save_path)
        
        # 6. 构造给前端的 URL
        file_url = f"/uploads/notes/images/{filename}" 
        
        # 7. 只有在真正保存成功后，才返回成功
        return jsonify({"success": True, "url": file_url})

    except Exception as e:
        # 8. ✅ 关键修复：如果发生任何错误，必须返回失败的 JSON
        print(f"Error saving image: {e}") # 在服务器上打印错误
        return jsonify({"success": False, "error": f"Internal server error: {e}"}), 500
    
@app.route('/uploads/<path:subpath>')
def serve_uploaded_file(subpath):
    """
    提供 /uploads/ 路径下的所有文件s。
    'subpath' 会自动捕获 URL 中 'uploads/' 之后的所有内容，
    例如 'notes/images/9ae4b168909be01f27d7ae41ec5be621.jpeg'
    """
    return send_from_directory(UPLOADS_BASE_DIR, subpath)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 取消注释，首次运行时创建所有表
    app.run(host='0.0.0.0', port=5000, debug=True)
