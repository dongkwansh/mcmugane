# app/logging_setup.py
import logging, os, json, datetime

class JsonLineFormatter(logging.Formatter):
    """로그 레코드를 한 줄의 JSON 형식으로 변환하는 포매터입니다."""
    def format(self, record):
        base = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z", # 타임스탬프 (UTC)
            "level": record.levelname, # 로그 레벨 (INFO, ERROR 등)
            "msg": record.getMessage(), # 로그 메시지
            "name": record.name # 로거 이름
        }
        # 예외 정보가 있는 경우 로그에 추가
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)

def setup_logging(log_dir: str):
    """애플리케이션 전체의 로깅을 설정합니다."""
    os.makedirs(log_dir, exist_ok=True)
    today = datetime.date.today().strftime("%Y-%m-%d")
    logfile = os.path.join(log_dir, f"{today}.jsonl")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 이미 핸들러가 설정되어 있다면 중복 추가 방지
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    # 콘솔(Stream) 핸들러 설정
    ch = logging.StreamHandler()
    ch.setFormatter(JsonLineFormatter())
    root.addHandler(ch)

    # 파일 핸들러 설정
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(JsonLineFormatter())
    root.addHandler(fh)