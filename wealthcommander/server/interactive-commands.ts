import { storage } from "./storage";

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
  etfHoldings?: Array<{ symbol: string; percentage: number; quantity: number; price: number; total: number }>;
}

const clientStates = new Map<string, InteractiveState>();
let etfData: any = {};

// Load ETF data
export async function loadETFData() {
  try {
    const fs = await import('fs');
    const data = fs.readFileSync('data/myetf.json', 'utf8');
    etfData = JSON.parse(data);
  } catch (error) {
    console.error('Failed to load myETF.json:', error);
    etfData = {};
  }
}

// Helper function to calculate buying power percentage
function calculateBuyingPower(percentage: number): number {
  const buyingPower = 30840.66; // Current buying power
  return (buyingPower * percentage) / 100;
}

// Helper function to get mock current price
function getCurrentPrice(symbol: string): number {
  // Mock current prices for demonstration
  const prices: { [key: string]: number } = {
    'SOXL': 25.50,
    'QQQ': 380.25,
    'VGT': 450.75,
    'ARKK': 45.30,
    'SOXX': 210.80,
    'VOO': 420.15,
    'VTI': 245.60,
    'VXUS': 65.20,
    'NVDA': 850.40,
    'AMD': 145.80,
    'TSM': 105.25,
    'AAPL': 175.50,
    'MSFT': 415.30,
    'GOOGL': 135.80
  };
  return prices[symbol] || 100.00;
}

// Helper function to get portfolio holdings
function getPortfolioHoldings(symbol: string) {
  // Mock portfolio data
  const holdings: { [key: string]: { quantity: number; avgPrice: number } } = {
    'SOXL': { quantity: 20, avgPrice: 20.00 },
    'QQQ': { quantity: 50, avgPrice: 375.25 },
    'VOO': { quantity: 25, avgPrice: 410.50 },
    'VTI': { quantity: 40, avgPrice: 240.75 }
  };
  return holdings[symbol] || null;
}

// Helper function to parse quantity input
function parseQuantity(input: string, currentPrice: number, buyingPower?: number): { type: 'shares' | 'percentage' | 'dollars', value: number, shares?: number } {
  if (input.endsWith('%')) {
    const percentage = parseFloat(input.slice(0, -1));
    const dollarAmount = calculateBuyingPower(percentage);
    const shares = Math.floor(dollarAmount / currentPrice);
    return { type: 'percentage', value: percentage, shares };
  } else if (input.startsWith('$')) {
    const dollars = parseFloat(input.slice(1));
    const shares = Math.floor(dollars / currentPrice);
    return { type: 'dollars', value: dollars, shares };
  } else {
    const shares = parseFloat(input);
    return { type: 'shares', value: shares, shares };
  }
}

// Calculate ETF holdings with prices and totals
function calculateETFDetails(etfName: string, totalAmount: number) {
  const etf = etfData[etfName];
  if (!etf) return null;

  const holdings = etf.holdings.map((holding: any) => {
    const currentPrice = getCurrentPrice(holding.symbol);
    const dollarAmount = (totalAmount * holding.percentage) / 100;
    const quantity = Math.floor(dollarAmount / currentPrice);
    const actualTotal = quantity * currentPrice;
    
    return {
      symbol: holding.symbol,
      percentage: holding.percentage,
      quantity,
      price: currentPrice,
      total: actualTotal
    };
  });

  return holdings;
}

// Process interactive buy command
export async function processInteractiveBuy(
  command: string, 
  clientId: string, 
  broadcast: Function
): Promise<string> {
  const parts = command.split(' ');
  const cmd = parts[0].toLowerCase();
  
  if (cmd !== 'buy') return '';
  
  const currentState = clientStates.get(clientId) || { type: null, step: 0 };
  
  // Parse full buy command with arguments
  if (parts.length > 1) {
    const arg1 = parts[1];
    const arg2 = parts[2];
    const arg3 = parts[3];
    
    // Direct buy command: buy .TICKER [QUANTITY] [PRICE]
    if (arg1?.startsWith('.')) {
      const ticker = arg1.slice(1).toUpperCase();
      const currentPrice = getCurrentPrice(ticker);
      
      // buy .TICKER - ask for quantity and price
      if (!arg2) {
        clientStates.set(clientId, { 
          type: 'buy', 
          step: 2, 
          ticker,
          isETF: false 
        });
        return `매수 수량:`;
      }
      
      // buy .TICKER QUANTITY - ask for price
      if (!arg3) {
        const quantityInfo = parseQuantity(arg2, currentPrice);
        clientStates.set(clientId, { 
          type: 'buy', 
          step: 3, 
          ticker,
          quantity: quantityInfo.shares || quantityInfo.value,
          isETF: false 
        });
        return `매수 가격:`;
      }
      
      // buy .TICKER QUANTITY PRICE - execute directly
      const quantityInfo = parseQuantity(arg2, currentPrice);
      const price = parseFloat(arg3);
      const quantity = quantityInfo.shares || quantityInfo.value;
      
      clientStates.delete(clientId);
      return `${ticker} ${quantity}주를 $${price}에 매수합니다. (y/N)`;
    }
    
    // ETF buy command: buy myETF1 [AMOUNT]
    if (etfData[arg1]) {
      const etfName = arg1;
      const amount = arg2 ? parseFloat(arg2.replace('$', '')) : null;
      
      if (!amount) {
        clientStates.set(clientId, { 
          type: 'buy', 
          step: 2, 
          etfName,
          isETF: true 
        });
        return `매수 금액 ($):`;
      }
      
      // Calculate ETF breakdown
      const holdings = calculateETFDetails(etfName, amount);
      if (!holdings) {
        return `ETF ${etfName}을 찾을 수 없습니다.`;
      }
      
      let response = '종목 | 수량 | 가격 | 총액\n';
      response += '────────────────────────\n';
      let totalCost = 0;
      
      holdings.forEach(holding => {
        response += `${holding.symbol} | ${holding.quantity} | $${holding.price.toFixed(2)} | $${holding.total.toFixed(2)}\n`;
        totalCost += holding.total;
      });
      
      response += `\n총합 $${totalCost.toFixed(2)} 매수합니다. (y/N)`;
      clientStates.delete(clientId);
      return response;
    }
  }
  
  // If no arguments, start interactive mode
  clientStates.set(clientId, { type: 'buy', step: 1 });
  return '.{TICKER} 또는 myETF를 입력하세요:';
}

// Process interactive sell command
export async function processInteractiveSell(
  command: string, 
  clientId: string, 
  broadcast: Function
): Promise<string> {
  const parts = command.split(' ');
  const cmd = parts[0].toLowerCase();
  
  if (cmd !== 'sell') return '';
  
  const currentState = clientStates.get(clientId) || { type: null, step: 0 };
  
  // Parse full sell command with arguments
  if (parts.length > 1) {
    const arg1 = parts[1];
    const arg2 = parts[2];
    const arg3 = parts[3];
    
    // Direct sell command: sell .TICKER [QUANTITY] [PRICE]
    if (arg1?.startsWith('.')) {
      const ticker = arg1.slice(1).toUpperCase();
      const holdings = getPortfolioHoldings(ticker);
      
      if (!holdings) {
        return `${ticker} 보유 종목이 없습니다.`;
      }
      
      // sell .TICKER - show holdings and ask for quantity
      if (!arg2) {
        clientStates.set(clientId, { 
          type: 'sell', 
          step: 2, 
          ticker,
          isETF: false 
        });
        return `보유 수량: ${holdings.quantity}       평균 단가: $${holdings.avgPrice.toFixed(2)}\n매도 수량:`;
      }
      
      // Handle 'all' keyword
      if (arg2 === 'all') {
        const price = arg3 ? parseFloat(arg3) : getCurrentPrice(ticker);
        clientStates.delete(clientId);
        return `${ticker} ${holdings.quantity}주를 $${price}에 매도합니다. (y/N)`;
      }
      
      // sell .TICKER QUANTITY - ask for price
      if (!arg3) {
        let quantity: number;
        
        if (arg2.endsWith('%')) {
          const percentage = parseFloat(arg2.slice(0, -1));
          quantity = Math.floor((holdings.quantity * percentage) / 100);
        } else {
          quantity = parseFloat(arg2);
        }
        
        clientStates.set(clientId, { 
          type: 'sell', 
          step: 3, 
          ticker,
          quantity,
          isETF: false 
        });
        return `매도 가격:`;
      }
      
      // sell .TICKER QUANTITY PRICE - execute directly
      let quantity: number;
      
      if (arg2.endsWith('%')) {
        const percentage = parseFloat(arg2.slice(0, -1));
        quantity = Math.floor((holdings.quantity * percentage) / 100);
      } else {
        quantity = parseFloat(arg2);
      }
      
      const price = parseFloat(arg3);
      
      clientStates.delete(clientId);
      return `${ticker} ${quantity}주를 $${price}에 매도합니다. (y/N)`;
    }
    
    // ETF sell command: sell myETF1 [all]
    if (etfData[arg1]) {
      const etfName = arg1;
      
      // Mock ETF holdings data
      const etfHoldings = [
        { symbol: 'QQQ', quantity: 15, avgPrice: 375.25, currentPrice: 380.25 },
        { symbol: 'VGT', quantity: 8, avgPrice: 445.75, currentPrice: 450.75 },
        { symbol: 'ARKK', quantity: 25, avgPrice: 42.30, currentPrice: 45.30 },
        { symbol: 'SOXX', quantity: 3, avgPrice: 205.80, currentPrice: 210.80 }
      ];
      
      let response = '종목 | 보유수량 | 평균가격 | 현재가격 | 총액\n';
      response += '──────────────────────────────────────\n';
      let totalValue = 0;
      
      etfHoldings.forEach(holding => {
        const total = holding.quantity * holding.currentPrice;
        response += `${holding.symbol} | ${holding.quantity} | $${holding.avgPrice.toFixed(2)} | $${holding.currentPrice.toFixed(2)} | $${total.toFixed(2)}\n`;
        totalValue += total;
      });
      
      response += `\n총합 $${totalValue.toFixed(2)} 매도합니다. (y/N)`;
      clientStates.delete(clientId);
      return response;
    }
  }
  
  // If no arguments, start interactive mode
  clientStates.set(clientId, { type: 'sell', step: 1 });
  return '.{TICKER} 또는 myETF를 입력하세요:';
}

// Handle interactive responses
export async function handleInteractiveResponse(
  input: string,
  clientId: string,
  broadcast: Function
): Promise<string> {
  const state = clientStates.get(clientId);
  
  if (!state || !state.type) {
    return '';
  }
  
  if (state.type === 'buy') {
    switch (state.step) {
      case 1: // Waiting for ticker or ETF input
        if (input.startsWith('.')) {
          const ticker = input.slice(1).toUpperCase();
          // Validate ticker exists (simple validation)
          if (ticker === 'PARKPAR') {
            return '존재하지 않는 티커입니다.\n\n.{TICKER} 또는 myETF를 입력하세요:';
          }
          
          clientStates.set(clientId, { 
            type: 'buy', 
            step: 2, 
            ticker,
            isETF: false 
          });
          return '매수 수량:';
        } else if (etfData[input]) {
          clientStates.set(clientId, { 
            type: 'buy', 
            step: 2, 
            etfName: input,
            isETF: true 
          });
          return '매수 금액 ($):';
        } else {
          return '존재하지 않는 티커입니다.\n\n.{TICKER} 또는 myETF를 입력하세요:';
        }
        
      case 2: // Waiting for quantity/amount
        if (state.isETF) {
          const amount = parseFloat(input.replace('$', ''));
          const holdings = calculateETFDetails(state.etfName!, amount);
          
          if (!holdings) {
            clientStates.delete(clientId);
            return `ETF ${state.etfName}을 찾을 수 없습니다.`;
          }
          
          let response = '종목 | 수량 | 가격 | 총액\n';
          response += '────────────────────────\n';
          let totalCost = 0;
          
          holdings.forEach(holding => {
            response += `${holding.symbol} | ${holding.quantity} | $${holding.price.toFixed(2)} | $${holding.total.toFixed(2)}\n`;
            totalCost += holding.total;
          });
          
          response += `\n총합 $${totalCost.toFixed(2)} 매수합니다. (y/N)`;
          clientStates.delete(clientId);
          return response;
          
        } else {
          const currentPrice = getCurrentPrice(state.ticker!);
          const quantityInfo = parseQuantity(input, currentPrice);
          
          clientStates.set(clientId, { 
            ...state, 
            step: 3, 
            quantity: quantityInfo.shares || quantityInfo.value 
          });
          return '매수 가격:';
        }
        
      case 3: // Waiting for price
        const price = parseFloat(input);
        const quantity = state.quantity!;
        const ticker = state.ticker!;
        
        clientStates.delete(clientId);
        return `${ticker} ${quantity}주를 $${price}에 매수합니다. (y/N)`;
        
      default:
        clientStates.delete(clientId);
        return '명령이 취소되었습니다.';
    }
  }
  
  if (state.type === 'sell') {
    switch (state.step) {
      case 1: // Waiting for ticker or ETF input
        if (input.startsWith('.')) {
          const ticker = input.slice(1).toUpperCase();
          const holdings = getPortfolioHoldings(ticker);
          
          if (!holdings) {
            return `${ticker} 보유 종목이 없습니다.\n\n.{TICKER} 또는 myETF를 입력하세요:`;
          }
          
          clientStates.set(clientId, { 
            type: 'sell', 
            step: 2, 
            ticker,
            isETF: false 
          });
          return `보유 수량: ${holdings.quantity}       평균 단가: $${holdings.avgPrice.toFixed(2)}\n매도 수량:`;
          
        } else if (etfData[input]) {
          // Mock ETF holdings data
          const etfHoldings = [
            { symbol: 'QQQ', quantity: 15, avgPrice: 375.25, currentPrice: getCurrentPrice('QQQ') },
            { symbol: 'VGT', quantity: 8, avgPrice: 445.75, currentPrice: getCurrentPrice('VGT') },
            { symbol: 'ARKK', quantity: 25, avgPrice: 42.30, currentPrice: getCurrentPrice('ARKK') },
            { symbol: 'SOXX', quantity: 3, avgPrice: 205.80, currentPrice: getCurrentPrice('SOXX') }
          ];
          
          let response = '종목 | 보유수량 | 평균가격 | 현재가격 | 총액\n';
          response += '──────────────────────────────────────\n';
          let totalValue = 0;
          
          etfHoldings.forEach(holding => {
            const total = holding.quantity * holding.currentPrice;
            response += `${holding.symbol} | ${holding.quantity} | $${holding.avgPrice.toFixed(2)} | $${holding.currentPrice.toFixed(2)} | $${total.toFixed(2)}\n`;
            totalValue += total;
          });
          
          response += `\n총합 $${totalValue.toFixed(2)} 매도합니다. (y/N)`;
          clientStates.delete(clientId);
          return response;
          
        } else {
          return '존재하지 않는 티커입니다.\n\n.{TICKER} 또는 myETF를 입력하세요:';
        }
        
      case 2: // Waiting for quantity
        const ticker = state.ticker!;
        const holdings = getPortfolioHoldings(ticker);
        
        if (!holdings) {
          clientStates.delete(clientId);
          return `${ticker} 보유 종목이 없습니다.`;
        }
        
        let quantity: number;
        
        if (input === 'all') {
          quantity = holdings.quantity;
        } else if (input.endsWith('%')) {
          const percentage = parseFloat(input.slice(0, -1));
          quantity = Math.floor((holdings.quantity * percentage) / 100);
        } else {
          quantity = parseFloat(input);
        }
        
        clientStates.set(clientId, { 
          ...state, 
          step: 3, 
          quantity 
        });
        return '매도 가격:';
        
      case 3: // Waiting for price
        const sellPrice = parseFloat(input);
        const sellQuantity = state.quantity!;
        const sellTicker = state.ticker!;
        
        clientStates.delete(clientId);
        return `${sellTicker} ${sellQuantity}주를 $${sellPrice}에 매도합니다. (y/N)`;
        
      default:
        clientStates.delete(clientId);
        return '명령이 취소되었습니다.';
    }
  }
  
  return '';
}

// Handle confirmation responses (y/N)
export async function handleConfirmation(
  input: string,
  clientId: string,
  broadcast: Function
): Promise<string> {
  const lowerInput = input.toLowerCase();
  
  if (lowerInput === 'y' || lowerInput === 'yes') {
    // Execute the trade
    return '주문이 실행되었습니다.';
  } else if (lowerInput === 'n' || lowerInput === 'no') {
    return '주문이 취소되었습니다.';
  }
  
  return '';
}

// Clear client state
export function clearClientState(clientId: string) {
  clientStates.delete(clientId);
}

// Get current client state
export function getClientState(clientId: string): InteractiveState | null {
  return clientStates.get(clientId) || null;
}

// Initialize ETF data on startup
loadETFData();