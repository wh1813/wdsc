# 基础镜像
FROM python:3.10-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1 \
    SCREEN_RESOLUTION=1280x800x24 \
    QT_QPA_PLATFORM=xcb \
    # 关键：设置语言为中文，避免生成的 Word 或 GUI 乱码
    LANG=C.UTF-8

# 1. 安装系统依赖
# 修复：去掉了 aliyun 源（GitHub Actions 在国外访问反而慢），并替换了 Debian 12 的新包名
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc fluxbox novnc net-tools \
    libgl1 libegl1 libxkbcommon-x11-0 libdbus-1-3 \
    libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
    xclip fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 2. 设置工作目录
WORKDIR /app

# 3. 复制依赖配置
COPY requirements.txt .

# 4. 安装 Python 依赖
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple websockify

# 5. 安装 Playwright 浏览器
RUN playwright install chromium && playwright install-deps chromium

# 6. 复制所有代码
COPY . .

# 7. 赋予脚本执行权限
RUN chmod +x start.sh

# 8. 创建关键数据目录 (对应你的代码路径)
RUN mkdir -p /app/output /app/data /app/logs

# 9. 暴露 Web 访问端口
EXPOSE 8080

# 10. 启动
CMD ["./start.sh"]
