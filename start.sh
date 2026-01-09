#!/bin/bash

# 1. 启动虚拟屏幕 (Xvfb)
Xvfb :1 -screen 0 1280x800x24 &
sleep 2

# 2. 启动窗口管理器 (让窗口有标题栏，方便拖动)
fluxbox &

# 3. 启动 VNC Server (传统 VNC)
x11vnc -display :1 -nopw -listen localhost -xkb -ncache 10 -ncache_cr -forever &

# 4. 启动 NoVNC (把 VNC 转成网页版，方便你直接用浏览器访问)
/usr/local/bin/websockify --web /usr/share/novnc/ 8080 localhost:5900 &

# 5. 启动你的 PyQt5 应用程序
# 必须设置 output 目录为挂载路径
export QT_DEBUG_PLUGINS=0
python3 main.py
