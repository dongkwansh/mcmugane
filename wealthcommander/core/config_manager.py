"""
Configuration Manager - Optimized for Container Environment
"""

import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """통합 설정 관리자 - NAS 환경 최적화"""
    
    def __init__(self):
        # Use relative path for development, absolute for container
        if os.path.exists("/app"):
            self.config_dir = Path("/app/config")
        else:
            self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)
        
        # 기본 설정
        self.default_config = {
            "language": "ko",
            "current_account": os.getenv("DEFAULT_ACCOUNT", "PAPER1"),
            "default_account": os.getenv("DEFAULT_ACCOUNT", "PAPER1"),
            "accounts": {
                "PAPER1": {
                    "name": "PAPER1",
                    "type": "PAPER",
                    "key_id": os.getenv("ALPACA_PAPER1_KEY_ID"),
                    "secret_key": os.getenv("ALPACA_PAPER1_SECRET_KEY")
                }
            },
            "auto_trading": {
                "enabled": False,
                "strategy": "Simple_Buy",
                "interval_minutes": 1
            },
            "ui_settings": {
                "theme": "retro_mac",
                "locale": "ko_KR",
                "date_format": "YYYY-MM-DD",
                "currency_symbol": "$"
            },
            "trading_settings": {
                "allow_fractional": True,
                "max_position_size": 10000,
                "risk_limit_percent": 5.0
            }
        }
        
        self._config = self._load_config()
        self._messages = self._load_messages()
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        config_file = self.config_dir / "settings.json"
        
        try:
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                # 기본 설정과 병합
                config = self.default_config.copy()
                config.update(loaded_config)
                return config
            else:
                # Note: config_manager can't use self.get_message here due to circular dependency
                logger.info("설정 파일이 없습니다. 기본 설정을 사용합니다.")
                self._save_config(self.default_config)
                return self.default_config.copy()
                
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            return self.default_config.copy()
    
    def _load_messages(self) -> Dict[str, Any]:
        """메시지 파일 로드"""
        messages_file = self.config_dir / "messages.json"
        
        try:
            if messages_file.exists():
                with open(messages_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning("messages.json 파일이 없습니다.")
                return {"ko": {}, "en": {}}
                
        except Exception as e:
            logger.error(f"메시지 로드 실패: {e}")
            return {"ko": {}, "en": {}}
    
    def get_message(self, key: str, **kwargs) -> str:
        """언어별 메시지 조회 (최적화된 중첩 구조 지원)"""
        try:
            lang = self._config.get("language", "ko")
            message = self._get_nested_message(key, lang)
            
            if not message:
                return f"[{key}]"
            
            # 템플릿 참조 처리 (예: {icons.success}, {separators.header_50})
            message = self._resolve_template_references(message, lang)
            
            # 이스케이프 시퀀스를 실제 문자로 변환
            if isinstance(message, str):
                message = message.replace('\\\\n', '\\n')
                message = message.replace('\\\\t', '\\t')
            
            # 포맷팅 적용
            try:
                return message.format(**kwargs)
            except (KeyError, ValueError):
                logger.warning(f"메시지 포맷팅 실패: {key} with {kwargs}")
                return message
                
        except Exception as e:
            logger.error(f"메시지 조회 실패 - key: {key}, error: {e}")
            return f"[{key}]"
    
    def _get_nested_message(self, key: str, lang: str) -> str:
        """중첩된 구조에서 메시지 검색"""
        try:
            lang_messages = self._messages.get(lang, {})
            
            # 카테고리별 검색 (key가 category.item 형태)
            if '.' in key:
                category, item = key.split('.', 1)
                category_messages = lang_messages.get(category, {})
                if isinstance(category_messages, dict):
                    return category_messages.get(item, "")
            
            # 전체 카테고리에서 검색
            for category_data in lang_messages.values():
                if isinstance(category_data, dict) and key in category_data:
                    return category_data[key]
            
            return ""
        except Exception:
            return ""
    
    def _resolve_template_references(self, message: str, lang: str) -> str:
        """템플릿 참조 해결 (예: {icons.success} → ✅)"""
        try:
            # common 섹션에서 참조 해결
            common = self._messages.get("common", {})
            
            # {icons.*} 참조 처리
            if "{icons." in message:
                icons = common.get("icons", {})
                for icon_key, icon_value in icons.items():
                    message = message.replace(f"{{icons.{icon_key}}}", icon_value)
            
            # {separators.*} 참조 처리
            if "{separators." in message:
                separators = common.get("separators", {})
                for sep_key, sep_value in separators.items():
                    message = message.replace(f"{{separators.{sep_key}}}", sep_value)
            
            # {formats.*} 참조 처리
            if "{formats." in message:
                formats = common.get("formats", {})
                for fmt_key, fmt_value in formats.items():
                    message = message.replace(f"{{formats.{fmt_key}}}", fmt_value)
            
            return message
        except Exception:
            return message
    
    def _save_config(self, config: Dict[str, Any]):
        """설정 파일 저장"""
        config_file = self.config_dir / "settings.json"
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("설정이 저장되었습니다.")
        except Exception as e:
            logger.error(f"설정 저장 실패: {e}")
    
    def get_current_account(self) -> str:
        """현재 계좌명 반환"""
        return self._config.get("current_account", self.get_default_account())
    
    def get_default_account(self) -> str:
        """기본 계좌명 반환"""
        return self._config.get("default_account", os.getenv("DEFAULT_ACCOUNT", "PAPER1"))
    
    def get_account_config(self, account_name: Optional[str] = None) -> Dict[str, Any]:
        """계좌 설정 반환 (환경변수 우선)"""
        if not account_name:
            account_name = self.get_current_account()
        
        accounts = self._config.get("accounts", {})
        account_config = accounts.get(account_name, {}).copy()
        
        # 환경변수에서 API 키 정보 로드 (우선순위 높음)
        if account_name == "LIVE":
            key_id = os.getenv("ALPACA_LIVE_KEY_ID")
            secret_key = os.getenv("ALPACA_LIVE_SECRET_KEY")
            if key_id and secret_key:
                account_config.update({
                    "key_id": key_id,
                    "secret_key": secret_key,
                    "type": "LIVE"
                })
        elif account_name.startswith("PAPER"):
            # PAPER1, PAPER2, PAPER3 처리
            key_id = os.getenv(f"ALPACA_{account_name}_KEY_ID")
            secret_key = os.getenv(f"ALPACA_{account_name}_SECRET_KEY")
            if key_id and secret_key:
                account_config.update({
                    "key_id": key_id,
                    "secret_key": secret_key,
                    "type": "PAPER"
                })
        
        return account_config
    
    def get_available_accounts(self) -> List[str]:
        """사용 가능한 계좌 목록"""
        return list(self._config.get("accounts", {}).keys())
    
    def switch_account(self, account_name: str):
        """계좌 전환"""
        if account_name in self.get_available_accounts():
            self._config["current_account"] = account_name
            self._save_config(self._config)
            logger.info(f"계좌가 {account_name}로 전환되었습니다.")
        else:
            raise ValueError(f"계좌 '{account_name}'를 찾을 수 없습니다.")
    
    def set_default_account(self, account_name: str):
        """기본 계좌 설정"""
        if account_name in self.get_available_accounts():
            self._config["default_account"] = account_name
            self._save_config(self._config)
            logger.info(f"기본 계좌가 {account_name}로 설정되었습니다.")
        else:
            raise ValueError(f"계좌 '{account_name}'를 찾을 수 없습니다.")
    
    def get_auto_trading_config(self) -> Dict[str, Any]:
        """자동매매 설정 반환"""
        return self._config.get("auto_trading", {})
    
    def update_auto_trading_config(self, config: Dict[str, Any]):
        """자동매매 설정 업데이트"""
        self._config.setdefault("auto_trading", {}).update(config)
        self._save_config(self._config)
    
    def get_ui_settings(self) -> Dict[str, Any]:
        """UI 설정 반환"""
        return self._config.get("ui_settings", {})
    
    def get_trading_settings(self) -> Dict[str, Any]:
        """거래 설정 반환"""
        return self._config.get("trading_settings", {})
    
    def get_strategies_config(self) -> Dict[str, Any]:
        """전략 설정 로드"""
        strategies_dir = self.config_dir / "strategies"
        strategies = {}
        
        try:
            if strategies_dir.exists():
                for strategy_file in strategies_dir.glob("*.json"):
                    with open(strategy_file, 'r', encoding='utf-8') as f:
                        strategy_data = json.load(f)
                        strategies[strategy_file.stem] = strategy_data
            
            return strategies
        except Exception as e:
            logger.error(f"전략 설정 로드 실패: {e}")
            return {}
    
    def get_etf_definitions(self) -> Dict[str, Any]:
        """ETF 정의 로드"""
        etf_file = self.config_dir / "myETFs.json"
        
        try:
            if etf_file.exists():
                with open(etf_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"ETF 정의 로드 실패: {e}")
            return {}
    
    def get_etfs(self) -> Dict[str, Any]:
        """ETF 목록 반환 (터미널 호환성)"""
        etf_data = self.get_etf_definitions()
        if isinstance(etf_data, dict) and 'myETFs' in etf_data:
            return etf_data['myETFs']
        return etf_data
    
    def get_messages(self) -> Dict[str, Any]:
        """메시지 정의 로드"""
        messages_file = self.config_dir / "messages.json"
        
        try:
            if messages_file.exists():
                with open(messages_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"메시지 정의 로드 실패: {e}")
            return {}