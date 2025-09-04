import { promises as fs } from 'fs';
import { join } from 'path';

interface LogEntry {
  timestamp: string;
  type: 'strategy_execution' | 'order_created' | 'order_filled' | 'strategy_completed' | 'strategy_stopped' | 'system_event' | 'login_attempt' | 'login_success' | 'login_failure';
  data: Record<string, any>;
}

class JSONLLogger {
  private logDir: string;
  
  constructor(baseDir: string = 'logs') {
    this.logDir = baseDir;
  }
  
  private getLogSubDirectory(type: LogEntry['type']): string {
    if (type === 'login_attempt' || type === 'login_success' || type === 'login_failure') {
      return 'logins';
    }
    return 'statements';
  }

  private async ensureLogDirectory(datePath: string, subDir: string): Promise<void> {
    const fullPath = join(this.logDir, subDir, datePath);
    try {
      await fs.access(fullPath);
    } catch {
      await fs.mkdir(fullPath, { recursive: true });
    }
  }

  private getFilePath(date: Date): { datePath: string; fileName: string } {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hour = date.getHours();
    
    // Calculate hour range (e.g., 09:30-10:00)
    const startHour = String(hour).padStart(2, '0');
    const endHour = String(hour + 1).padStart(2, '0');
    
    // Get month name
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const monthName = monthNames[date.getMonth()];
    
    const datePath = `${year}/${month}-${day}`;
    const fileName = `${startHour}_30-${endHour}_00_${monthName}_${day}_${year}.jsonl`;
    
    return { datePath, fileName };
  }

  async log(type: LogEntry['type'], data: Record<string, any>): Promise<void> {
    try {
      const now = new Date();
      const { datePath, fileName } = this.getFilePath(now);
      const subDir = this.getLogSubDirectory(type);
      
      // Ensure directory exists
      await this.ensureLogDirectory(datePath, subDir);
      
      const logEntry: LogEntry = {
        timestamp: now.toISOString(),
        type,
        data
      };
      
      const logLine = JSON.stringify(logEntry) + '\n';
      const filePath = join(this.logDir, subDir, datePath, fileName);
      
      // Append to file
      await fs.appendFile(filePath, logLine, 'utf8');
      
      console.log(`[JSONL Logger] Logged ${type} to ${filePath}`);
    } catch (error) {
      console.error('Failed to write log entry:', error);
    }
  }

  // Convenience methods for different log types
  async logStrategyExecution(strategyName: string, config: any, accountId: string): Promise<void> {
    await this.log('strategy_execution', {
      strategyName,
      config,
      accountId,
      action: 'started'
    });
  }

  async logStrategyCompletion(strategyName: string, summary: any): Promise<void> {
    await this.log('strategy_completed', {
      strategyName,
      summary,
      action: 'completed'
    });
  }

  async logStrategyStopped(strategyName: string, reason?: string): Promise<void> {
    await this.log('strategy_stopped', {
      strategyName,
      reason: reason || 'manual_stop',
      action: 'stopped'
    });
  }

  async logOrderCreated(order: any): Promise<void> {
    await this.log('order_created', {
      orderId: order.id,
      symbol: order.symbol,
      side: order.side,
      quantity: order.quantity,
      orderType: order.orderType,
      accountId: order.accountId,
      strategyId: order.strategyId,
      price: order.price
    });
  }

  async logOrderFilled(orderId: string, fillPrice: number, fillTime: string): Promise<void> {
    await this.log('order_filled', {
      orderId,
      fillPrice,
      fillTime,
      action: 'filled'
    });
  }

  async logSystemEvent(event: string, details: Record<string, any>): Promise<void> {
    await this.log('system_event', {
      event,
      details
    });
  }
  
  async logLoginAttempt(username: string, success: boolean, ip?: string, userAgent?: string): Promise<void> {
    const logType = success ? 'login_success' : 'login_failure';
    await this.log(logType, {
      username,
      success,
      ip,
      userAgent,
      action: success ? 'login_success' : 'login_failure'
    });
  }
}

// Export singleton instance
export const logger = new JSONLLogger();