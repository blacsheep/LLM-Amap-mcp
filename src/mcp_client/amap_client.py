"""
高德地图MCP客户端实现
"""

import asyncio
import subprocess
import signal
import os
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..core.config import get_settings
from ..core.logger import get_logger
from ..core.exceptions import (
    MCPConnectionError,
    ServerProcessError,
    ToolCallError,
    TimeoutError
)
from ..utils.helpers import retry_async


class AmapMCPClient:
    """高德地图MCP客户端"""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger("amap_mcp_client")
        
        # 连接相关
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.stdio = None
        self.write = None
        
        # 进程管理
        self.server_process: Optional[subprocess.Popen] = None
        self.is_connected = False
        
        # 工具缓存
        self._available_tools: Optional[List[Dict[str, Any]]] = None
    
    async def connect(self) -> None:
        """
        连接到高德MCP服务器
        """
        try:
            self.logger.info("开始连接高德MCP服务器")
            
            # 启动MCP服务器进程
            await self._start_amap_server()
            
            # 建立MCP连接
            await self._establish_mcp_connection()
            
            # 初始化会话
            await self._initialize_session()
            
            # 获取可用工具
            await self._load_available_tools()
            
            self.is_connected = True
            self.logger.info("成功连接到高德MCP服务器", 
                           tools_count=len(self._available_tools or []))
            
        except Exception as e:
            self.logger.error("连接高德MCP服务器失败", error=str(e))
            await self.disconnect()
            raise MCPConnectionError(f"连接失败: {e}")
    
    async def disconnect(self) -> None:
        """
        断开连接并清理资源
        """
        try:
            self.logger.info("开始断开MCP连接")
            
            # 清理MCP会话
            if self.session:
                try:
                    await self.exit_stack.aclose()
                except Exception as e:
                    self.logger.warning("清理MCP会话时出错", error=str(e))
            
            # 停止服务器进程
            await self._stop_amap_server()
            
            # 重置状态
            self.session = None
            self.stdio = None
            self.write = None
            self.is_connected = False
            self._available_tools = None
            
            self.logger.info("MCP连接已断开")
            
        except Exception as e:
            self.logger.error("断开连接时出错", error=str(e))
    
    @retry_async(max_retries=3, delay=1.0)
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用MCP工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具调用结果
        """
        if not self.is_connected or not self.session:
            raise MCPConnectionError("MCP客户端未连接")
        
        try:
            self.logger.info("调用MCP工具", tool_name=tool_name, arguments=arguments)
            
            # 验证工具是否可用
            if not self._is_tool_available(tool_name):
                raise ToolCallError(f"工具 {tool_name} 不可用")
            
            # 调用工具
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments),
                timeout=self.settings.mcp_server_timeout
            )
            
            self.logger.info("工具调用成功", tool_name=tool_name)
            return result.content
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"工具调用超时: {tool_name}")
        except Exception as e:
            self.logger.error("工具调用失败", tool_name=tool_name, error=str(e))
            raise ToolCallError(f"工具调用失败: {e}")
    
    async def list_available_tools(self) -> List[Dict[str, Any]]:
        """
        获取可用工具列表
        
        Returns:
            工具列表
        """
        if not self.is_connected:
            raise MCPConnectionError("MCP客户端未连接")
        
        if self._available_tools is None:
            await self._load_available_tools()
        
        return self._available_tools or []
    
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            bool: 连接是否健康
        """
        try:
            if not self.is_connected or not self.session:
                return False
            
            # 尝试获取工具列表
            await self.session.list_tools()
            return True
            
        except Exception as e:
            self.logger.warning("健康检查失败", error=str(e))
            return False
    
    async def _start_amap_server(self) -> None:
        """启动高德MCP服务器进程"""
        try:
            # 设置环境变量
            env = os.environ.copy()
            env["AMAP_MAPS_API_KEY"] = self.settings.amap_maps_api_key
            
            # 构建命令
            cmd = [self.settings.amap_server_command] + self.settings.amap_server_args
            
            self.logger.info("启动高德MCP服务器", command=cmd)
            
            # 启动进程
            self.server_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=0
            )
            
            # 等待进程启动
            await asyncio.sleep(2)
            
            # 检查进程是否正常运行
            if self.server_process.poll() is not None:
                stderr_output = self.server_process.stderr.read() if self.server_process.stderr else ""
                raise ServerProcessError(f"MCP服务器启动失败: {stderr_output}")
            
            self.logger.info("高德MCP服务器启动成功", pid=self.server_process.pid)
            
        except Exception as e:
            self.logger.error("启动高德MCP服务器失败", error=str(e))
            raise ServerProcessError(f"启动服务器失败: {e}")
    
    async def _stop_amap_server(self) -> None:
        """停止高德MCP服务器进程"""
        if not self.server_process:
            return
        
        try:
            self.logger.info("停止高德MCP服务器", pid=self.server_process.pid)
            
            # 尝试优雅关闭
            self.server_process.terminate()
            
            # 等待进程结束
            try:
                await asyncio.wait_for(
                    asyncio.create_task(self._wait_for_process()),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                # 强制杀死进程
                self.logger.warning("强制终止MCP服务器进程")
                self.server_process.kill()
                await asyncio.create_task(self._wait_for_process())
            
            self.server_process = None
            self.logger.info("高德MCP服务器已停止")
            
        except Exception as e:
            self.logger.error("停止MCP服务器时出错", error=str(e))
    
    async def _wait_for_process(self) -> None:
        """等待进程结束"""
        if self.server_process:
            while self.server_process.poll() is None:
                await asyncio.sleep(0.1)
    
    async def _establish_mcp_connection(self) -> None:
        """建立MCP连接"""
        try:
            # 配置服务器参数
            server_params = StdioServerParameters(
                command=self.settings.amap_server_command,
                args=self.settings.amap_server_args,
                env={"AMAP_MAPS_API_KEY": self.settings.amap_maps_api_key}
            )
            
            # 建立stdio连接
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self.stdio, self.write = stdio_transport
            
            # 创建会话
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.stdio, self.write)
            )
            
        except Exception as e:
            raise MCPConnectionError(f"建立MCP连接失败: {e}")
    
    async def _initialize_session(self) -> None:
        """初始化MCP会话"""
        try:
            await self.session.initialize()
        except Exception as e:
            raise MCPConnectionError(f"初始化MCP会话失败: {e}")
    
    async def _load_available_tools(self) -> None:
        """加载可用工具列表"""
        try:
            response = await self.session.list_tools()
            self._available_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
                for tool in response.tools
            ]
        except Exception as e:
            self.logger.error("加载工具列表失败", error=str(e))
            self._available_tools = []
    
    def _is_tool_available(self, tool_name: str) -> bool:
        """检查工具是否可用"""
        if not self._available_tools:
            return False
        
        return any(tool["name"] == tool_name for tool in self._available_tools)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()