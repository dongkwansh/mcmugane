from flask_jwt_extended import create_access_token, create_refresh_token
import bcrypt
import json
from datetime import timedelta

class AuthManager:
    def __init__(self, config_path='/app/config/users.json'):
        self.config_path = config_path
        self.users = self.load_users()
    
    def load_users(self):
        """사용자 정보 로드"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except:
            # 기본 사용자
            return {
                'trader': {
                    'password_hash': bcrypt.hashpw('mcmugane'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
                    'role': 'admin'
                }
            }
    
    def verify_user(self, username: str, password: str) -> bool:
        """사용자 인증"""
        user = self.users.get(username)
        if not user:
            return False
        
        return bcrypt.checkpw(
            password.encode('utf-8'),
            user['password_hash'].encode('utf-8')
        )
    
    def create_tokens(self, username: str):
        """JWT 토큰 생성"""
        access_token = create_access_token(
            identity=username,
            expires_delta=timedelta(hours=24)
        )
        refresh_token = create_refresh_token(
            identity=username,
            expires_delta=timedelta(days=30)
        )
        return {
            'access_token': access_token,
            'refresh_token': refresh_token
        }
    
    def add_user(self, username: str, password: str, role: str = 'user'):
        """사용자 추가"""
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.users[username] = {
            'password_hash': password_hash,
            'role': role
        }
        self.save_users()
    
    def save_users(self):
        """사용자 정보 저장"""
        with open(self.config_path, 'w') as f:
            json.dump(self.users, f, indent=2)