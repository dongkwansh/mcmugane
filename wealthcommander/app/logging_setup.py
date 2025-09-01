# app/logging_setup.py
import logging
import os
import json
import datetime

class JsonLineFormatter(logging.Formatter):
    """JSON 라인 포매터"""
    def format(self, record):
        base = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "msg": record.getMessage(),
            "name": record.name
        }
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)

def setup_logging(log_dir: str):
    """로깅 설정"""
    os.makedirs(log_dir, exist_ok=True)
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    logfile = os.path.join(log_dir, f"{today}.jsonl")
    
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    
    # 기존 핸들러 제거
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    # 콘솔 핸들러
    ch = logging.StreamHandler()
    ch.setFormatter(JsonLineFormatter())
    root.addHandler(ch)
    
    # 파일 핸들러
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(JsonLineFormatter())
    root.addHandler(fh)