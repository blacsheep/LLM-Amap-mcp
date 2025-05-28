#!/usr/bin/env python3
"""
运行测试脚本
"""

import os
import sys
import argparse
import asyncio

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="运行测试脚本")
    
    parser.add_argument("--claude", action="store_true", help="运行Claude多轮工具调用测试")
    parser.add_argument("--openai", action="store_true", help="运行OpenAI多轮工具调用测试")
    parser.add_argument("--complex", action="store_true", help="运行复杂多轮工具调用测试")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    
    return parser.parse_args()

async def run_claude_test():
    """运行Claude多轮工具调用测试"""
    print("=== 运行Claude多轮工具调用测试 ===")
    from tests.test_multi_tool_calls import test_multi_tool_calls
    await test_multi_tool_calls()

async def run_openai_test():
    """运行OpenAI多轮工具调用测试"""
    print("=== 运行OpenAI多轮工具调用测试 ===")
    from tests.test_openai_multi_tool_calls import test_openai_multi_tool_calls
    await test_openai_multi_tool_calls()

async def run_complex_test():
    """运行复杂多轮工具调用测试"""
    print("=== 运行复杂多轮工具调用测试 ===")
    from tests.test_complex_multi_tool_calls import test_complex_multi_tool_calls
    await test_complex_multi_tool_calls()

async def main():
    """主函数"""
    args = parse_args()
    
    # 默认运行Claude测试
    run_all = args.all or not (args.claude or args.openai or args.complex)
    
    if args.claude or run_all:
        await run_claude_test()
    
    if args.openai or run_all:
        await run_openai_test()
    
    if args.complex or run_all:
        await run_complex_test()

if __name__ == "__main__":
    asyncio.run(main()) 