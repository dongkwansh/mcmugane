import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWebSocket } from "./websocket-provider";
import { getMessage } from "@/lib/messages";
import { useMutation } from "@tanstack/react-query";

interface TerminalProps {
  onCommandExecuted?: (command: string) => void;
}

export function TerminalInterface({ onCommandExecuted }: TerminalProps) {
  const [command, setCommand] = useState("");
  const [output, setOutput] = useState<string[]>([]);
  const [autoTradeMessages, setAutoTradeMessages] = useState<string[]>([]);
  const [strategyInfo, setStrategyInfo] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("자동매매 대기 중...");
  const { ws, isConnected, sendCommand } = useWebSocket();
  const outputRef = useRef<HTMLDivElement>(null);
  const autoTradeRef = useRef<HTMLDivElement>(null);

  // REST API fallback for terminal commands
  const terminalMutation = useMutation({
    mutationFn: async (command: string) => {
      const response = await fetch('/api/terminal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      });
      if (!response.ok) throw new Error('Failed to execute command');
      const data = await response.json();
      return data.result;
    },
    onSuccess: (result) => {
      if (result) {
        setOutput(prev => [...prev, result]);
      }
    },
    onError: (error) => {
      setOutput(prev => [...prev, `❌ 오류: ${error instanceof Error ? error.message : 'Unknown error'}`]);
    }
  });

  // Helper function to add auto-trade messages (max 3 lines)
  const addAutoTradeMessage = (message: string) => {
    setAutoTradeMessages(prev => {
      const newMessages = [message, ...prev];
      return newMessages.slice(0, 3); // Keep only latest 3 messages
    });
  };

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  useEffect(() => {
    if (autoTradeRef.current) {
      autoTradeRef.current.scrollTop = autoTradeRef.current.scrollHeight;
    }
  }, [autoTradeMessages]);

  useEffect(() => {
    if (ws) {
      ws.onMessage('terminal_output', (payload: string) => {
        setOutput(prev => [...prev, payload]);
      });

      // Listen for strategy execution events - only add to auto-trade messages
      ws.onMessage('strategy_executed', (payload: any) => {
        const time = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
        addAutoTradeMessage(`🚀 ${payload.strategyName} 시작 - ${time}`);
        setStatusMessage(`🚀 자동매매 시작됨: 사용자가 ${payload.strategyName} 전략을 실행했습니다`);
        
        // Update strategy info based on strategy name - fetch detailed JSON info
        const fetchStrategyInfo = async (strategyName: string) => {
          try {
            const response = await fetch('/api/strategies');
            const strategies = await response.json();
            const strategy = strategies[strategyName];
            
            if (strategy) {
              const params = strategy.parameters;
              let infoText = `${strategy.description}\n`;
              
              if (strategyName === 'Simple Buy') {
                infoText += `종목: ${params.symbols.join(', ')} | 수량: ${params.quantity}주 | 실행시간: ${params.executionTime}`;
              } else if (strategyName === 'SMA Cross') {
                infoText += `종목: ${params.symbols.join(', ')} | 단기MA: ${params.shortMA}일 | 장기MA: ${params.longMA}일 | 포트폴리오: ${params.portfolioRatio*100}%`;
              } else if (strategyName === 'RSI Mean') {
                infoText += `종목: ${params.symbols.join(', ')} | RSI기간: ${params.rsiPeriod}일 | 과매도: ${params.oversoldLevel} | 과매수: ${params.overboughtLevel}`;
              } else if (strategyName === 'Iron Condor') {
                infoText += `종목: ${params.symbol} | 계약수: ${params.contracts} | DTE: ${params.dte}일 | 숏델타: ±${params.shortDelta} | 목표수익: ${params.profitTarget*100}%`;
              } else if (strategyName === 'Covered Call') {
                infoText += `종목: ${params.symbol} | 보유주식: ${params.stockQuantity}주 | OTM: ${params.otmPercent*100}% | 최소프리미엄: ${params.minPremiumPercent*100}%`;
              } else if (strategyName === 'Bull Put Spread') {
                infoText += `종목: ${params.symbol} | 계약수: ${params.contracts} | 숏델타: ${params.shortDelta} | 스프레드폭: $${params.spreadWidth} | DTE: ${params.dte}일`;
              } else if (strategyName === 'TMF Test') {
                infoText += `종목: ${params.symbol} | 수량: ${params.quantity}주 | 최대라운드: ${params.maxRounds} | 매수→매도 대기: ${params.buyToSellDelay}초`;
              }
              
              setStrategyInfo(infoText);
            }
          } catch (error) {
            console.error('전략 정보 로딩 실패:', error);
            // Fallback to simple descriptions
            if (payload.strategyName === 'TMF Test') {
              setStrategyInfo(`TMF 테스트 전략: 5주씩 5회 반복, 매수→10초대기→매도→2초대기`);
            } else if (payload.strategyName === 'Simple Buy') {
              setStrategyInfo(`단순매수 전략: VOO,VTI,QQQ 각 10주씩 14:00 자동실행`);
            } else if (payload.strategyName === 'SMA Cross') {
              setStrategyInfo(`이동평균 교차 전략: 5일/20일 MA 기준, SPY,QQQ 50% 포트폴리오`);
            } else if (payload.strategyName === 'RSI Mean') {
              setStrategyInfo(`RSI 평균회귀 전략: RSI<30 매수, RSI>70 매도, TQQQ,SOXL 15주`);
            }
          }
        };
        
        fetchStrategyInfo(payload.strategyName);
      });

      ws.onMessage('order_update', (payload: any) => {
        const { order, action } = payload;
        if (action === 'created') {
          const emoji = order.side === 'buy' ? '📈' : '📉';
          const shortTime = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
          addAutoTradeMessage(`${emoji} ${order.symbol} ${order.quantity}주 ${order.side.toUpperCase()} - ${shortTime}`);
        }
      });

      ws.onMessage('strategy_completed', (payload: any) => {
        const shortTime = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
        addAutoTradeMessage(`✅ ${payload.strategyName} 완료 - ${shortTime}`);
        setStatusMessage(`✅ 자동매매 완료됨: ${payload.strategyName} 전략이 모든 라운드를 완료했습니다`);
        setStrategyInfo(""); // Clear strategy info when completed
      });

      ws.onMessage('strategy_stopped', (payload: any) => {
        const shortTime = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
        addAutoTradeMessage(`⏹️ ${payload.strategyName} 정지 - ${shortTime}`);
        setStatusMessage(`⏹️ 자동매매 정지됨: 사용자가 ${payload.strategyName} 전략을 중단했습니다`);
        setStrategyInfo(""); // Clear strategy info when stopped
      });

      // Listen for countdown events
      // 카운트다운과 자동매매 관련 메시지는 터미널에 표시하지 않음
      // 대신 자동매매 전용 상태창에서 처리됨
    }
  }, [ws]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (command.trim()) {
      setOutput(prev => [...prev, `$ ${command}`]);
      
      // Notify parent about command execution
      if (onCommandExecuted) {
        onCommandExecuted(command);
      }
      
      // Try WebSocket first, fallback to REST API
      if (isConnected) {
        sendCommand(command);
      } else {
        terminalMutation.mutate(command);
      }
      
      setCommand("");
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit(e);
    }
  };

  const handleClear = () => {
    setOutput([]);
  };

  const handleHelp = () => {
    const helpText = `
WealthCommander v2.1 - 사용 가능한 명령어:

📊 포트폴리오 관리:
- portfolio: 보유 종목 조회 
- list: MyETF 목록 조회
- list [myETF1|myETF2|myETF3|myETF4]: MyETF 상세 정보
- account [live|paper1|paper2|paper3]: 계정 변경

💰 거래 명령어:
- buy .TICKER [수량|비율|금액]: 매수
  • buy .AAPL 100 (100주 매수)
  • buy .TSLA 20% (구매력의 20%)
  • buy .NVDA $5000 (5,000달러 어치)
  • buy myETF1 (ETF 그룹 매수)
- sell .TICKER [수량|비율|all]: 매도
  • sell .AAPL 50 (50주 매도)
  • sell .TSLA 50% (보유량의 50%)
  • sell .NVDA all (전량 매도)

🛠️ 기타:
- cancel [all|orderID]: 주문 취소
- status: 시스템 상태 확인
- clear: 화면 지우기
- help: 이 도움말 표시
`;
    setOutput(prev => [...prev, helpText]);
  };

  return (
    <div className="h-full bg-black text-green-400 font-mono text-sm overflow-hidden" data-testid="terminal">
      <div className="h-full flex flex-col p-4">
        {/* Input area - 맨 위로 이동 */}
        <div className="mb-4 bg-gray-800 rounded border border-gray-600">
          <form onSubmit={handleSubmit} className="flex">
            <span className="text-green-400 px-3 py-2 bg-gray-900 border-r border-gray-600">&gt;</span>
            <Input
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              onKeyPress={handleKeyPress}
              className="flex-1 bg-transparent border-none text-white font-mono focus:ring-0 focus:outline-none"
              placeholder="명령어 입력 (help로 도움말 확인)"
              data-testid="terminal-input"
            />
            <Button 
              type="submit" 
              variant="ghost"
              size="sm"
              className="text-green-400 hover:text-green-300 hover:bg-gray-700"
              data-testid="terminal-submit"
            >
              실행
            </Button>
          </form>
        </div>

        {/* Terminal Controls - 입력창 바로 아래 */}
        <div className="flex space-x-2 mb-4">
          <Button 
            onClick={handleHelp}
            variant="ghost"
            size="sm"
            className="text-blue-400 hover:text-blue-300 hover:bg-gray-700 text-xs"
            data-testid="terminal-help"
          >
            도움말
          </Button>
          <Button 
            onClick={handleClear}
            variant="ghost"
            size="sm"
            className="text-yellow-400 hover:text-yellow-300 hover:bg-gray-700 text-xs"
            data-testid="terminal-clear"
          >
            지우기
          </Button>
        </div>
        
        <div 
          ref={outputRef}
          className="flex-1 mb-4 overflow-y-auto bg-black border border-gray-600 p-2 rounded min-h-[400px] max-h-[600px]"
          data-testid="terminal-output"
        >
          {output.map((line, index) => (
            <div key={index} className="text-sm mb-1 whitespace-pre-wrap flex">
              <span className="text-green-400 mr-2">&gt;</span>
              <span dangerouslySetInnerHTML={{ __html: line }}></span>
            </div>
          ))}
          <div className="flex items-center mt-2">
            <span className="text-green-400">&gt; </span>
            <span className="text-gray-400 ml-2 animate-pulse">_</span>
          </div>
        </div>
        
        {/* Auto-Trade Status Area - 하단으로 이동 */}
        <div className="mt-auto">
          <div className="flex items-center gap-2 mb-2">
            <h4 className="text-sm font-medium text-blue-400">자동매매 상태</h4>
          </div>
          <div 
            className="bg-blue-950 text-blue-100 p-3 rounded border border-blue-400 text-xs font-mono"
            data-testid="auto-trade-messages"
          >
            {/* Status Message */}
            <div className="text-blue-200 font-semibold mb-2">
              {statusMessage}
            </div>
            
            {/* Strategy Info Line */}
            {strategyInfo && (
              <div className="text-blue-300 mb-2 border-b border-blue-700 pb-1">
                {strategyInfo}
              </div>
            )}
            
            {/* Recent Messages - 2 lines max */}
            <div ref={autoTradeRef} className="h-8 overflow-hidden">
              {autoTradeMessages.slice(-2).map((message, index) => (
                <div 
                  key={index} 
                  className="mb-1 text-blue-100"
                >
                  {message}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}