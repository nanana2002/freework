#!/bin/bash

# 定义端口
PORT=5000

# 检查服务是否运行
if ! lsof -i :$PORT > /dev/null 2>&1; then
    echo "端口 $PORT 上没有运行的服务"
    exit 0
fi

# 获取进程ID并停止服务
PID=$(lsof -t -i :$PORT)
echo "正在停止端口 $PORT 上的服务（进程ID: $PID）..."
kill $PID

# 等待进程终止
sleep 2

# 强制清理残留进程（如果有的话）
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "强制终止残留进程..."
    kill -9 $(lsof -t -i :$PORT)
fi

echo "服务已停止"