import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowUp, ArrowDown, XCircle, Pause, Plus } from "lucide-react";
import { getMessage } from "@/lib/messages";

interface PortfolioData {
  totalValue: number;
  dayChange: number;
  dayChangePercent: number;
  buyingPower: number;
  positionCount: number;
}

interface StatusData {
  portfolio?: PortfolioData;
}

interface Strategy {
  id: string;
  name: string;
  symbols?: string[];
  isActive: boolean;
}

export function PortfolioSummary() {
  const { data: status } = useQuery<StatusData>({
    queryKey: ['/api/status'],
    refetchInterval: 5000,
  });

  const portfolio: PortfolioData = status?.portfolio || {
    totalValue: 0,
    dayChange: 0,
    dayChangePercent: 0,
    buyingPower: 0,
    positionCount: 0
  };

  const { data: strategies = [] } = useQuery<Strategy[]>({
    queryKey: ['/api/strategies'],
    refetchInterval: 10000,
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatChange = (change: number, percent: number) => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${formatCurrency(change)} (${sign}${percent.toFixed(2)}%)`;
  };

  return (
    <div className="space-y-6">
      {/* Portfolio Summary */}
      <Card className="bg-secondary" data-testid="portfolio-summary">
        <CardHeader>
          <CardTitle>{getMessage('portfolio_summary')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-sm text-muted-foreground">{getMessage('total_value')}</div>
              <div className="font-bold" data-testid="total-value">
                {formatCurrency(portfolio.totalValue)}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">{getMessage('day_change')}</div>
              <div className={`font-bold ${portfolio.dayChange >= 0 ? 'gain' : 'loss'}`} data-testid="day-change">
                {formatChange(portfolio.dayChange, portfolio.dayChangePercent)}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">{getMessage('buying_power')}</div>
              <div className="font-bold" data-testid="buying-power">
                {formatCurrency(portfolio.buyingPower)}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">{getMessage('positions')}</div>
              <div className="font-bold" data-testid="position-count">
                {portfolio.positionCount}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Active Strategies */}
      <Card className="bg-secondary" data-testid="active-strategies">
        <CardHeader>
          <CardTitle>{getMessage('active_strategies')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {strategies.map((strategy: any) => (
              <div key={strategy.id} className="flex items-center justify-between p-3 bg-muted rounded-md" data-testid={`strategy-${strategy.id}`}>
                <div>
                  <div className="font-medium">{strategy.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {strategy.symbols?.join(', ') || 'No symbols'}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`status-indicator ${strategy.isActive ? 'status-online' : 'status-offline'}`}></span>
                  <Button 
                    variant="destructive" 
                    size="sm"
                    data-testid={`stop-strategy-${strategy.id}`}
                  >
                    <XCircle className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
          
          <Button className="w-full mt-4 bg-primary text-primary-foreground hover:bg-primary/90" data-testid="add-strategy">
            <Plus className="h-4 w-4 mr-2" />
            {getMessage('add_strategy')}
          </Button>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Card className="bg-secondary" data-testid="quick-actions">
        <CardHeader>
          <CardTitle>{getMessage('quick_actions')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            <Button className="bg-primary text-primary-foreground hover:bg-primary/90" data-testid="quick-buy">
              <ArrowUp className="h-4 w-4 mr-1" />
              {getMessage('buy')}
            </Button>
            <Button className="bg-destructive text-destructive-foreground hover:bg-destructive/90" data-testid="quick-sell">
              <ArrowDown className="h-4 w-4 mr-1" />
              {getMessage('sell')}
            </Button>
            <Button className="bg-accent text-accent-foreground hover:bg-accent/90" data-testid="close-all">
              <XCircle className="h-4 w-4 mr-1" />
              {getMessage('close_all')}
            </Button>
            <Button className="bg-muted text-muted-foreground hover:bg-muted/90" data-testid="pause-all">
              <Pause className="h-4 w-4 mr-1" />
              {getMessage('pause_all')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
