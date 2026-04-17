#!/usr/bin/env python3
"""
实时查看应用日志

用法:
    python tail_log.py              # 查看最新的日志
    python tail_log.py --follow     # 实时跟踪日志（类似 tail -f）
    python tail_log.py --lines 100  # 显示最后100行
"""

import argparse
import time
import os
from pathlib import Path


def tail_file(filepath: Path, lines: int = 50):
    """读取文件的最后几行"""
    if not filepath.exists():
        print(f"日志文件不存在: {filepath}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
        for line in all_lines[-lines:]:
            print(line.rstrip())


def follow_file(filepath: Path):
    """实时跟踪文件（类似 tail -f）"""
    if not filepath.exists():
        print(f"日志文件不存在: {filepath}")
        return
    
    print(f"实时跟踪日志: {filepath}")
    print("按 Ctrl+C 退出\n")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        f.seek(0, 2)
        
        try:
            while True:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n停止跟踪日志")


def main():
    parser = argparse.ArgumentParser(description='查看应用日志')
    parser.add_argument('--follow', '-f', action='store_true', 
                       help='实时跟踪日志（类似 tail -f）')
    parser.add_argument('--lines', '-n', type=int, default=50,
                       help='显示最后N行（默认50行）')
    parser.add_argument('--log-file', '-l', type=str, default='logs/app.log',
                       help='日志文件路径（默认 logs/app.log）')
    
    args = parser.parse_args()
    
    log_file = Path(args.log_file)
    
    if args.follow:
        follow_file(log_file)
    else:
        tail_file(log_file, args.lines)


if __name__ == '__main__':
    main()
