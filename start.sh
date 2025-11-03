#!/bin/bash

# 定义服务参数
PORT=5000
LOG_FILE="backend/app.log"
VENV_NAME="freework"  # 虚拟环境名称

# 清除系统代理
echo "正在清除系统代理..."
unset http_proxy
unset https_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
echo "代理已清除"

# 检查端口是否被占用
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "错误：端口 $PORT 已被占用（进程ID: $(lsof -t -i :$PORT)）"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "$VENV_NAME" ]; then
    echo "警告：未找到虚拟环境 $VENV_NAME，将使用系统Python环境"
else
    echo "激活虚拟环境: $VENV_NAME"
    source "$VENV_NAME/bin/activate" || {
        echo "激活虚拟环境失败"
        exit 1
    }
fi

# 启动服务
echo "正在启动服务（端口: $PORT）..."
mkdir -p backend  # 确保日志目录存在
nohup python3 -m backend.app > "$LOG_FILE" 2>&1 &

# 等待服务启动
sleep 3

# 验证启动结果
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "服务启动成功！"
    echo "进程ID: $(lsof -t -i :$PORT)"
    echo "日志文件: $LOG_FILE"
else
    echo "服务启动失败，请查看日志: $LOG_FILE"
    exit 1
fi