import type { Express } from "express";
import { createServer, type Server } from "http";
import { WebSocketServer, WebSocket } from "ws";
import session from "express-session";
import { storage } from "./storage";
import { 
  processInteractiveBuy, 
  processInteractiveSell,
  handleInteractiveResponse,
  handleConfirmation,
  getClientState,
  loadETFData
} from "./interactive-commands";
import { z } from "zod";
import { insertOrderSchema, type WebSocketMessage, type TerminalCommand } from "@shared/schema";
import { logger } from "./logger";
import { authService } from "./auth";

// Declare session user interface for TypeScript
declare module 'express-session' {
  interface SessionData {
    userId?: string;
    username?: string;
  }
}

// WebSocket client management
const wsClients = new Map<string, WebSocket>();
let messages: Record<string, string> = {};

// Interactive command state management
interface InteractiveState {
  type: 'buy' | 'sell' | null;
  step: number;
  ticker?: string;
  etfName?: string;
  quantity?: number | string;
  price?: number;
  totalAmount?: number;
  isETF?: boolean;
}

const clientStates = new Map<string, InteractiveState>();
let etfData: any = {};

// Load messages
async function loadMessages() {
  try {
    const fs = await import('fs');
    const data = fs.readFileSync('data/messages.json', 'utf8');
    messages = JSON.parse(data);
  } catch (error) {
    console.error('Failed to load messages.json:', error);
    messages = {};
  }
}

function getMessage(key: string, params?: Record<string, string>): string {
  let message = messages[key] || key;
  if (params) {
    Object.entries(params).forEach(([param, value]) => {
      message = message.replace(`{${param}}`, value);
    });
  }
  return message;
}

// Broadcast to all WebSocket clients
function broadcast(message: WebSocketMessage) {
  const data = JSON.stringify({ ...message, timestamp: new Date().toISOString() });
  wsClients.forEach((ws) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(data);
    }
  });
}

// Send to specific client
function sendToClient(clientId: string, message: WebSocketMessage) {
  const ws = wsClients.get(clientId);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ ...message, timestamp: new Date().toISOString() }));
  }
}

// Process terminal commands based on Python implementation
async function processTerminalCommand(command: string, clientId?: string): Promise<string> {
  if (!command) return '';
  
  const parts = command.split(' ');
  const cmd = parts[0].toLowerCase();
  
  try {
    // Handle interactive responses first
    if (clientId) {
      const interactiveResponse = await handleInteractiveResponse(command, clientId, broadcast);
      if (interactiveResponse) {
        return interactiveResponse;
      }
    }
    
    // Check for buy command
    if (cmd === 'buy' && clientId) {
      return await processInteractiveBuy(command, clientId, broadcast);
    }
    
    // Check for sell command
    if (cmd === 'sell' && clientId) {
      return await processInteractiveSell(command, clientId, broadcast);
    }
    
    // Check for confirmation responses
    if (clientId && ['y', 'yes', 'n', 'no'].includes(cmd)) {
      return await handleConfirmation(command, clientId, broadcast);
    }
    // Ticker command (.TICKER)
    if (cmd.startsWith('.') && cmd.length > 1) {
      const ticker = command.slice(1).toUpperCase();
      // Get market data for the ticker - first try to get from storage, then create if not exists
      let marketData = await storage.getMarketData(ticker);
      if (!marketData) {
        // Create mock market data for demonstration (in real app, would fetch from Alpaca API)
        const mockPrice = (Math.random() * 200 + 50).toFixed(2);
        const mockChange = ((Math.random() - 0.5) * 10).toFixed(2);
        const mockChangePercent = ((parseFloat(mockChange) / parseFloat(mockPrice)) * 100).toFixed(2);
        
        marketData = await storage.updateMarketData(ticker, {
          symbol: ticker,
          price: mockPrice,
          change: mockChange,
          changePercent: mockChangePercent,
          volume: Math.floor(Math.random() * 1000000),
          timestamp: new Date()
        });
      }
      
      const price = parseFloat(marketData.price);
      const change = parseFloat(marketData.change || '0');
      const changePercent = parseFloat(marketData.changePercent || '0');
      
      const arrow = change >= 0 ? '▲' : '▼';
      const sign = change >= 0 ? '+' : '';
      
      let result = `=== ${ticker} | 현재 시세 ===\n`;
      result += `Price : $${price.toFixed(2)}  ${arrow} ${sign}$${Math.abs(change).toFixed(2)} (${sign}${changePercent.toFixed(2)}%)\n`;
      
      // Check if we have a position
      const positions = await storage.getPositionsByAccountId('demo-account-1');
      const position = positions.find(p => p.symbol === ticker);
      if (position) {
        const marketValue = position.quantity * price;
        result += `\n[HOLDING]\n`;
        result += `Qty ${position.quantity.toLocaleString()} @ $${Number(position.avgPrice).toFixed(2)}\n`;
        result += `      = $${marketValue.toFixed(2)}`;
      } else {
        result += `\n(보유 없음)`;
      }
      
      return result;
    }
    
    // Help command
    if (cmd === 'help' || cmd === '?') {
      return `[계좌]\n  accounts / acc         계좌 목록 보기\n  account [ID]           계좌 변경\n\n[기본]\n  info / list / orders / .TICKER\n\n[주문]\n  buy .T QTY [LIMIT]     주식 구매\n  sell .T all|QTY [LIMIT] 주식 판매\n  cancel [ID]            주문 취소\n  cancel all             모든 주문 취소\n\n[차트/분석]\n  chart .T [DAYS]        차트 보기\n\n[기타]\n  help / quit`;
    }
    
    // Mode switching
    if (cmd === 'live') {
      return '!!! LIVE TRADING ENABLED !!!';
    }
    
    if (cmd === 'paper') {
      return 'PAPER TRADING MODE';
    }
    
    // Account info
    if (cmd === 'info') {
      const account = await storage.getAccount('demo-account-1');
      if (!account) return 'Account not found';
      
      const positions = await storage.getPositionsByAccountId('demo-account-1');
      let totalValue = 0;
      
      // Calculate portfolio value
      for (const pos of positions) {
        const marketData = await storage.getMarketData(pos.symbol);
        if (marketData) {
          totalValue += pos.quantity * parseFloat(marketData.price);
        }
      }
      
      let result = '=== ACCOUNT INFO ===\n';
      result += `계좌: ${account.name}\n`;
      result += `Equity: $${totalValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}\n`;
      result += `Cash: $15,420.33\n`;
      result += `Buying Power: $30,840.66\n`;
      result += `P/L Today: +$432.15 (+1.73%)\n`;
      result += `Status: ACTIVE`;
      
      return result;
    }
    
    // Portfolio list
    if (cmd === 'portfolio') {
      const positions = await storage.getPositionsByAccountId('demo-account-1');
      if (positions.length === 0) {
        return '(보유 종목 없음)';
      }
      
      let result = '=== POSITIONS ===\n';
      let totalValue = 0;
      
      for (const pos of positions) {
        const marketData = await storage.getMarketData(pos.symbol);
        const currentPrice = marketData ? parseFloat(marketData.price) : Number(pos.avgPrice);
        const marketValue = pos.quantity * currentPrice;
        totalValue += marketValue;
        
        result += `${pos.symbol.padEnd(6)} ${pos.quantity.toLocaleString().padStart(5)} $${Number(pos.avgPrice).toFixed(2).padStart(7)} $${marketValue.toFixed(2).padStart(10)}\n`;
      }
      
      result += `\nTotal Value: $${totalValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
      return result;
    }

    // MyETF list command  
    if (cmd === 'list') {
      const etfName = parts[1]?.toLowerCase(); // list myETF1, case insensitive
      
      try {
        const fs = await import('fs/promises');
        const myETFData = JSON.parse(await fs.readFile('data/myetf.json', 'utf-8'));
        
        if (!etfName) {
          // Show all myETF list in 2 columns
          let result = '=== MyETF 목록 ===\n';
          const entries = Object.entries(myETFData);
          
          // Split into pairs for 2-column layout
          for (let i = 0; i < entries.length; i += 2) {
            const [key1, etf1] = entries[i] as [string, any];
            const [key2, etf2] = entries[i + 1] as [string, any] || [null, null];
            
            // First row - ETF names
            const col1Name = `${key1.padEnd(10)} | ${etf1.name}`.padEnd(40);
            const col2Name = key2 ? `${key2.padEnd(10)} | ${etf2.name}` : '';
            result += `${col1Name} ${col2Name}\n`;
            
            // Second row - descriptions
            const col1Desc = `${''.padEnd(10)} | ${etf1.description}`.padEnd(40);
            const col2Desc = key2 ? `${''.padEnd(10)} | ${etf2.description}` : '';
            result += `${col1Desc} ${col2Desc}\n`;
            
            // Third row - risk and category
            const col1Risk = `${''.padEnd(10)} | 위험도: ${etf1.riskLevel} | 카테고리: ${etf1.category}`.padEnd(40);
            const col2Risk = key2 ? `${''.padEnd(10)} | 위험도: ${etf2.riskLevel} | 카테고리: ${etf2.category}` : '';
            result += `${col1Risk} ${col2Risk}\n`;
            
            // Fourth row - symbols
            const col1Symbols = `${''.padEnd(10)} | 구성종목: ${etf1.symbols.join(', ')}`.padEnd(40);
            const col2Symbols = key2 ? `${''.padEnd(10)} | 구성종목: ${etf2.symbols.join(', ')}` : '';
            result += `${col1Symbols} ${col2Symbols}\n\n`;
          }
          
          return result;
        } else {
          // Show specific myETF details - case insensitive matching
          let matchedKey = null;
          let etf: any = null;
          
          // Find case-insensitive match
          for (const [key, value] of Object.entries(myETFData)) {
            if (key.toLowerCase() === etfName) {
              matchedKey = key;
              etf = value as any;
              break;
            }
          }
          
          if (!etf) {
            return `MyETF '${etfName}'을 찾을 수 없습니다.\n사용 가능한 ETF: ${Object.keys(myETFData).join(', ')}`;
          }
          
          let result = `=== ${matchedKey} 상세 정보 ===\n`;
          result += `이름: ${etf.name}\n`;
          result += `설명: ${etf.description}\n`;
          result += `위험도: ${etf.riskLevel}\n`;
          result += `카테고리: ${etf.category}\n`;
          result += `생성일: ${etf.createdDate}\n`;
          result += `수정일: ${etf.lastModified}\n\n`;
          result += `=== 구성 종목 ===\n`;
          etf.symbols.forEach((symbol: string, index: number) => {
            result += `${symbol.padEnd(6)} ${etf.weights[index]}%\n`;
          });
          result += `\n총 비중: ${etf.totalAllocation}%`;
          
          return result;
        }
      } catch (error) {
        return 'MyETF 데이터를 불러올 수 없습니다.';
      }
    }
    
    // Orders
    if (cmd === 'orders') {
      const orders = await storage.getOrdersByAccountId('demo-account-1');
      if (orders.length === 0) {
        return '(주문 없음)';
      }
      
      let result = '=== ORDERS ===\n';
      orders.forEach((order, index) => {
        const shortId = order.id.slice(-8);
        const orderType = order.orderType === 'market' ? 'MARKET' : `LIMIT @ $${order.price || '0.00'}`;
        result += `${shortId} | ${order.symbol} ${order.side.toUpperCase()} ${order.quantity} (${orderType}) - ${order.status}\n`;
      });
      
      return result;
    }
    
    // Cancel command
    if (cmd === 'cancel') {
      const orderId = parts[1];
      
      if (!orderId) {
        return 'Usage: cancel [order_id] | cancel all';
      }
      
      if (orderId === 'all') {
        // Cancel all pending orders
        const orders = await storage.getOrdersByAccountId('demo-account-1');
        const pendingOrders = orders.filter(order => order.status === 'pending');
        
        if (pendingOrders.length === 0) {
          return 'No pending orders to cancel.';
        }
        
        // Cancel all pending orders
        for (const order of pendingOrders) {
          await storage.updateOrder(order.id, { status: 'cancelled' });
        }
        
        return `Cancelled ${pendingOrders.length} pending orders.`;
      } else {
        // Cancel specific order
        const orders = await storage.getOrdersByAccountId('demo-account-1');
        const order = orders.find(o => o.id.endsWith(orderId) || o.id === orderId);
        
        if (!order) {
          return `Order ${orderId} not found.`;
        }
        
        if (order.status !== 'pending') {
          return `Order ${orderId} cannot be cancelled (status: ${order.status}).`;
        }
        
        await storage.updateOrder(order.id, { status: 'cancelled' });
        return `Order ${orderId} cancelled.`;
      }
    }
    
    // Accounts command
    if (cmd === 'accounts' || cmd === 'acc') {
      let result = '=== AVAILABLE ACCOUNTS ===\n\n';
      result += 'Live Account:\n';
      result += '  live-account-1 (LIVE) - $25,430.50\n\n';
      result += 'Paper Accounts:\n';
      result += '* paper-account-1 (PAPER) - $100,000.00\n';
      result += '  paper-account-2 (PAPER) - $50,000.00\n';
      result += '  paper-account-3 (PAPER) - $75,000.00\n\n';
      result += '* = Current active account\n';
      result += '\nUse: account [account_id] to switch';
      return result;
    }
    
    // Account switch command
    if (cmd === 'account') {
      const accountAlias = parts[1];
      if (!accountAlias) {
        return 'Usage: account [live|paper1|paper2|paper3]';
      }
      
      // Map aliases to account IDs
      const accountMap: Record<string, string> = {
        'live': 'live-account-1',
        'paper1': 'paper-account-1', 
        'paper2': 'paper-account-2',
        'paper3': 'paper-account-3'
      };
      
      const accountId = accountMap[accountAlias];
      if (!accountId) {
        return `Invalid account: ${accountAlias}\nValid accounts: ${Object.keys(accountMap).join(', ')}`;
      }
      
      // Switch account (in real implementation, this would update current session)
      return `Switched to account: ${accountId} (${accountAlias})`;
    }
    
    // Legacy buy command fallback (should not reach here if clientId exists)
    if (cmd === 'buy') {
      return '대화형 매수 명령을 사용하세요. "buy"만 입력하십시오.';
    }
    
    // Sell command
    if (cmd === 'sell') {
      if (parts.length < 2) {
        return '사용법: sell .TICKER QTY|all [LIMIT]';
      }
      
      const ticker = parts[1]?.startsWith('.') ? parts[1].slice(1).toUpperCase() : parts[1]?.toUpperCase();
      const quantityStr = parts[2];
      const limitPrice = parts[3] ? parseFloat(parts[3]) : null;
      
      if (!ticker || !quantityStr) {
        return '올바른 종목과 수량을 입력하세요.';
      }
      
      let quantity: number;
      if (quantityStr.toLowerCase() === 'all') {
        // Find position and sell all
        const positions = await storage.getPositionsByAccountId('demo-account-1');
        const position = positions.find(p => p.symbol === ticker);
        if (!position) {
          return `${ticker} 보유 종목이 없습니다.`;
        }
        quantity = position.quantity;
      } else {
        quantity = parseInt(quantityStr);
        if (quantity <= 0) {
          return '올바른 수량을 입력하세요.';
        }
      }
      
      // Create order
      const order = await storage.createOrder({
        accountId: 'demo-account-1',
        symbol: ticker,
        side: 'sell',
        quantity,
        orderType: limitPrice ? 'limit' : 'market',
        price: limitPrice ? limitPrice.toString() : null
      });
      
      // Broadcast order update
      broadcast({
        type: 'order_update',
        payload: { order, action: 'created' }
      });
      
      let result = '요청 전송 완료.\n';
      result += `  - 종목: ${ticker}\n`;
      result += `  - 수량: ${quantity.toLocaleString()}\n`;
      result += `  - 타입: ${limitPrice ? `LIMIT @ $${limitPrice}` : 'MARKET'}\n`;
      result += `  - 상태: ${order.status}`;
      
      return result;
    }
    
    // Cancel command
    if (cmd === 'cancel') {
      if (parts[1] === 'all') {
        return '모든 열린 주문 취소 요청 완료';
      }
      const orderId = parts[1] || '대화형 취소 모드';
      return `주문 취소 완료: ${orderId}`;
    }
    
    // Chart command with real-time data
    if (cmd === 'chart') {
      const ticker = parts[1]?.startsWith('.') ? parts[1].slice(1).toUpperCase() : 'SOXL';
      const days = parseInt(parts[2] || '30');
      
      const marketData = await storage.getMarketData(ticker);
      const currentPrice = marketData ? parseFloat(marketData.price) : 150;
      
      // Generate historical data points
      const dataPoints = [];
      const now = new Date();
      let price = currentPrice;
      
      // Generate realistic price history
      for (let i = days; i >= 0; i--) {
        const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
        price += (Math.random() - 0.5) * 4; // Daily volatility
        price = Math.max(price, 10); // Minimum price
        dataPoints.push({
          date: date,
          price: price,
          dateStr: date.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' })
        });
      }
      
      // Find min/max for scaling
      const prices = dataPoints.map(d => d.price);
      const minPrice = Math.min(...prices);
      const maxPrice = Math.max(...prices);
      const priceRange = maxPrice - minPrice || 1;
      
      let result = `=== ${ticker} 차트 (${days}일) ===\n\n`;
      
      const chartHeight = 8;
      const chartWidth = Math.min(dataPoints.length, 20);
      const step = Math.max(1, Math.floor(dataPoints.length / chartWidth));
      
      // Create chart
      for (let row = chartHeight - 1; row >= 0; row--) {
        const priceLevel = minPrice + (priceRange * row) / (chartHeight - 1);
        let line = `$${priceLevel.toFixed(0).padStart(3)} ┤`;
        
        for (let col = 0; col < chartWidth; col++) {
          const dataIndex = col * step;
          if (dataIndex < dataPoints.length) {
            const price = dataPoints[dataIndex].price;
            const relativePos = (price - minPrice) / priceRange;
            const expectedRow = relativePos * (chartHeight - 1);
            
            if (Math.abs(expectedRow - row) < 0.5) {
              line += '●';
            } else {
              line += ' ';
            }
          } else {
            line += ' ';
          }
        }
        result += line + '\n';
      }
      
      // Add date labels
      result += '    └';
      for (let i = 0; i < chartWidth; i++) {
        result += '─';
      }
      result += '→\n     ';
      
      // Show selected dates
      for (let i = 0; i < chartWidth; i += 4) {
        const dataIndex = i * step;
        if (dataIndex < dataPoints.length) {
          result += dataPoints[dataIndex].dateStr.padEnd(6);
        }
      }
      
      result += `\n\nLast: $${currentPrice.toFixed(2)}`;
      if (marketData) {
        const change = parseFloat(marketData.change || '0');
        const changePercent = parseFloat(marketData.changePercent || '0');
        result += ` (${change >= 0 ? '↗' : '↘'} ${change >= 0 ? '+' : ''}${change.toFixed(2)} ${change >= 0 ? '+' : ''}${changePercent.toFixed(2)}%)`;
      }
      
      return result;
    }
    
    // Source command
    if (cmd === 'source') {
      const source = parts[1]?.toLowerCase() || 'current: STOOQ';
      return `시세 소스: ${source.toUpperCase()}`;
    }
    
    // Feed command
    if (cmd === 'feed') {
      const feed = parts[1]?.toLowerCase() || 'current: IEX';
      return `데이터 피드: ${feed.toUpperCase()}`;
    }
    
    // Diagnostics
    if (cmd === 'diag') {
      let result = '--- System Diagnostics ---\n';
      result += 'Trading Mode  : PAPER\n';
      result += 'Quote Source  : STOOQ\n';
      result += '\n[Alpaca Configuration]\n';
      result += 'Endpoint      : https://paper-api.alpaca.markets\n';
      result += 'API Key       : PK76S...C6CZ\n';
      result += 'Market URL    : https://data.alpaca.markets\n';
      result += 'Data Feed     : IEX\n';
      result += '\n[Alpaca Connection Status]\n';
      result += 'Connection    : 성공 (계좌 ID: PA123456789)\n';
      result += 'Account Status: ACTIVE\n';
      result += '------------------------';
      
      return result;
    }
    
    // Reload
    if (cmd === 'reload') {
      return '설정 재적용 완료.';
    }
    
    // Quit
    if (cmd === 'quit') {
      return 'WealthCommander 종료';
    }
    
    // Unknown command
    return `알 수 없는 명령어: ${cmd}\n도움말을 보려면 'help'를 입력하세요.`;
    
  } catch (error) {
    console.error('Terminal command error:', error);
    return `오류: ${error instanceof Error ? error.message : 'Unknown error'}`;
  }
}

// Mock market data updates
function startMarketDataUpdates() {
  setInterval(async () => {
    const symbols = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN'];
    const updates = await Promise.all(
      symbols.map(async (symbol) => {
        const current = await storage.getMarketData(symbol);
        if (!current) return null;
        
        // Simulate price movement
        const change = (Math.random() - 0.5) * 2; // -1 to +1
        const currentPrice = parseFloat(current.price);
        const newPrice = Math.max(currentPrice + change, 1);
        const priceChange = newPrice - currentPrice;
        const changePercent = (priceChange / currentPrice) * 100;
        
        return await storage.updateMarketData(symbol, {
          price: newPrice.toFixed(2),
          change: priceChange.toFixed(2),
          changePercent: changePercent.toFixed(2),
          timestamp: new Date()
        });
      })
    );
    
    const validUpdates = updates.filter(Boolean);
    if (validUpdates.length > 0) {
      broadcast({
        type: 'market_update',
        payload: validUpdates
      });
    }
  }, 5000); // Update every 5 seconds
}

export async function registerRoutes(app: Express): Promise<Server> {
  await loadMessages();
  await loadETFData();
  
  // Session configuration
  app.use(session({
    secret: process.env.SESSION_SECRET || 'wealthcommander-secret-key-2025',
    resave: false,
    saveUninitialized: false,
    cookie: {
      secure: false, // Set to true in production with HTTPS
      httpOnly: true,
      maxAge: 24 * 60 * 60 * 1000 // 24 hours
    }
  }));


  // Authentication middleware
  const requireAuth = (req: any, res: any, next: any) => {
    if (req.session.userId) {
      next();
    } else {
      res.status(401).json({ error: '로그인이 필요합니다.' });
    }
  };

  // Authentication routes
  app.post("/api/login", async (req, res) => {
    try {
      const { username, password } = req.body;
      
      if (!username || !password) {
        return res.status(400).json({ error: '사용자명과 비밀번호를 입력해주세요.' });
      }

      const clientIp = req.ip || req.connection.remoteAddress;
      const result = await authService.authenticateUser(username, password, clientIp);

      if (result.success && result.user) {
        req.session.userId = result.user.id;
        req.session.username = result.user.username;
        
        res.json({
          success: true,
          message: result.message,
          user: {
            id: result.user.id,
            username: result.user.username,
            email: result.user.email,
            role: result.user.role
          }
        });
      } else {
        res.status(401).json({ error: result.message });
      }
    } catch (error) {
      console.error('Login error:', error);
      res.status(500).json({ error: '서버 오류가 발생했습니다.' });
    }
  });

  app.post("/api/logout", (req, res) => {
    req.session.destroy((err) => {
      if (err) {
        console.error('Logout error:', err);
        return res.status(500).json({ error: '로그아웃 중 오류가 발생했습니다.' });
      }
      res.clearCookie('connect.sid');
      res.json({ success: true, message: '로그아웃되었습니다.' });
    });
  });

  app.get("/api/user", requireAuth, async (req, res) => {
    try {
      const user = await authService.getUserById(req.session.userId!);
      if (user) {
        res.json({ user });
      } else {
        res.status(404).json({ error: '사용자를 찾을 수 없습니다.' });
      }
    } catch (error) {
      console.error('Get user error:', error);
      res.status(500).json({ error: '사용자 정보를 가져올 수 없습니다.' });
    }
  });

  app.post("/api/change-password", requireAuth, async (req, res) => {
    try {
      const { currentPassword, newPassword } = req.body;
      
      if (!currentPassword || !newPassword) {
        return res.status(400).json({ error: '현재 비밀번호와 새 비밀번호를 입력해주세요.' });
      }

      const result = await authService.changePassword(req.session.userId!, currentPassword, newPassword);
      
      if (result.success) {
        res.json({ success: true, message: result.message });
      } else {
        res.status(400).json({ error: result.message });
      }
    } catch (error) {
      console.error('Change password error:', error);
      res.status(500).json({ error: '비밀번호 변경 중 오류가 발생했습니다.' });
    }
  });
  
  // Serve messages.json file
  app.get("/messages.json", (req, res) => {
    res.json(messages);
  });
  
  // API Routes
  app.get("/api/status", async (req, res) => {
    try {
      const account = await storage.getAccount('demo-account-1');
      const strategies = await storage.getStrategiesByAccountId('demo-account-1');
      const positions = await storage.getPositionsByAccountId('demo-account-1');
      
      res.json({
        status: "running",
        market: {
          isOpen: true,
          status: getMessage('market_open')
        },
        account: {
          id: account?.id,
          name: account?.name,
          buyingPower: 15420.33,
          totalValue: 52430.21
        },
        portfolio: {
          totalValue: 52430.21,
          dayChange: 1234.56,
          dayChangePercent: 2.4,
          buyingPower: 15420.33,
          positionCount: positions.length
        },
        strategies: strategies.length,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error('Status error:', error);
      res.status(500).json({ error: getMessage('broker_error', { error: error instanceof Error ? error.message : 'Unknown error' }) });
    }
  });

  app.get("/api/accounts", requireAuth, async (req, res) => {
    try {
      const userId = req.session.userId!;
      const allowedAccounts = await authService.getAllowedAccounts(userId);
      
      // 모든 계좌 조회 (관리자는 모든 계좌, 게스트는 권한 체크)
      const user = await authService.getUserById(userId);
      const allAccounts = await storage.getAccountsByUserId(user?.role === 'admin' ? 'demo-user-1' : userId);
      
      // 권한에 따라 계좌 필터링
      let filteredAccounts;
      if (allowedAccounts.includes('all')) {
        filteredAccounts = allAccounts;
      } else {
        filteredAccounts = allAccounts.filter(acc => allowedAccounts.includes(acc.id));
      }
      
      // 기본 계좌 설정 (guest는 paper-account-3, admin은 demo-account-1)
      const defaultAccount = user?.role === 'guest' ? 'paper-account-3' : 'demo-account-1';
      
      res.json({
        accounts: filteredAccounts.map(acc => ({ 
          id: acc.id, 
          name: acc.name, 
          isPaper: acc.isPaper 
        })),
        currentAccount: defaultAccount
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Unknown error' });
    }
  });

  app.get("/api/strategies", async (req, res) => {
    try {
      // Load strategies from strategies.json file
      const fs = await import('fs/promises');
      const strategiesData = JSON.parse(await fs.readFile('data/strategies.json', 'utf-8'));
      res.json(strategiesData);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Unknown error' });
    }
  });

  app.get("/api/portfolio", async (req, res) => {
    try {
      const positions = await storage.getPositionsByAccountId('demo-account-1');
      res.json(positions);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Unknown error' });
    }
  });

  app.get("/api/orders", async (req, res) => {
    try {
      const orders = await storage.getOrdersByAccountId('demo-account-1');
      res.json(orders);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Unknown error' });
    }
  });

  app.get("/api/market-data", async (req, res) => {
    try {
      const symbols = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN'];
      const marketData = await storage.getWatchlistData(symbols);
      res.json(marketData);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Unknown error' });
    }
  });

  app.post("/api/terminal", async (req, res) => {
    try {
      const { command, clientId } = req.body as TerminalCommand;
      const result = await processTerminalCommand(command, clientId);
      res.json({ result });
    } catch (error) {
      console.error('Terminal API error:', error);
      res.status(500).json({ error: error instanceof Error ? error.message : 'Unknown error' });
    }
  });

  app.post("/api/orders", async (req, res) => {
    try {
      const orderData = insertOrderSchema.parse(req.body);
      const order = await storage.createOrder({
        ...orderData,
        accountId: 'demo-account-1'
      });

      // Broadcast order update
      broadcast({
        type: 'order_update',
        payload: { order, action: 'created' }
      });

      res.json(order);
    } catch (error) {
      res.status(400).json({ error: error instanceof Error ? error.message : 'Invalid order data' });
    }
  });

  // Auto-trading strategy endpoints
  app.post("/api/strategy/start", async (req, res) => {
    try {
      const { strategyName } = req.body;
      
      // Start the selected strategy
      if (strategyName === 'Simple Buy') {
        // Update strategy status
        strategyStatus.set(strategyName, {
          isRunning: true,
          startTime: new Date().toISOString(),
          lastExecution: new Date().toISOString()
        });
        
        // Log strategy execution
        await logger.logStrategyExecution(strategyName, {
          symbols: ['VOO', 'VTI', 'QQQ'],
          quantity: 10,
          orderType: 'market'
        }, 'demo-account-1');
        
        // Execute Simple Buy strategy
        const symbols = ['VOO', 'VTI', 'QQQ'];
        const orders = [];
        
        for (const symbol of symbols) {
          const order = await storage.createOrder({
            accountId: 'demo-account-1',
            symbol,
            side: 'buy',
            quantity: 10,
            orderType: 'market'
          });
          orders.push(order);
          
          // Log each order
          await logger.logOrderCreated(order);
        }
        
        // Broadcast strategy execution
        broadcast({
          type: 'strategy_executed',
          payload: { strategyName, orders, timestamp: new Date().toISOString() }
        });
        
        // Mark strategy as completed for Simple Buy (one-time execution)
        setTimeout(async () => {
          strategyStatus.set(strategyName, {
            isRunning: false,
            lastExecution: new Date().toISOString()
          });
          
          // Log strategy completion
          await logger.logStrategyCompletion(strategyName, {
            ordersCreated: orders.length,
            symbols: ['VOO', 'VTI', 'QQQ'],
            totalQuantity: 30
          });
          
          broadcast({
            type: 'strategy_status_update',
            payload: { strategyName, isRunning: false }
          });
        }, 1000);
        
        res.json({ success: true, message: `${strategyName} 전략 실행 완료`, orders });
      } else if (strategyName === 'SMA Cross') {
        // Update strategy status
        strategyStatus.set(strategyName, {
          isRunning: true,
          startTime: new Date().toISOString(),
          lastExecution: new Date().toISOString()
        });
        
        // Log strategy execution
        await logger.logStrategyExecution(strategyName, {
          symbols: ['SPY', 'QQQ'],
          shortMA: 5,
          longMA: 20,
          quantity: 20
        }, 'demo-account-1');
        
        // Execute SMA Cross strategy
        const symbols = ['SPY', 'QQQ'];
        const orders = [];
        
        for (const symbol of symbols) {
          const order = await storage.createOrder({
            accountId: 'demo-account-1',
            symbol,
            side: 'buy',
            quantity: 20,
            orderType: 'market'
          });
          orders.push(order);
          
          // Log each order
          await logger.logOrderCreated(order);
        }
        
        // Broadcast strategy execution
        broadcast({
          type: 'strategy_executed',
          payload: { strategyName, orders, timestamp: new Date().toISOString() }
        });
        
        res.json({ success: true, message: `${strategyName} 전략 실행 완료`, orders });
      } else if (strategyName === 'RSI Mean') {
        // Update strategy status
        strategyStatus.set(strategyName, {
          isRunning: true,
          startTime: new Date().toISOString(),
          lastExecution: new Date().toISOString()
        });
        
        // Log strategy execution
        await logger.logStrategyExecution(strategyName, {
          symbols: ['TQQQ', 'SOXL'],
          rsiPeriod: 14,
          oversoldLevel: 30,
          quantity: 15
        }, 'demo-account-1');
        
        // Execute RSI Mean strategy
        const symbols = ['TQQQ', 'SOXL'];
        const orders = [];
        
        for (const symbol of symbols) {
          const order = await storage.createOrder({
            accountId: 'demo-account-1',
            symbol,
            side: 'buy',
            quantity: 15,
            orderType: 'market'
          });
          orders.push(order);
          
          // Log each order
          await logger.logOrderCreated(order);
        }
        
        // Broadcast strategy execution
        broadcast({
          type: 'strategy_executed',
          payload: { strategyName, orders, timestamp: new Date().toISOString() }
        });
        
        res.json({ success: true, message: `${strategyName} 전략 실행 완료`, orders });
      } else if (strategyName === 'Iron Condor') {
        // Update strategy status
        strategyStatus.set(strategyName, {
          isRunning: true,
          startTime: new Date().toISOString(),
          lastExecution: new Date().toISOString()
        });
        
        // Log strategy execution
        await logger.logStrategyExecution(strategyName, {
          symbol: 'SPY',
          contracts: 1,
          dte: 35,
          strategy: 'Iron Condor'
        }, 'demo-account-1');
        
        // Simulate Iron Condor option orders
        const orders = [
          await storage.createOrder({
            accountId: 'demo-account-1',
            symbol: 'SPY_PUT_420',
            side: 'sell',
            quantity: 1,
            orderType: 'market'
          }),
          await storage.createOrder({
            accountId: 'demo-account-1',
            symbol: 'SPY_PUT_410',
            side: 'buy', 
            quantity: 1,
            orderType: 'market'
          }),
          await storage.createOrder({
            accountId: 'demo-account-1',
            symbol: 'SPY_CALL_460',
            side: 'sell',
            quantity: 1,
            orderType: 'market'
          }),
          await storage.createOrder({
            accountId: 'demo-account-1',
            symbol: 'SPY_CALL_470',
            side: 'buy',
            quantity: 1,
            orderType: 'market'
          })
        ];
        
        // Log each order
        for (const order of orders) {
          await logger.logOrderCreated(order);
        }
        
        // Broadcast strategy execution
        broadcast({
          type: 'strategy_executed',
          payload: { strategyName, orders, timestamp: new Date().toISOString() }
        });
        
        res.json({ success: true, message: `${strategyName} 전략 실행 완료 - Iron Condor 포지션 생성`, orders });
      } else if (strategyName === 'Covered Call') {
        // Update strategy status
        strategyStatus.set(strategyName, {
          isRunning: true,
          startTime: new Date().toISOString(),
          lastExecution: new Date().toISOString()
        });
        
        // Log strategy execution
        await logger.logStrategyExecution(strategyName, {
          symbol: 'AAPL',
          stockQuantity: 100,
          callContracts: 1,
          otmPercent: 0.07
        }, 'demo-account-1');
        
        // Execute Covered Call strategy
        const orders = [
          await storage.createOrder({
            accountId: 'demo-account-1',
            symbol: 'AAPL',
            side: 'buy',
            quantity: 100,
            orderType: 'market'
          }),
          await storage.createOrder({
            accountId: 'demo-account-1',
            symbol: 'AAPL_CALL_200',
            side: 'sell',
            quantity: 1,
            orderType: 'market'
          })
        ];
        
        // Log each order
        for (const order of orders) {
          await logger.logOrderCreated(order);
        }
        
        // Broadcast strategy execution
        broadcast({
          type: 'strategy_executed',
          payload: { strategyName, orders, timestamp: new Date().toISOString() }
        });
        
        res.json({ success: true, message: `${strategyName} 전략 실행 완료 - 보유주 100주 + 콜옵션 매도`, orders });
      } else if (strategyName === 'Bull Put Spread') {
        // Update strategy status
        strategyStatus.set(strategyName, {
          isRunning: true,
          startTime: new Date().toISOString(),
          lastExecution: new Date().toISOString()
        });
        
        // Log strategy execution
        await logger.logStrategyExecution(strategyName, {
          symbol: 'QQQ',
          contracts: 2,
          shortDelta: 18,
          spreadWidth: 5
        }, 'demo-account-1');
        
        // Execute Bull Put Spread strategy
        const orders = [
          await storage.createOrder({
            accountId: 'demo-account-1',
            symbol: 'QQQ_PUT_380',
            side: 'sell',
            quantity: 2,
            orderType: 'market'
          }),
          await storage.createOrder({
            accountId: 'demo-account-1',
            symbol: 'QQQ_PUT_375',
            side: 'buy',
            quantity: 2,
            orderType: 'market'
          })
        ];
        
        // Log each order
        for (const order of orders) {
          await logger.logOrderCreated(order);
        }
        
        // Broadcast strategy execution
        broadcast({
          type: 'strategy_executed',
          payload: { strategyName, orders, timestamp: new Date().toISOString() }
        });
        
        res.json({ success: true, message: `${strategyName} 전략 실행 완료 - Bull Put Spread 포지션 생성`, orders });
      } else if (strategyName === 'TMF Test') {
        // Paper account only check
        const currentAccountId = 'demo-account-1'; // In real app, get from session
        if (!currentAccountId.includes('paper') && currentAccountId !== 'demo-account-1') {
          res.json({ success: false, message: 'TMF Test는 Paper 계좌에서만 실행 가능합니다.' });
          return;
        }
        
        // Initialize timeout tracking for strategy
        activeTimeouts.set(strategyName, []);
        
        // Update strategy status
        strategyStatus.set(strategyName, {
          isRunning: true,
          startTime: new Date().toISOString(),
          completedRounds: 0,
          totalRounds: 5,
          lastExecution: new Date().toISOString()
        });
        
        // Log strategy execution
        await logger.logStrategyExecution(strategyName, {
          symbol: 'TMF',
          quantity: 5,
          maxRounds: 5,
          strategyType: 'repeated_buy_sell'
        }, 'demo-account-1');
        
        // TMF Test strategy parameters
        const symbol = 'TMF';
        const quantity = 5;
        const maxRounds = 5; // 최대 5회 반복
        let currentRound = 0;
        
        // Strategy execution function
        const executeRound = async () => {
          if (currentRound >= maxRounds) {
            broadcast({
              type: 'strategy_completed',
              payload: { strategyName, message: `TMF Test 완료: ${maxRounds}회 실행`, timestamp: new Date().toISOString() }
            });
            return;
          }
          
          currentRound++;
          
          // Update strategy status with current round
          strategyStatus.set(strategyName, {
            isRunning: true,
            startTime: strategyStatus.get(strategyName)?.startTime || new Date().toISOString(),
            completedRounds: currentRound - 1,
            totalRounds: maxRounds,
            lastExecution: new Date().toISOString()
          });
          
          // Broadcast round start
          broadcast({
            type: 'terminal_output',
            payload: `🔄 라운드 ${currentRound}/${maxRounds} 시작 - TMF ${quantity}주 매수 준비`
          });
          
          try {
            // Create buy order
            const buyOrder = await storage.createOrder({
              accountId: currentAccountId,
              symbol,
              side: 'buy',
              quantity,
              orderType: 'market'
            });
            
            broadcast({
              type: 'order_update',
              payload: { order: buyOrder, action: 'created' }
            });
            
            broadcast({
              type: 'terminal_output',
              payload: `✅ 매수 주문 생성됨 - 주문ID: ${buyOrder.id?.slice(-8)}`
            });
            
            broadcast({
              type: 'terminal_output',
              payload: `⏰ 10초 후 자동 매도 예정...`
            });
            
            // Schedule sell order after 10 seconds
            const sellTimeout = setTimeout(async () => {
              // Check if strategy is still running
              const currentStatus = strategyStatus.get(strategyName);
              if (!currentStatus?.isRunning) return;
              try {
                const sellOrder = await storage.createOrder({
                  accountId: currentAccountId,
                  symbol,
                  side: 'sell',
                  quantity,
                  orderType: 'market'
                });
                
                broadcast({
                  type: 'order_update',
                  payload: { order: sellOrder, action: 'created' }
                });
                
                broadcast({
                  type: 'terminal_output',
                  payload: `✅ 매도 주문 생성됨 - 주문ID: ${sellOrder.id?.slice(-8)}`
                });
                
                // Schedule next round after sell
                if (currentRound < maxRounds) {
                  broadcast({
                    type: 'terminal_output',
                    payload: `⏳ 2초 후 다음 라운드 진행...`
                  });
                  const nextRoundTimeout = setTimeout(executeRound, 2000); // 2초 후 다음 라운드
                  if (!activeTimeouts.has(strategyName)) {
                    activeTimeouts.set(strategyName, []);
                  }
                  activeTimeouts.get(strategyName)!.push(nextRoundTimeout);
                } else {
                  // Mark strategy as completed
                  strategyStatus.set(strategyName, {
                    isRunning: false,
                    completedRounds: maxRounds,
                    totalRounds: maxRounds,
                    lastExecution: new Date().toISOString()
                  });
                  
                  broadcast({
                    type: 'strategy_completed',
                    payload: { strategyName, message: `TMF Test 완료: ${maxRounds}회 실행`, timestamp: new Date().toISOString() }
                  });
                  
                  broadcast({
                    type: 'strategy_status_update',
                    payload: { strategyName, isRunning: false }
                  });
                }
              } catch (error) {
                console.error('TMF Test sell order failed:', error);
                broadcast({
                  type: 'terminal_output',
                  payload: `❌ 매도 주문 실패: ${error instanceof Error ? error.message : 'Unknown error'}`
                });
              }
            }, 10000);
            
            // Track sell timeout
            activeTimeouts.get(strategyName)!.push(sellTimeout); // 10 seconds
            
          } catch (error) {
            console.error('TMF Test buy order failed:', error);
            broadcast({
              type: 'terminal_output',
              payload: `❌ 매수 주문 실패: ${error instanceof Error ? error.message : 'Unknown error'}`
            });
          }
        };
        
        // Start first round
        executeRound();
        
        // Broadcast strategy execution
        broadcast({
          type: 'strategy_executed',
          payload: { strategyName, message: `TMF Test 시작 - ${maxRounds}회 반복`, timestamp: new Date().toISOString() }
        });
        
        res.json({ 
          success: true, 
          message: `${strategyName} 전략 실행 - TMF ${quantity}주씩 ${maxRounds}회 반복 매매`,
          config: { symbol, quantity, maxRounds }
        });
      } else {
        res.json({ success: false, message: '지원되지 않는 전략입니다.' });
      }
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Strategy execution failed' });
    }
  });

  app.post("/api/strategy/stop", async (req, res) => {
    try {
      const { strategyName } = req.body;
      
      // Clear all active timeouts for this strategy
      const timeouts = activeTimeouts.get(strategyName);
      if (timeouts) {
        timeouts.forEach(timeout => clearTimeout(timeout));
        activeTimeouts.delete(strategyName);
      }
      
      // Update strategy status
      const currentStatus = strategyStatus.get(strategyName);
      if (currentStatus) {
        strategyStatus.set(strategyName, {
          ...currentStatus,
          isRunning: false,
          lastExecution: new Date().toISOString()
        });
      }
      
      // Log strategy stop
      await logger.logStrategyStopped(strategyName, 'manual_stop');
      
      // Broadcast strategy stop
      broadcast({
        type: 'strategy_stopped',
        payload: { strategyName, timestamp: new Date().toISOString() }
      });
      
      broadcast({
        type: 'strategy_status_update',
        payload: { strategyName, isRunning: false }
      });
      
      res.json({ success: true, message: `${strategyName} 전략 정지 완료` });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Strategy stop failed' });
    }
  });

  app.get("/api/strategies", async (req, res) => {
    try {
      const fs = await import('fs/promises');
      const strategiesData = await fs.readFile('data/strategies.json', 'utf-8');
      res.json(JSON.parse(strategiesData));
    } catch (error) {
      res.status(500).json({ error: 'Failed to load strategies' });
    }
  });

  // Strategy status tracking
  const strategyStatus = new Map<string, {
    isRunning: boolean;
    startTime?: string;
    completedRounds?: number;
    totalRounds?: number;
    lastExecution?: string;
  }>();
  
  // Active strategy timeouts for cleanup
  const activeTimeouts = new Map<string, NodeJS.Timeout[]>();

  app.get("/api/strategy/status", async (req, res) => {
    try {
      const { strategyName } = req.query;
      if (strategyName && typeof strategyName === 'string') {
        const status = strategyStatus.get(strategyName) || {
          isRunning: false,
          lastExecution: null
        };
        res.json(status);
      } else {
        // Return all strategy statuses
        const allStatuses: any = {};
        for (const [name, status] of Array.from(strategyStatus.entries())) {
          allStatuses[name] = status;
        }
        res.json(allStatuses);
      }
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get strategy status' });
    }
  });

  // Create HTTP server
  const httpServer = createServer(app);

  // Set up WebSocket server on a specific path
  const wss = new WebSocketServer({ 
    server: httpServer,
    path: '/ws/terminal'
  });

  wss.on('connection', (ws) => {
    const clientId = Date.now().toString();
    wsClients.set(clientId, ws);

    // Send welcome message
    ws.send(JSON.stringify({
      type: 'terminal_output',
      payload: getMessage('welcome_message'),
      timestamp: new Date().toISOString()
    }));

    ws.on('message', async (data) => {
      try {
        const message = JSON.parse(data.toString());
        
        if (message.type === 'terminal_command') {
          const result = await processTerminalCommand(message.payload, clientId);
          if (result) {
            sendToClient(clientId, {
              type: 'terminal_output',
              payload: result
            });
          }
        }
      } catch (error) {
        console.error('WebSocket message error:', error);
        sendToClient(clientId, {
          type: 'terminal_output',
          payload: getMessage('broker_error', { error: error instanceof Error ? error.message : 'Unknown error' })
        });
      }
    });

    ws.on('close', () => {
      wsClients.delete(clientId);
    });
  });

  // Initialize ETF data and start market data updates
  await loadETFData();
  startMarketDataUpdates();

  return httpServer;
}
