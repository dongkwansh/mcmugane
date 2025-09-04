import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWebSocket } from "./websocket-provider";
import { useEffect, useState } from "react";
import { getMessage } from "@/lib/messages";

interface MarketDataItem {
  symbol: string;
  price: number | string;
  change: number | string;
  changePercent: number | string;
  volume?: number;
}

export function MarketData() {
  const { data: initialData = [] } = useQuery<MarketDataItem[]>({
    queryKey: ['/api/market-data'],
    refetchInterval: 10000,
  });

  const [marketData, setMarketData] = useState<MarketDataItem[]>([]);
  const { ws } = useWebSocket();

  // Use useEffect with proper dependency to sync with initialData
  useEffect(() => {
    if (initialData && initialData.length > 0) {
      setMarketData(initialData);
    }
  }, [JSON.stringify(initialData)]); // Use JSON.stringify to create stable dependency

  useEffect(() => {
    if (ws) {
      ws.onMessage('market_update', (payload: MarketDataItem[]) => {
        setMarketData(payload);
      });
    }
  }, [ws]);

  const formatPrice = (price: number | string) => {
    const priceNum = typeof price === 'string' ? parseFloat(price) : price;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(priceNum);
  };

  const formatChange = (change: number | string, percent: number | string) => {
    const changeNum = typeof change === 'string' ? parseFloat(change) : change;
    const percentNum = typeof percent === 'string' ? parseFloat(percent) : percent;
    const sign = changeNum >= 0 ? '+' : '';
    return {
      change: `${sign}${changeNum.toFixed(2)}`,
      percent: `${sign}${percentNum.toFixed(2)}%`
    };
  };

  const getCompanyName = (symbol: string) => {
    const names: Record<string, string> = {
      'AAPL': 'Apple Inc.',
      'TSLA': 'Tesla Inc.',
      'MSFT': 'Microsoft Corp.',
      'GOOGL': 'Alphabet Inc.',
      'AMZN': 'Amazon.com Inc.'
    };
    return names[symbol] || symbol;
  };

  const getSymbolColor = (index: number) => {
    const colors = ['bg-primary', 'bg-accent', 'bg-chart-1', 'bg-chart-2', 'bg-chart-3'];
    return colors[index % colors.length];
  };

  // Mock market indices data
  const marketIndices = [
    { name: 'S&P 500', value: 4567.89, change: 0.75 },
    { name: 'NASDAQ', value: 14234.56, change: 1.23 },
    { name: 'Dow Jones', value: 34987.12, change: -0.45 }
  ];

  return (
    <Card className="bg-card border-border" data-testid="market-data">
      <CardHeader>
        <CardTitle>{getMessage('market_data')}</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Watchlist */}
        <div className="space-y-3" data-testid="watchlist">
          {marketData.map((stock, index) => (
            <div 
              key={stock.symbol} 
              className="flex items-center justify-between p-3 bg-secondary rounded-md hover:bg-secondary/80 transition-colors"
              data-testid={`stock-${stock.symbol}`}
            >
              <div className="flex items-center space-x-3">
                <div className={`w-8 h-8 ${getSymbolColor(index)} rounded-full flex items-center justify-center text-xs font-bold`}>
                  {stock.symbol}
                </div>
                <div>
                  <div className="font-medium">{getCompanyName(stock.symbol)}</div>
                  <div className="text-sm text-muted-foreground">NASDAQ</div>
                </div>
              </div>
              <div className="text-right">
                <div className="font-bold" data-testid={`price-${stock.symbol}`}>
                  {formatPrice(stock.price)}
                </div>
                <div className={`text-sm ${(typeof stock.change === 'string' ? parseFloat(stock.change) : stock.change) >= 0 ? 'gain' : 'loss'}`} data-testid={`change-${stock.symbol}`}>
                  {formatChange(stock.change, stock.changePercent).change} ({formatChange(stock.change, stock.changePercent).percent})
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Market Indices */}
        <div className="mt-6 pt-4 border-t border-border" data-testid="market-indices">
          <h3 className="font-semibold mb-3">{getMessage('market_indices')}</h3>
          <div className="grid grid-cols-1 gap-2">
            {marketIndices.map((index) => (
              <div key={index.name} className="flex justify-between items-center" data-testid={`index-${index.name.replace(/\s+/g, '-').toLowerCase()}`}>
                <span className="text-sm text-muted-foreground">{index.name}</span>
                <div className="text-right">
                  <span className="font-medium">{index.value.toLocaleString()}</span>
                  <span className={`text-sm ml-2 ${index.change >= 0 ? 'gain' : 'loss'}`}>
                    {index.change >= 0 ? '+' : ''}{index.change.toFixed(2)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
