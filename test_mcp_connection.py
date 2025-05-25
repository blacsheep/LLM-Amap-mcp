#!/usr/bin/env python3
"""
测试MCP连接的简单脚本
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.mcp_client.amap_client import AmapMCPClient
from src.core.config import get_settings

async def test_mcp_connection():
    """测试MCP连接"""
    print("开始测试MCP连接...")
    
    try:
        # 获取配置
        settings = get_settings()
        print(f"高德API密钥: {settings.amap_maps_api_key[:10]}...")
        print(f"MCP服务器命令: {settings.amap_server_command}")
        print(f"MCP服务器参数: {settings.get_amap_server_args_list()}")
        
        # 创建客户端
        client = AmapMCPClient()
        
        # 尝试连接
        print("正在连接MCP服务器...")
        await client.connect()
        
        # 检查健康状态
        print("检查健康状态...")
        health = await client.health_check()
        print(f"健康状态: {health}")
        
        # 获取工具列表
        print("获取工具列表...")
        tools = await client.list_available_tools()
        print(f"可用工具数量: {len(tools)}")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        # 断开连接
        print("断开连接...")
        await client.disconnect()
        
        print("✅ MCP连接测试成功!")
        
    except Exception as e:
        print(f"❌ MCP连接测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_connection()) 