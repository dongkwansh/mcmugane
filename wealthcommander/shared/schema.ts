import { sql } from "drizzle-orm";
import { pgTable, text, varchar, integer, decimal, timestamp, boolean, jsonb } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

export const users = pgTable("users", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  username: text("username").notNull().unique(),
  password: text("password").notNull(),
});

export const accounts = pgTable("accounts", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  userId: varchar("user_id").references(() => users.id).notNull(),
  name: text("name").notNull(),
  alpacaApiKey: text("alpaca_api_key").notNull(),
  alpacaSecretKey: text("alpaca_secret_key").notNull(),
  isPaper: boolean("is_paper").default(true),
  isActive: boolean("is_active").default(true),
  createdAt: timestamp("created_at").defaultNow(),
});

export const strategies = pgTable("strategies", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  accountId: varchar("account_id").references(() => accounts.id).notNull(),
  name: text("name").notNull(),
  type: text("type").notNull(), // 'simple_buy', 'sma_crossover', 'rsi_mean_reversion', 'breakout_donchian'
  symbols: text("symbols").array(),
  parameters: jsonb("parameters"),
  isActive: boolean("is_active").default(false),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const orders = pgTable("orders", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  accountId: varchar("account_id").references(() => accounts.id).notNull(),
  strategyId: varchar("strategy_id").references(() => strategies.id),
  symbol: text("symbol").notNull(),
  side: text("side").notNull(), // 'buy', 'sell'
  quantity: integer("quantity").notNull(),
  orderType: text("order_type").notNull(), // 'market', 'limit', 'stop'
  price: decimal("price", { precision: 10, scale: 2 }),
  status: text("status").notNull(), // 'pending', 'filled', 'cancelled', 'rejected'
  alpacaOrderId: text("alpaca_order_id"),
  filledAt: timestamp("filled_at"),
  createdAt: timestamp("created_at").defaultNow(),
});

export const positions = pgTable("positions", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  accountId: varchar("account_id").references(() => accounts.id).notNull(),
  symbol: text("symbol").notNull(),
  quantity: integer("quantity").notNull(),
  avgPrice: text("avg_price").notNull(),
  marketValue: text("market_value"),
  unrealizedPl: text("unrealized_pl"),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const marketData = pgTable("market_data", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  symbol: text("symbol").notNull(),
  price: text("price").notNull(),
  change: text("change"),
  changePercent: text("change_percent"),
  volume: integer("volume"),
  timestamp: timestamp("timestamp").defaultNow(),
});

// Insert schemas
export const insertUserSchema = createInsertSchema(users).pick({
  username: true,
  password: true,
});

export const insertAccountSchema = createInsertSchema(accounts).pick({
  name: true,
  alpacaApiKey: true,
  alpacaSecretKey: true,
  isPaper: true,
});

export const insertStrategySchema = createInsertSchema(strategies).pick({
  name: true,
  type: true,
  symbols: true,
  parameters: true,
});

export const insertOrderSchema = createInsertSchema(orders).pick({
  symbol: true,
  side: true,
  quantity: true,
  orderType: true,
  price: true,
});

// Types
export type InsertUser = z.infer<typeof insertUserSchema>;
export type User = typeof users.$inferSelect;
export type InsertAccount = z.infer<typeof insertAccountSchema>;
export type Account = typeof accounts.$inferSelect;
export type InsertStrategy = z.infer<typeof insertStrategySchema>;
export type Strategy = typeof strategies.$inferSelect;
export type InsertOrder = z.infer<typeof insertOrderSchema>;
export type Order = typeof orders.$inferSelect;
export type Position = typeof positions.$inferSelect;
export type MarketData = typeof marketData.$inferSelect;

// WebSocket message types
export interface WebSocketMessage {
  type: 'terminal_output' | 'market_update' | 'portfolio_update' | 'order_update' | 'strategy_update' | 'strategy_executed' | 'strategy_stopped' | 'strategy_status_update' | 'strategy_completed' | 'countdown_update' | 'cycle_update';
  payload: any;
  timestamp?: string;
}

export interface TerminalCommand {
  command: string;
  clientId?: string;
}

export interface MarketStatus {
  isOpen: boolean;
  nextOpen?: string;
  nextClose?: string;
}

export interface AccountInfo {
  id: string;
  buyingPower: number;
  totalValue: number;
  dayChange: number;
  dayChangePercent: number;
}

export interface PortfolioSummary {
  totalValue: number;
  dayChange: number;
  dayChangePercent: number;
  buyingPower: number;
  positionCount: number;
}
