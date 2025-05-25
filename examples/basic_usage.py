#!/usr/bin/env python3
"""
基础使用示例
展示如何使用高德MCP客户端和多种LLM处理器进行地址解析
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_client import AmapMCPClient, create_llm_handler, get_current_provider
from src.core.logger import setup_logger
from src.core.config import get_settings


async def basic_address_parsing_example():
    """基础地址解析示例"""
    logger = setup_logger("basic_example")
    
    try:
        logger.info("开始基础地址解析示例")
        
        # 创建MCP客户端
        async with AmapMCPClient() as amap_client:
            logger.info("MCP客户端连接成功")
            
            # 使用工厂模式创建LLM处理器
            llm_handler = create_llm_handler(amap_client)
            current_provider = get_current_provider()
            logger.info(f"使用{current_provider.upper()}处理器")
            
            # 示例查询列表
            queries = [
                "请帮我解析这个地址：北京市朝阳区三里屯太古里",
                "116.397428,39.90923 这个坐标对应的地址是什么？",
                "我想知道上海市浦东新区陆家嘴金融中心的具体位置信息",
                "帮我查找北京大学的地理坐标"
            ]
            
            # 处理每个查询
            for i, query in enumerate(queries, 1):
                print(f"\n{'='*60}")
                print(f"示例 {i}: {query}")
                print('='*60)
                
                try:
                    # 处理查询
                    result = await llm_handler.process_query(query)
                    
                    # 显示结果
                    if result["success"]:
                        print(f"✅ 处理成功")
                        print(f"📝 回复: {result['final_answer']}")
                        
                        if result["tool_calls"]:
                            print(f"\n🔧 工具调用详情:")
                            for tool_call in result["tool_calls"]:
                                print(f"  - 工具: {tool_call['tool_name']}")
                                print(f"  - 参数: {tool_call['arguments']}")
                                print(f"  - 成功: {'是' if tool_call['success'] else '否'}")
                                if tool_call.get('error'):
                                    print(f"  - 错误: {tool_call['error']}")
                    else:
                        print(f"❌ 处理失败: {result.get('error', '未知错误')}")
                
                except Exception as e:
                    logger.error(f"处理查询失败", query=query, error=str(e))
                    print(f"❌ 处理查询时发生错误: {e}")
                
                # 等待一下再处理下一个查询
                await asyncio.sleep(1)
        
        logger.info("基础地址解析示例完成")
        
    except Exception as e:
        logger.error("示例执行失败", error=str(e))
        print(f"❌ 示例执行失败: {e}")


async def tool_listing_example():
    """工具列表示例"""
    logger = setup_logger("tool_example")
    
    try:
        logger.info("开始工具列表示例")
        
        # 创建MCP客户端
        async with AmapMCPClient() as amap_client:
            # 获取可用工具
            tools = await amap_client.list_available_tools()
            
            print(f"\n🔧 可用工具列表 (共 {len(tools)} 个):")
            print("="*60)
            
            for i, tool in enumerate(tools, 1):
                print(f"{i}. {tool['name']}")
                print(f"   描述: {tool['description']}")
                print(f"   输入参数: {tool['input_schema']}")
                print()
        
        logger.info("工具列表示例完成")
        
    except Exception as e:
        logger.error("工具列表示例失败", error=str(e))
        print(f"❌ 工具列表示例失败: {e}")


async def health_check_example():
    """健康检查示例"""
    logger = setup_logger("health_example")
    
    try:
        logger.info("开始健康检查示例")
        
        # 创建MCP客户端
        amap_client = AmapMCPClient()
        
        # 连接
        await amap_client.connect()
        
        # 健康检查
        is_healthy = await amap_client.health_check()
        
        print(f"\n🏥 健康检查结果: {'✅ 健康' if is_healthy else '❌ 不健康'}")
        
        # 断开连接
        await amap_client.disconnect()
        
        logger.info("健康检查示例完成")
        
    except Exception as e:
        logger.error("健康检查示例失败", error=str(e))
        print(f"❌ 健康检查示例失败: {e}")


async def interactive_mode():
    """交互模式"""
    logger = setup_logger("interactive_example")
    
    try:
        logger.info("开始交互模式")
        
        current_provider = get_current_provider()
        print(f"\n🤖 高德地址解析服务 - 交互模式 (使用 {current_provider.upper()})")
        print("="*60)
        print("输入地址或坐标进行解析，输入 'quit' 退出")
        print("示例:")
        print("  - 北京市朝阳区三里屯太古里")
        print("  - 116.397428,39.90923")
        print("  - 上海市浦东新区陆家嘴")
        print("="*60)
        
        # 创建MCP客户端和LLM处理器
        async with AmapMCPClient() as amap_client:
            llm_handler = create_llm_handler(amap_client)
            
            while True:
                try:
                    # 获取用户输入
                    query = input("\n🔍 请输入查询: ").strip()
                    
                    if query.lower() in ['quit', 'exit', '退出']:
                        print("👋 再见！")
                        break
                    
                    if not query:
                        continue
                    
                    print("⏳ 处理中...")
                    
                    # 处理查询
                    result = await llm_handler.process_query(query)
                    
                    # 显示结果
                    if result["success"]:
                        print(f"\n✅ {result['final_answer']}")
                    else:
                        print(f"\n❌ 处理失败: {result.get('error', '未知错误')}")
                
                except KeyboardInterrupt:
                    print("\n👋 再见！")
                    break
                except Exception as e:
                    logger.error("交互处理失败", error=str(e))
                    print(f"\n❌ 处理时发生错误: {e}")
        
        logger.info("交互模式结束")
        
    except Exception as e:
        logger.error("交互模式失败", error=str(e))
        print(f"❌ 交互模式失败: {e}")


def check_configuration():
    """检查配置是否正确"""
    try:
        settings = get_settings()
        current_provider = get_current_provider()
        
        print(f"🔧 当前LLM提供商: {current_provider.upper()}")
        
        # 检查高德地图API密钥
        if not settings.amap_maps_api_key or settings.amap_maps_api_key == "your_amap_api_key_here":
            print("❌ 请设置 AMAP_MAPS_API_KEY 环境变量")
            print("   从 https://lbs.amap.com/ 获取API密钥")
            return False
        
        # 根据当前提供商检查相应的API密钥
        if current_provider == "claude":
            if not settings.anthropic_api_key or settings.anthropic_api_key == "your_anthropic_api_key_here":
                print("❌ 请设置 ANTHROPIC_API_KEY 环境变量")
                print("   从 https://console.anthropic.com/ 获取API密钥")
                return False
            print(f"✅ Claude配置: 模型 {settings.claude_model}")
            
        elif current_provider == "openai":
            if not settings.openai_api_key or settings.openai_api_key == "your_openai_api_key_here":
                print("❌ 请设置 OPENAI_API_KEY 环境变量")
                print("   从 https://platform.openai.com/ 获取API密钥")
                return False
            
            print(f"✅ OpenAI配置: 模型 {settings.openai_model}")
            if settings.openai_base_url:
                print(f"   基础URL: {settings.openai_base_url}")
            else:
                print("   使用官方OpenAI API")
        
        print("✅ 配置检查通过")
        return True
        
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        print("💡 请检查 .env 文件是否存在并正确配置")
        return False


async def main():
    """主函数"""
    print("🚀 高德地址解析服务示例")
    print("="*60)
    
    # 检查配置
    if not check_configuration():
        print("\n💡 配置帮助:")
        print("1. 复制 .env.example 为 .env")
        print("2. 编辑 .env 文件，填入你的API密钥")
        print("3. 可通过 LLM_PROVIDER 环境变量选择 claude 或 openai")
        return
    
    # 选择示例模式
    print("\n请选择示例模式:")
    print("1. 基础地址解析示例")
    print("2. 工具列表示例") 
    print("3. 健康检查示例")
    print("4. 交互模式")
    print("5. 运行所有示例")
    
    try:
        choice = input("\n请输入选择 (1-5): ").strip()
        
        if choice == "1":
            await basic_address_parsing_example()
        elif choice == "2":
            await tool_listing_example()
        elif choice == "3":
            await health_check_example()
        elif choice == "4":
            await interactive_mode()
        elif choice == "5":
            await tool_listing_example()
            await health_check_example()
            await basic_address_parsing_example()
        else:
            print("❌ 无效选择")
    
    except KeyboardInterrupt:
        print("\n👋 再见！")
    except Exception as e:
        print(f"❌ 运行示例时发生错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())