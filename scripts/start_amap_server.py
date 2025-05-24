#!/usr/bin/env python3
"""
高德MCP服务器启动脚本
独立启动和管理高德地图MCP服务器进程
"""

import os
import sys
import signal
import subprocess
import time
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings
from src.core.logger import setup_logger


class AmapServerManager:
    """高德MCP服务器管理器"""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = setup_logger("amap_server_manager")
        self.server_process = None
        self.is_running = False
    
    def start_server(self, daemon: bool = False) -> bool:
        """
        启动高德MCP服务器
        
        Args:
            daemon: 是否以守护进程模式运行
            
        Returns:
            bool: 启动是否成功
        """
        try:
            # 检查API密钥
            if not self.settings.amap_maps_api_key:
                self.logger.error("AMAP_MAPS_API_KEY环境变量未设置")
                return False
            
            # 检查是否已经在运行
            if self.is_running:
                self.logger.warning("服务器已经在运行")
                return True
            
            # 设置环境变量
            env = os.environ.copy()
            env["AMAP_MAPS_API_KEY"] = self.settings.amap_maps_api_key
            
            # 构建启动命令
            cmd = [self.settings.amap_server_command] + self.settings.amap_server_args
            
            self.logger.info("启动高德MCP服务器", command=" ".join(cmd))
            
            # 启动进程
            if daemon:
                # 守护进程模式
                self.server_process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )
            else:
                # 前台模式
                self.server_process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=0
                )
            
            # 等待进程启动
            time.sleep(2)
            
            # 检查进程状态
            if self.server_process.poll() is None:
                self.is_running = True
                self.logger.info("高德MCP服务器启动成功", pid=self.server_process.pid)
                return True
            else:
                # 进程启动失败
                stderr_output = ""
                if self.server_process.stderr:
                    stderr_output = self.server_process.stderr.read()
                
                self.logger.error("高德MCP服务器启动失败", stderr=stderr_output)
                return False
                
        except Exception as e:
            self.logger.error("启动服务器时发生异常", error=str(e))
            return False
    
    def stop_server(self, force: bool = False) -> bool:
        """
        停止高德MCP服务器
        
        Args:
            force: 是否强制停止
            
        Returns:
            bool: 停止是否成功
        """
        if not self.is_running or not self.server_process:
            self.logger.info("服务器未运行")
            return True
        
        try:
            self.logger.info("停止高德MCP服务器", pid=self.server_process.pid)
            
            if force:
                # 强制终止
                self.server_process.kill()
            else:
                # 优雅停止
                self.server_process.terminate()
            
            # 等待进程结束
            try:
                self.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.logger.warning("进程未在规定时间内结束，强制终止")
                self.server_process.kill()
                self.server_process.wait()
            
            self.is_running = False
            self.server_process = None
            self.logger.info("高德MCP服务器已停止")
            return True
            
        except Exception as e:
            self.logger.error("停止服务器时发生异常", error=str(e))
            return False
    
    def restart_server(self) -> bool:
        """
        重启高德MCP服务器
        
        Returns:
            bool: 重启是否成功
        """
        self.logger.info("重启高德MCP服务器")
        
        # 先停止
        if not self.stop_server():
            return False
        
        # 等待一下
        time.sleep(1)
        
        # 再启动
        return self.start_server()
    
    def get_status(self) -> dict:
        """
        获取服务器状态
        
        Returns:
            dict: 状态信息
        """
        status = {
            "is_running": self.is_running,
            "pid": None,
            "uptime": None
        }
        
        if self.server_process:
            status["pid"] = self.server_process.pid
            
            # 检查进程是否还在运行
            if self.server_process.poll() is None:
                status["is_running"] = True
            else:
                status["is_running"] = False
                self.is_running = False
        
        return status
    
    def monitor_server(self, check_interval: int = 30) -> None:
        """
        监控服务器状态，自动重启
        
        Args:
            check_interval: 检查间隔（秒）
        """
        self.logger.info("开始监控高德MCP服务器", check_interval=check_interval)
        
        try:
            while True:
                status = self.get_status()
                
                if not status["is_running"]:
                    self.logger.warning("检测到服务器停止，尝试重启")
                    if self.restart_server():
                        self.logger.info("服务器重启成功")
                    else:
                        self.logger.error("服务器重启失败")
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，停止监控")
            self.stop_server()
        except Exception as e:
            self.logger.error("监控过程中发生异常", error=str(e))


def signal_handler(signum, frame):
    """信号处理器"""
    print(f"\n收到信号 {signum}，正在停止服务器...")
    if hasattr(signal_handler, 'manager'):
        signal_handler.manager.stop_server()
    sys.exit(0)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="高德MCP服务器管理工具")
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "monitor"],
                       help="操作类型")
    parser.add_argument("--daemon", action="store_true", help="以守护进程模式启动")
    parser.add_argument("--force", action="store_true", help="强制停止")
    parser.add_argument("--interval", type=int, default=30, help="监控检查间隔（秒）")
    
    args = parser.parse_args()
    
    # 创建管理器
    manager = AmapServerManager()
    signal_handler.manager = manager
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 执行操作
    if args.action == "start":
        success = manager.start_server(daemon=args.daemon)
        if success:
            print("服务器启动成功")
            if not args.daemon:
                print("按 Ctrl+C 停止服务器")
                try:
                    manager.server_process.wait()
                except KeyboardInterrupt:
                    manager.stop_server()
        else:
            print("服务器启动失败")
            sys.exit(1)
    
    elif args.action == "stop":
        success = manager.stop_server(force=args.force)
        if success:
            print("服务器停止成功")
        else:
            print("服务器停止失败")
            sys.exit(1)
    
    elif args.action == "restart":
        success = manager.restart_server()
        if success:
            print("服务器重启成功")
        else:
            print("服务器重启失败")
            sys.exit(1)
    
    elif args.action == "status":
        status = manager.get_status()
        print(f"服务器状态: {'运行中' if status['is_running'] else '已停止'}")
        if status["pid"]:
            print(f"进程ID: {status['pid']}")
    
    elif args.action == "monitor":
        manager.monitor_server(check_interval=args.interval)


if __name__ == "__main__":
    main()