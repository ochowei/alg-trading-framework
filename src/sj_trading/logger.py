import logging
from pathlib import Path

def init_logger(filename, mode='w'):
    logger = logging.getLogger(filename)
    logger.setLevel(logging.DEBUG)

    # ✅ 確保只添加 handler 一次，避免重複輸出 log
    if not logger.hasHandlers():
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')        
        # ✅ 設定 console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # ✅ 設定 file handler（確保 log 不會被重複寫入）
        log_file = Path(f'log/{filename}')
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(f'log/{filename}', mode=mode, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
