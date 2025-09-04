import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Square, Settings } from "lucide-react";
import { getMessage } from "@/lib/messages";

interface Strategy {
  id: string;
  name: string;
  type: string;
  symbols: string[];
  isActive: boolean;
  parameters: any;
}

export function StrategyManager() {
  const { data: strategies = [] } = useQuery<Strategy[]>({
    queryKey: ['/api/strategies'],
    refetchInterval: 10000,
  });

  const getStrategyTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      'simple_buy': '단순 매수',
      'sma_crossover': 'SMA 교차',
      'rsi_mean_reversion': 'RSI 평균회귀',
      'breakout_donchian': '돌파 도치안'
    };
    return labels[type] || type;
  };

  const toggleStrategy = async (strategyId: string, isActive: boolean) => {
    try {
      // TODO: Implement strategy toggle API call
      console.log(`Toggle strategy ${strategyId} to ${!isActive}`);
    } catch (error) {
      console.error('Failed to toggle strategy:', error);
    }
  };

  return (
    <Card className="bg-card border-border" data-testid="strategy-manager">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>전략 관리</span>
          <Button size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90" data-testid="add-new-strategy">
            <Settings className="h-4 w-4 mr-2" />
            새 전략
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {strategies.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground" data-testid="no-strategies">
            활성 전략이 없습니다.
          </div>
        ) : (
          <div className="space-y-4">
            {strategies.map((strategy) => (
              <div 
                key={strategy.id} 
                className="flex items-center justify-between p-4 bg-secondary rounded-lg border border-border"
                data-testid={`strategy-card-${strategy.id}`}
              >
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h4 className="font-medium">{strategy.name}</h4>
                    <Badge variant={strategy.isActive ? "default" : "secondary"} data-testid={`strategy-status-${strategy.id}`}>
                      {strategy.isActive ? '실행중' : '정지'}
                    </Badge>
                  </div>
                  
                  <div className="text-sm text-muted-foreground mb-2">
                    <span className="font-medium">유형:</span> {getStrategyTypeLabel(strategy.type)}
                  </div>
                  
                  {strategy.symbols && strategy.symbols.length > 0 && (
                    <div className="text-sm text-muted-foreground">
                      <span className="font-medium">종목:</span> {strategy.symbols.join(', ')}
                    </div>
                  )}
                </div>
                
                <div className="flex items-center space-x-2">
                  <Button
                    size="sm"
                    variant={strategy.isActive ? "destructive" : "default"}
                    onClick={() => toggleStrategy(strategy.id, strategy.isActive)}
                    data-testid={`toggle-strategy-${strategy.id}`}
                  >
                    {strategy.isActive ? (
                      <>
                        <Square className="h-4 w-4 mr-1" />
                        정지
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-1" />
                        시작
                      </>
                    )}
                  </Button>
                  
                  <Button
                    size="sm"
                    variant="outline"
                    data-testid={`configure-strategy-${strategy.id}`}
                  >
                    <Settings className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
