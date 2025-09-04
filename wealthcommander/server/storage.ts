import { type User, type InsertUser, type Account, type InsertAccount, type Strategy, type InsertStrategy, type Order, type InsertOrder, type Position, type MarketData, type PortfolioSummary, type AccountInfo, type MarketStatus } from "@shared/schema";
import { randomUUID } from "crypto";

export interface IStorage {
  // User management
  getUser(id: string): Promise<User | undefined>;
  getUserByUsername(username: string): Promise<User | undefined>;
  createUser(user: InsertUser): Promise<User>;

  // Account management
  getAccount(id: string): Promise<Account | undefined>;
  getAccountsByUserId(userId: string): Promise<Account[]>;
  createAccount(account: InsertAccount & { userId: string }): Promise<Account>;
  updateAccount(id: string, updates: Partial<Account>): Promise<Account | undefined>;

  // Strategy management
  getStrategy(id: string): Promise<Strategy | undefined>;
  getStrategiesByAccountId(accountId: string): Promise<Strategy[]>;
  createStrategy(strategy: InsertStrategy & { accountId: string }): Promise<Strategy>;
  updateStrategy(id: string, updates: Partial<Strategy>): Promise<Strategy | undefined>;
  deleteStrategy(id: string): Promise<boolean>;

  // Order management
  getOrder(id: string): Promise<Order | undefined>;
  getOrdersByAccountId(accountId: string): Promise<Order[]>;
  createOrder(order: InsertOrder & { accountId: string; strategyId?: string }): Promise<Order>;
  updateOrder(id: string, updates: Partial<Order>): Promise<Order | undefined>;

  // Position management
  getPosition(accountId: string, symbol: string): Promise<Position | undefined>;
  getPositionsByAccountId(accountId: string): Promise<Position[]>;
  updatePosition(accountId: string, symbol: string, updates: Partial<Position>): Promise<Position>;

  // Market data
  getMarketData(symbol: string): Promise<MarketData | undefined>;
  updateMarketData(symbol: string, data: Partial<MarketData>): Promise<MarketData>;
  getWatchlistData(symbols: string[]): Promise<MarketData[]>;
}

export class MemStorage implements IStorage {
  private users: Map<string, User> = new Map();
  private accounts: Map<string, Account> = new Map();
  private strategies: Map<string, Strategy> = new Map();
  private orders: Map<string, Order> = new Map();
  private positions: Map<string, Position> = new Map();
  private marketData: Map<string, MarketData> = new Map();

  constructor() {
    this.initializeData();
  }

  private initializeData() {
    // Create demo user
    const demoUser: User = {
      id: "demo-user-1",
      username: "demo",
      password: "demo123"
    };
    this.users.set(demoUser.id, demoUser);

    // Create paper trading accounts
    const paperAccount1: Account = {
      id: "paper-account-1",
      userId: demoUser.id,
      name: "Paper Account #1",
      alpacaApiKey: process.env.ALPACA_PAPER_API_KEY_1 || "demo_key",
      alpacaSecretKey: process.env.ALPACA_PAPER_SECRET_KEY_1 || "demo_secret",
      isPaper: true,
      isActive: true,
      createdAt: new Date()
    };
    this.accounts.set(paperAccount1.id, paperAccount1);

    const paperAccount2: Account = {
      id: "paper-account-2",
      userId: demoUser.id,
      name: "Paper Account #2",
      alpacaApiKey: process.env.ALPACA_PAPER_API_KEY_2 || "demo_key",
      alpacaSecretKey: process.env.ALPACA_PAPER_SECRET_KEY_2 || "demo_secret",
      isPaper: true,
      isActive: true,
      createdAt: new Date()
    };
    this.accounts.set(paperAccount2.id, paperAccount2);


    // Create live trading account
    const liveAccount: Account = {
      id: "live-account-1",
      userId: demoUser.id,
      name: "Live Account",
      alpacaApiKey: process.env.ALPACA_LIVE_API_KEY || "demo_key",
      alpacaSecretKey: process.env.ALPACA_LIVE_SECRET_KEY || "demo_secret",
      isPaper: false,
      isActive: true,
      createdAt: new Date()
    };
    this.accounts.set(liveAccount.id, liveAccount);

    // Create guest user and their dedicated account
    const guestUser: User = {
      id: "guest",
      username: "guest", 
      password: "Guest4321"
    };
    this.users.set(guestUser.id, guestUser);

    // Create paper account for guest
    const guestPaperAccount: Account = {
      id: "paper-account-3",
      userId: guestUser.id,
      name: "Paper Account #3",
      alpacaApiKey: process.env.ALPACA_PAPER_API_KEY_3 || "demo_key",
      alpacaSecretKey: process.env.ALPACA_PAPER_SECRET_KEY_3 || "demo_secret",
      isPaper: true,
      isActive: true,
      createdAt: new Date()
    };
    this.accounts.set(guestPaperAccount.id, guestPaperAccount);

    // Initialize market data for watchlist
    const watchlistSymbols = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN'];
    watchlistSymbols.forEach(symbol => {
      const mockData: MarketData = {
        id: randomUUID(),
        symbol,
        price: (Math.random() * 200 + 100).toFixed(2), // Random price between 100-300
        change: ((Math.random() - 0.5) * 10).toFixed(2), // Random change between -5 to +5
        changePercent: ((Math.random() - 0.5) * 5).toFixed(2), // Random percent between -2.5% to +2.5%
        volume: Math.floor(Math.random() * 1000000),
        timestamp: new Date()
      };
      this.marketData.set(symbol, mockData);
    });
  }

  // User methods
  async getUser(id: string): Promise<User | undefined> {
    return this.users.get(id);
  }

  async getUserByUsername(username: string): Promise<User | undefined> {
    return Array.from(this.users.values()).find(user => user.username === username);
  }

  async createUser(insertUser: InsertUser): Promise<User> {
    const id = randomUUID();
    const user: User = { ...insertUser, id };
    this.users.set(id, user);
    return user;
  }

  // Account methods
  async getAccount(id: string): Promise<Account | undefined> {
    return this.accounts.get(id);
  }

  async getAccountsByUserId(userId: string): Promise<Account[]> {
    return Array.from(this.accounts.values()).filter(account => account.userId === userId);
  }

  async createAccount(account: InsertAccount & { userId: string }): Promise<Account> {
    const id = randomUUID();
    const newAccount: Account = {
      ...account,
      id,
      isPaper: account.isPaper ?? true,
      isActive: true,
      createdAt: new Date()
    };
    this.accounts.set(id, newAccount);
    return newAccount;
  }

  async updateAccount(id: string, updates: Partial<Account>): Promise<Account | undefined> {
    const account = this.accounts.get(id);
    if (!account) return undefined;
    
    const updatedAccount = { ...account, ...updates };
    this.accounts.set(id, updatedAccount);
    return updatedAccount;
  }

  // Strategy methods
  async getStrategy(id: string): Promise<Strategy | undefined> {
    return this.strategies.get(id);
  }

  async getStrategiesByAccountId(accountId: string): Promise<Strategy[]> {
    return Array.from(this.strategies.values()).filter(strategy => strategy.accountId === accountId);
  }

  async createStrategy(strategy: InsertStrategy & { accountId: string }): Promise<Strategy> {
    const id = randomUUID();
    const newStrategy: Strategy = {
      ...strategy,
      id,
      symbols: strategy.symbols || null,
      parameters: strategy.parameters || null,
      isActive: false,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    this.strategies.set(id, newStrategy);
    return newStrategy;
  }

  async updateStrategy(id: string, updates: Partial<Strategy>): Promise<Strategy | undefined> {
    const strategy = this.strategies.get(id);
    if (!strategy) return undefined;
    
    const updatedStrategy = { ...strategy, ...updates, updatedAt: new Date() };
    this.strategies.set(id, updatedStrategy);
    return updatedStrategy;
  }

  async deleteStrategy(id: string): Promise<boolean> {
    return this.strategies.delete(id);
  }

  // Order methods
  async getOrder(id: string): Promise<Order | undefined> {
    return this.orders.get(id);
  }

  async getOrdersByAccountId(accountId: string): Promise<Order[]> {
    return Array.from(this.orders.values())
      .filter(order => order.accountId === accountId)
      .sort((a, b) => b.createdAt!.getTime() - a.createdAt!.getTime());
  }

  async createOrder(order: InsertOrder & { accountId: string; strategyId?: string }): Promise<Order> {
    const id = randomUUID();
    const newOrder: Order = {
      ...order,
      id,
      strategyId: order.strategyId || null,
      price: order.price || null,
      status: 'pending',
      alpacaOrderId: null,
      filledAt: null,
      createdAt: new Date()
    };
    this.orders.set(id, newOrder);
    return newOrder;
  }

  async updateOrder(id: string, updates: Partial<Order>): Promise<Order | undefined> {
    const order = this.orders.get(id);
    if (!order) return undefined;
    
    const updatedOrder = { ...order, ...updates };
    this.orders.set(id, updatedOrder);
    return updatedOrder;
  }

  // Position methods
  async getPosition(accountId: string, symbol: string): Promise<Position | undefined> {
    const key = `${accountId}-${symbol}`;
    return this.positions.get(key);
  }

  async getPositionsByAccountId(accountId: string): Promise<Position[]> {
    return Array.from(this.positions.values()).filter(position => position.accountId === accountId);
  }

  async updatePosition(accountId: string, symbol: string, updates: Partial<Position>): Promise<Position> {
    const key = `${accountId}-${symbol}`;
    const existing = this.positions.get(key);
    
    const position: Position = {
      id: existing?.id || randomUUID(),
      accountId,
      symbol,
      quantity: 0,
      avgPrice: "0.00",
      marketValue: "0.00",
      unrealizedPl: "0.00",
      updatedAt: new Date(),
      ...existing,
      ...updates
    };
    
    this.positions.set(key, position);
    return position;
  }

  // Market data methods
  async getMarketData(symbol: string): Promise<MarketData | undefined> {
    return this.marketData.get(symbol);
  }

  async updateMarketData(symbol: string, data: Partial<MarketData>): Promise<MarketData> {
    const existing = this.marketData.get(symbol);
    const marketData: MarketData = {
      id: existing?.id || randomUUID(),
      symbol,
      price: "0.00",
      change: "0.00",
      changePercent: "0.00",
      volume: 0,
      timestamp: new Date(),
      ...existing,
      ...data
    };
    
    this.marketData.set(symbol, marketData);
    return marketData;
  }

  async getWatchlistData(symbols: string[]): Promise<MarketData[]> {
    return symbols.map(symbol => this.marketData.get(symbol)).filter(Boolean) as MarketData[];
  }
}

export const storage = new MemStorage();
