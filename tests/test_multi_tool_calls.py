#!/usr/bin/env python3
"""
测试多轮工具调用
"""

import asyncio
import sys
import os
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.mcp_client.amap_client import AmapMCPClient
from src.mcp_client import create_llm_handler, get_current_provider
from src.core.config import get_settings

async def test_multi_tool_calls():
    """测试多轮工具调用"""
    logger.info("开始测试多轮工具调用...")
    
    try:
        # 创建MCP客户端
        async with AmapMCPClient() as amap_client:
            logger.info("MCP客户端连接成功")
            
            # 使用工厂模式创建LLM处理器
            llm_handler = create_llm_handler(amap_client)
            current_provider = get_current_provider()
            logger.info(f"使用{current_provider.upper()}处理器")
            
            # 测试需要多轮工具调用的查询
            query = "查询一下北京市和上海市今天的天气，并告诉我在这两个城市中，哪个城市更适合户外活动？"
            
            logger.info(f"发送查询: {query}")
            
            # 处理查询
            result = await llm_handler.process_query(query)
            
            # 显示结果
            if result["success"]:
                logger.info("处理成功")
                logger.info(f"回复: {result['final_answer']}")
                
                if result["tool_calls"]:
                    logger.info(f"工具调用详情 (共 {len(result['tool_calls'])} 次):")
                    for i, tool_call in enumerate(result["tool_calls"], 1):
                        logger.info(f"  - 调用 {i}:")
                        logger.info(f"    工具: {tool_call['tool_name']}")
                        logger.info(f"    参数: {tool_call['arguments']}")
                        logger.info(f"    成功: {'是' if tool_call['success'] else '否'}")
                        if tool_call.get('error'):
                            logger.info(f"    错误: {tool_call['error']}")
            else:
                logger.error(f"处理失败: {result.get('error', '未知错误')}")
        
        logger.info("多轮工具调用测试完成")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_multi_tool_calls()) 