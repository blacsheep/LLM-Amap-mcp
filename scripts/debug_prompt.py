#!/usr/bin/env python3
"""
提示词调试脚本
用于测试自定义system prompt和query的效果

这个脚本允许你轻松测试不同的系统提示词(system prompt)，看看它们如何影响大模型的响应。
你可以使用默认的提示词、从文件加载自定义提示词，或者直接在命令行中指定提示词。

功能特点:
- 支持从文件加载自定义提示词
- 支持保存当前使用的提示词到文件
- 可以直接执行单个查询，或者进入交互式模式连续测试多个查询
- 可以设置上下文信息（JSON格式）
- 可以查看完整的响应结果，包括工具调用详情

使用示例:
1. 使用默认提示词，进入交互式模式:
   python scripts/debug_prompt.py

2. 使用自定义提示词文件，进入交互式模式:
   python scripts/debug_prompt.py --prompt-file my_prompt.txt

3. 使用命令行指定的提示词，执行单个查询:
   python scripts/debug_prompt.py --prompt "你是一个地址解析助手..." --query "北京市朝阳区三里屯太古里"

4. 保存当前使用的提示词到文件:
   python scripts/debug_prompt.py --save-prompt my_prompt.txt

5. 使用自定义上下文信息:
   python scripts/debug_prompt.py --context '{"city": "北京"}'

交互式模式命令:
  :q, :quit  - 退出程序
  :p, :prompt - 显示当前使用的系统提示词
  :s, :save <文件名> - 保存当前提示词到文件
  :c, :context <JSON> - 设置上下文信息（JSON格式）

提示词文件格式:
提示词文件是一个纯文本文件，内容就是你想要使用的系统提示词。
例如，创建一个名为 my_prompt.txt 的文件，内容如下:

```
你是一个专业的地址解析助手，擅长解析中国地址。
请分析用户提供的地址信息，提取其中的省份、城市、区县、街道等信息。
如果用户提供的是坐标，请将其转换为详细地址。
```

然后使用 --prompt-file my_prompt.txt 参数加载这个提示词。
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_client import AmapMCPClient, create_llm_handler, get_current_provider
from src.core.logger import setup_logger, get_logger
from src.core.config import get_settings
from src.core.prompt_manager import get_prompt_manager, get_system_prompt


def setup_argument_parser() -> argparse.ArgumentParser:
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="系统提示词调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认提示词，交互式输入查询
  python scripts/debug_prompt.py
  
  # 使用自定义提示词文件，交互式输入查询
  python scripts/debug_prompt.py --prompt-file my_prompt.txt
  
  # 使用默认提示词，执行单个查询
  python scripts/debug_prompt.py --query "北京市朝阳区三里屯太古里"
  
  # 使用自定义提示词文本，执行单个查询
  python scripts/debug_prompt.py --prompt "你是一个地址解析助手..." --query "北京市朝阳区三里屯太古里"
  
  # 将当前使用的提示词保存到文件
  python scripts/debug_prompt.py --save-prompt my_prompt.txt
"""
    )
    
    # 提示词相关参数
    prompt_group = parser.add_argument_group("提示词选项")
    prompt_source = prompt_group.add_mutually_exclusive_group()
    prompt_source.add_argument(
        "--prompt", "-p", 
        type=str, 
        help="直接指定系统提示词文本"
    )
    prompt_source.add_argument(
        "--prompt-file", "-f", 
        type=str, 
        help="从文件加载系统提示词"
    )
    prompt_source.add_argument(
        "--template", "-t", 
        type=str, 
        default="default",
        help="使用注册的提示词模板名称 (默认: default)"
    )
    prompt_group.add_argument(
        "--save-prompt", "-s", 
        type=str, 
        help="将当前使用的提示词保存到文件"
    )
    
    # 查询相关参数
    query_group = parser.add_argument_group("查询选项")
    query_group.add_argument(
        "--query", "-q", 
        type=str, 
        help="直接指定查询内容，如果不提供则进入交互模式"
    )
    query_group.add_argument(
        "--context", "-c", 
        type=str, 
        help="额外的上下文信息，JSON格式"
    )
    
    # 输出选项
    output_group = parser.add_argument_group("输出选项")
    output_group.add_argument(
        "--json", "-j", 
        action="store_true", 
        help="以JSON格式输出结果"
    )
    output_group.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="显示详细输出信息"
    )
    
    return parser


def load_prompt_from_file(file_path: str) -> str:
    """从文件加载提示词"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"❌ 无法从文件加载提示词: {e}")
        sys.exit(1)


def save_prompt_to_file(prompt: str, file_path: str) -> None:
    """将提示词保存到文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        print(f"✅ 提示词已保存到文件: {file_path}")
    except Exception as e:
        print(f"❌ 无法保存提示词到文件: {e}")


def parse_context(context_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """解析上下文字符串为字典"""
    if not context_str:
        return None
    
    try:
        return json.loads(context_str)
    except json.JSONDecodeError:
        print(f"❌ 上下文必须是有效的JSON格式")
        sys.exit(1)


async def process_query(
    llm_handler, 
    query: str, 
    system_prompt: str, 
    context: Optional[Dict[str, Any]] = None,
    json_output: bool = False,
    verbose: bool = False
) -> None:
    """处理单个查询"""
    try:
        # 处理查询
        result = await llm_handler.process_query(
            query=query,
            context=context,
            system_prompt=system_prompt
        )
        
        if json_output:
            # 以JSON格式输出
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        
        # 格式化输出
        if result["success"]:
            print(f"\n✅ 处理成功")
            print(f"\n📝 回复: {result['final_answer']}")
            
            if result["tool_calls"] and verbose:
                print(f"\n🔧 工具调用详情:")
                for tool_call in result["tool_calls"]:
                    print(f"  - 工具: {tool_call['tool_name']}")
                    print(f"  - 参数: {tool_call['arguments']}")
                    print(f"  - 成功: {'是' if tool_call['success'] else '否'}")
                    if tool_call.get('result'):
                        if isinstance(tool_call['result'], str) and len(tool_call['result']) > 100:
                            print(f"  - 结果: {tool_call['result'][:100]}...")
                        else:
                            print(f"  - 结果: {tool_call['result']}")
                    if tool_call.get('error'):
                        print(f"  - 错误: {tool_call['error']}")
        else:
            print(f"\n❌ 处理失败: {result.get('error', '未知错误')}")
    
    except Exception as e:
        print(f"\n❌ 处理查询时发生错误: {e}")


async def interactive_mode(
    llm_handler, 
    system_prompt: str, 
    json_output: bool = False,
    verbose: bool = False
) -> None:
    """交互式模式"""
    current_provider = get_current_provider()
    print(f"\n🤖 系统提示词调试工具 - 交互模式 (使用 {current_provider.upper()})")
    print("="*60)
    print("输入查询内容进行测试，输入以下命令执行特殊功能：")
    print("  :q, :quit  - 退出程序")
    print("  :p, :prompt - 显示当前使用的系统提示词")
    print("  :s, :save <文件名> - 保存当前提示词到文件")
    print("  :c, :context <JSON> - 设置上下文信息（JSON格式）")
    print("="*60)
    
    context = None
    
    while True:
        try:
            # 获取用户输入
            query = input("\n🔍 请输入查询: ").strip()
            
            if not query:
                continue
                
            # 处理特殊命令
            if query.startswith(":"):
                parts = query.split(maxsplit=1)
                command = parts[0].lower()
                
                if command in [":q", ":quit", ":exit"]:
                    print("👋 再见！")
                    break
                    
                elif command in [":p", ":prompt"]:
                    print("\n📋 当前系统提示词:")
                    print("-" * 40)
                    print(system_prompt)
                    print("-" * 40)
                    continue
                    
                elif command in [":s", ":save"]:
                    if len(parts) < 2:
                        print("❌ 请指定保存文件名")
                        continue
                    save_prompt_to_file(system_prompt, parts[1])
                    continue
                    
                elif command in [":c", ":context"]:
                    if len(parts) < 2:
                        print(f"📋 当前上下文: {context}")
                        continue
                    try:
                        context = json.loads(parts[1])
                        print(f"✅ 上下文已更新: {context}")
                    except json.JSONDecodeError:
                        print("❌ 上下文必须是有效的JSON格式")
                    continue
                    
                else:
                    print(f"❌ 未知命令: {command}")
                    continue
            
            print("⏳ 处理中...")
            
            # 处理查询
            await process_query(
                llm_handler=llm_handler,
                query=query,
                system_prompt=system_prompt,
                context=context,
                json_output=json_output,
                verbose=verbose
            )
            
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 处理时发生错误: {e}")


async def main() -> None:
    """主函数"""
    # 设置日志记录器
    logger = setup_logger("prompt_debug")
    
    # 解析命令行参数
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # 确定系统提示词
    system_prompt = None
    
    if args.prompt:
        system_prompt = args.prompt
        logger.info("使用命令行提供的系统提示词")
    elif args.prompt_file:
        system_prompt = load_prompt_from_file(args.prompt_file)
        logger.info(f"从文件加载系统提示词: {args.prompt_file}")
    else:
        system_prompt = get_system_prompt(args.template)
        logger.info(f"使用模板提示词: {args.template}")
    
    # 如果只是要保存提示词，则执行保存并退出
    if args.save_prompt:
        save_prompt_to_file(system_prompt, args.save_prompt)
        return
    
    # 解析上下文
    context = parse_context(args.context)
    
    try:
        # 创建MCP客户端和LLM处理器
        async with AmapMCPClient() as amap_client:
            llm_handler = create_llm_handler(amap_client)
            
            current_provider = get_current_provider()
            print(f"🔧 使用 {current_provider.upper()} 处理器")
            
            if args.query:
                # 单次查询模式
                print(f"🔍 执行查询: {args.query}")
                
                await process_query(
                    llm_handler=llm_handler,
                    query=args.query,
                    system_prompt=system_prompt,
                    context=context,
                    json_output=args.json,
                    verbose=args.verbose
                )
            else:
                # 交互式模式
                await interactive_mode(
                    llm_handler=llm_handler,
                    system_prompt=system_prompt,
                    json_output=args.json,
                    verbose=args.verbose
                )
                
    except Exception as e:
        logger.error("执行失败", error=str(e))
        print(f"❌ 执行失败: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 