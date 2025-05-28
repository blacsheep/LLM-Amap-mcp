"""
数据处理主模块
提供命令行接口，协调整个数据处理流程
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到sys.path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, project_root)

from scripts.process_data.processor import DataProcessor
from scripts.process_data.utils import read_json_file, write_json_file
from src.core.logger import get_logger


async def main(input_file: str, output_file: str, batch_size: int = 1) -> None:
    """
    主函数，协调整个处理流程
    
    Args:
        input_file: 输入JSON文件路径
        output_file: 输出JSON文件路径
        batch_size: 批处理大小
    """
    logger = get_logger("process_data_main")
    logger.info(f"开始处理数据: 输入文件 {input_file}, 输出文件 {output_file}")
    
    processor = DataProcessor()
    
    try:
        # 读取输入文件
        data = read_json_file(input_file)
        logger.info(f"从 {input_file} 读取了 {len(data)} 条数据")
        
        # 连接到服务
        await processor.connect()
        
        # 处理数据
        processed_data = await processor.process_batch(data, batch_size)
        
        # 写入输出文件
        write_json_file(processed_data, output_file)
        logger.info(f"已将 {len(processed_data)} 条处理后的数据写入 {output_file}")
        
    except Exception as e:
        logger.error(f"处理数据时出错: {e}")
        raise
    finally:
        # 确保断开连接
        await processor.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="处理JSON数据文件")
    parser.add_argument("--input", "-i", required=True, help="输入JSON文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出JSON文件路径")
    parser.add_argument("--batch-size", "-b", type=int, default=1, help="批处理大小")
    
    args = parser.parse_args()
    
    asyncio.run(main(args.input, args.output, args.batch_size))