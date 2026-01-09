# 使用 Python 3.10 基础镜像
FROM python:3.10-slim

# 设置环境变量，避免 Python 生成 .pyc 文件，并设置屏幕参数
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1 \
    QT_QPA_PLATFORM=xcb

# 1. 更换国内源（Claw Cloud 在国内访问快）并安装系统依赖
# xvfb: 虚拟屏幕, x11vnc: 远程桌面服务, fluxbox: 轻量级窗口管理器
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc fluxbox novnc net-tools \
    libgl1-mesa-glx libegl1-mesa libxkbcommon-x11-0 \
    libdbus-1-3 fontconfig ttf-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 2. 设置工作目录
WORKDIR /app

# 3. 复制依赖并安装
COPY requirements.txt .
# 升级 pip 并安装 Python 依赖
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt && \
    pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple websockify

# 4. 安装 Playwright 的浏览器（Chromium）
RUN playwright install chromium && playwright install-deps chromium

# 5. 复制所有代码到容器
COPY . .

# 6. 复制启动脚本并赋予权限
COPY start.sh .
RUN chmod +x start.sh

# 7. 暴露 VNC 网页版端口
EXPOSE 8080

# 8. 启动命令
CMD ["./start.sh"]
