import sqlite3
from datetime import datetime
import json
from typing import List, Dict, Any, Optional
import threading

class DatabaseManager:
    def __init__(self, db_path: str = '/app/data/mcmugane.db'):
        self.db_path = db_path
        self.local = threading.local()
        self._init_db()
    
    def _get_connection(self):
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_path)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn
    
    def _init_db(self):
        """데이터베이스 초기화"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 거래 내역 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                order_id TEXT,
                status TEXT,
                strategy TEXT,
                mode TEXT
            )
        ''')
        
        # 로그 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                level TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT
            )
        ''')
        
        # 전략 성과 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                strategy_name TEXT NOT NULL,
                total_trades INTEGER,
                winning_trades INTEGER,
                total_pnl REAL,
                win_rate REAL,
                sharpe_ratio REAL
            )
        ''')
        
        # 포트폴리오 스냅샷 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_value REAL,
                cash REAL,
                positions TEXT,
                daily_pnl REAL
            )
        ''')
        
        conn.commit()
    
    def add_trade(self, trade_data: Dict[str, Any]) -> int:
        """거래 기록 추가"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (symbol, side, quantity, price, order_id, status, strategy, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['symbol'],
            trade_data['side'],
            trade_data['quantity'],
            trade_data['price'],
            trade_data.get('order_id'),
            trade_data.get('status', 'pending'),
            trade_data.get('strategy'),
            trade_data.get('mode', 'PAPER')
        ))
        
        conn.commit()
        return cursor.lastrowid
    
    def add_log(self, level: str, category: str, message: str, details: Optional[str] = None):
        """로그 추가"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO logs (level, category, message, details)
            VALUES (?, ?, ?, ?)
        ''', (level, category, message, json.dumps(details) if details else None))
        
        conn.commit()
    
    def get_trades(self, 
                   symbol: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """거래 내역 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        trades = []
        for row in cursor.fetchall():
            trades.append(dict(row))
        
        return trades
    
    def get_logs(self, date: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """로그 조회"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM logs WHERE 1=1"
        params = []
        
        if date:
            query += " AND DATE(timestamp) = ?"
            params.append(date)
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        
        logs = []
        for row in cursor.fetchall():
            log_dict = dict(row)
            if log_dict.get('details'):
                log_dict['details'] = json.loads(log_dict['details'])
            logs.append(log_dict)
        
        return logs
    
    def save_portfolio_snapshot(self, snapshot: Dict[str, Any]):
        """포트폴리오 스냅샷 저장"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO portfolio_snapshots (total_value, cash, positions, daily_pnl)
            VALUES (?, ?, ?, ?)
        ''', (
            snapshot['total_value'],
            snapshot['cash'],
            json.dumps(snapshot['positions']),
            snapshot.get('daily_pnl', 0)
        ))
        
        conn.commit()
    
    def update_strategy_performance(self, strategy_name: str, performance: Dict[str, Any]):
        """전략 성과 업데이트"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategy_performance 
            (strategy_name, total_trades, winning_trades, total_pnl, win_rate, sharpe_ratio)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            strategy_name,
            performance['total_trades'],
            performance['winning_trades'],
            performance['total_pnl'],
            performance['win_rate'],
            performance.get('sharpe_ratio', 0)
        ))
        
        conn.commit()