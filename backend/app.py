from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import uuid
from datetime import datetime
import jwt
import time
from functools import wraps
from .models import db, PDFBook
from flask import send_file, abort
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()  # 读取项目根目录的.env文件

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 初始化 Flask 应用，指定模板和静态文件目录
app = Flask(
    __name__,
    template_folder=os.path.join(current_dir, 'templates'),  # 明确指定模板目录
    static_folder=os.path.join(current_dir, 'static')       # 明确指定静态文件目录
)
# 配置
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['PDF_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'pdfs')
app.config['IMAGE_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'images')
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 生产环境中更换为安全的密钥

# 创建上传目录
os.makedirs(app.config['PDF_FOLDER'], exist_ok=True)
os.makedirs(app.config['IMAGE_FOLDER'], exist_ok=True)

# 初始化数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///freework.db'  # 使用SQLite数据库
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)



# 上传PDF接口
@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未找到文件'})
    
    file = request.files['file']
    title = request.form.get('title', '未命名文档')
    
    if file.filename == '':
        return jsonify({'success': False, 'error': '未选择文件'})
    
    if file and file.filename.endswith('.pdf'):
        # 使用 PDF_FOLDER 保存（之前的配置）
        filename = f"{datetime.now().timestamp()}_{file.filename.replace(' ', '_')}"
        file_path = os.path.join(app.config['PDF_FOLDER'], filename)  # 关键修改
        file.save(file_path)
        
        # 相对路径计算正确（相对于 backend 目录）
        relative_path = os.path.relpath(file_path, os.path.dirname(__file__))
        new_book = PDFBook(title=title, file_path=relative_path)

        # 保存到数据库
        db.session.add(new_book)
        db.session.commit()
        
        return jsonify({'success': True, 'book': new_book.to_dict()})
    
    return jsonify({'success': False, 'error': '文件格式错误，仅支持PDF'})

# 获取PDF文件接口
@app.route('/api/get-pdf/<int:book_id>', methods=['GET'])  # 明确指定 int 类型
def get_pdf(book_id):
    book = PDFBook.query.get_or_404(book_id)
    # 转换为绝对路径（避免相对路径查找失败）
    file_path = os.path.join(os.path.dirname(__file__), book.file_path)
    if not os.path.exists(file_path):
        abort(404, description="PDF文件不存在")
    return send_file(file_path, mimetype='application/pdf')

# 获取所有PDF列表
@app.route('/api/get-pdfs', methods=['GET'])
def get_pdfs():
    books = PDFBook.query.all()
    return jsonify({'books': [book.to_dict() for book in books]})

# 删除pdf
@app.route('/api/delete-pdf/<int:book_id>', methods=['DELETE'])  # 明确 int 类型
def delete_pdf(book_id):
    book = PDFBook.query.get_or_404(book_id)
    # 同样转换为绝对路径删除
    file_path = os.path.join(os.path.dirname(__file__), book.file_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            return jsonify({'success': False, 'error': f'文件删除失败：{str(e)}'})
    db.session.delete(book)
    db.session.commit()
    return jsonify({'success': True})

# 简单的认证装饰器
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': '认证令牌缺失'}), 401
            
        try:
            # 移除Bearer前缀
            if token.startswith('Bearer '):
                token = token[7:]
                
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            # 在实际应用中，这里可以从数据库加载用户信息
        except:
            return jsonify({'message': '无效的认证令牌'}), 401
            
        return f(*args, **kwargs)
    return decorated

# 主页路由
@app.route('/')
def index():
    return render_template('index.html')

# 静态文件路由
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory(app.config['STATIC_FOLDER'], path)

# 图片上传接口（用于备忘录）
@app.route('/api/upload-image', methods=['POST'])
# @token_required  # 如果需要认证可以启用
def upload_image():
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '缺少图片文件'}), 400
            
        file = request.files['file']
        
        # 检查文件类型
        if file.filename == '' or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            return jsonify({'success': False, 'error': '请上传图片文件（png, jpg, jpeg, gif）'}), 400
            
        # 保存文件
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(app.config['IMAGE_FOLDER'], filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'image_url': f"/api/files/image/{filename}"
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 游戏接口 - 获取游戏列表
@app.route('/api/games', methods=['GET'])
def get_games():
    games = [
        {'id': '1024', 'name': '1024游戏'},
        {'id': 'gomoku', 'name': '五子棋'}
    ]
    return jsonify({'games': games})

# 游戏接口 - 获取游戏HTML
@app.route('/api/games/<game_id>', methods=['GET'])
def get_game(game_id):
    # 实际应用中应该检查游戏是否存在
    return send_from_directory(os.path.join(app.config['STATIC_FOLDER'], 'games'), f'{game_id}.html')

# Qwen API代理接口
@app.route('/api/proxy/qwen', methods=['POST'])

# @token_required  # 如果需要认证可以启用
def qwen_proxy():
    import requests
    
    try:
        data = request.json
        api_key = data.get('api_key')
        messages = data.get('messages')
        
        if not api_key or not messages:
            return jsonify({'error': '缺少API密钥或消息'}), 400
            
        # 调用Qwen API
        url = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        payload = {
            'model': 'qwen-plus',  # 可以根据需要更换模型
            'messages': messages
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return jsonify(response.json())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

import requests  # 确保已导入

# 新增：Qwen API对话接口
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message')
    api_key = data.get('api_key')
    
    if not message or not api_key:
        return jsonify({'success': False, 'error': '消息和API密钥不能为空'})
    
    try:
        # 调用Qwen官方API（替换为真实接口）
        response = requests.post(
            url='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            json={
                'model': 'qwen-plus',  # 模型名称，可根据需要更换
                'messages': [{'role': 'user', 'content': message}]
            },
            timeout=30  # 设置超时时间，避免无限等待
        )
        
        # 处理API返回结果
        if response.status_code == 200:
            qwen_data = response.json()
            if qwen_data.get('choices') and len(qwen_data['choices']) > 0:
                return jsonify({
                    'success': True,
                    'response': qwen_data['choices'][0]['message']['content']
                })
            else:
                return jsonify({'success': False, 'error': 'API返回格式错误'})
        else:
            return jsonify({
                'success': False,
                'error': f'API调用失败: {response.status_code}，{response.text}'
            })
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'服务器错误: {str(e)}'})

if __name__ == '__main__':
    # 生产环境中使用 waitress或gunicorn等WSGI服务器
    app.run(host='0.0.0.0', port=5000, debug=True)
    