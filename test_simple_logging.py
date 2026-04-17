"""
简单测试文件日志
"""

import logging
from pathlib import Path

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "test.log"

print(f"测试日志文件: {log_file.absolute()}")

handler = logging.FileHandler(log_file, mode='w')
handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

logger = logging.getLogger("test")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

logger.info("这是一条测试日志")
logger.debug("这是一条调试日志")
logger.warning("这是一条警告日志")

handler.flush()
handler.close()

print(f"\n日志已写入，请查看: {log_file.absolute()}")
print(f"文件大小: {log_file.stat().st_size} 字节")

with open(log_file, 'r') as f:
    content = f.read()
    print(f"\n文件内容:\n{content}")
