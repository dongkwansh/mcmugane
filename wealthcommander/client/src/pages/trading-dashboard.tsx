import { useQuery } from "@tanstack/react-query";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TerminalInterface } from "@/components/terminal-interface";
import { Play, Square, Settings } from "lucide-react";
import { getMessage } from "@/lib/messages";
import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useWebSocket } from "@/components/websocket-provider";

export default function TradingDashboard() {
  const { data: status } = useQuery({
    queryKey: ["/api/status"],
    refetchInterval: 5000,
  });
  
  const { data: marketData = [] } = useQuery({
    queryKey: ["/api/market-data"],
    refetchInterval: 10000,
  });

  const [selectedStrategy, setSelectedStrategy] = useState<string>('Simple Buy');
  const [strategySettings, setStrategySettings] = useState({
    targetSymbols: 'VOO, VTI, QQQ',
    portfolioRatio: '단순 매수 전략',
    priceGap: '지정의 30%',
    executionTime: '매일 14:00',
    timezone: 'America/New_York',
    enabled: true
  });
  const [isStrategyRunning, setIsStrategyRunning] = useState(false);
  const { ws } = useWebSocket();
  const [strategyStatus, setStrategyStatus] = useState({
    lastExecution: null as string | null,
    nextExecution: '14:00',
    totalExecutions: 0
  });
  const [commandHistory, setCommandHistory] = useState<Array<{command: string, time: string}>>([]);
  const [isStrategyInfoExpanded, setIsStrategyInfoExpanded] = useState(false);
  const [strategyDetails, setStrategyDetails] = useState<any>(null);
  const [selectedAccount, setSelectedAccount] = useState<string>('paper-account-1');
  const [availableStrategies, setAvailableStrategies] = useState<string[]>([]);
  const [tradingMessages, setTradingMessages] = useState<string[]>([]);
  const [currentCountdown, setCurrentCountdown] = useState<string>('');

  // Strategy control mutation
  const strategyMutation = useMutation({
    mutationFn: async ({ action, strategyName }: { action: 'start' | 'stop', strategyName: string }) => {
      const response = await fetch(`/api/strategy/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategyName })
      });
      if (!response.ok) throw new Error('Strategy action failed');
      return response.json();
    },
    onSuccess: (data) => {
      console.log('Strategy action result:', data);
    },
    onError: (error) => {
      console.error('Strategy action failed:', error);
    }
  });

  const handleStrategyToggle = () => {
    const action = isStrategyRunning ? 'stop' : 'start';
    strategyMutation.mutate({ action, strategyName: selectedStrategy });
    setIsStrategyRunning(!isStrategyRunning);
  };

  // Load available strategies on component mount
  useEffect(() => {
    const loadStrategies = async () => {
      try {
        const response = await fetch('/api/strategies');
        const strategies = await response.json();
        const strategyNames = Object.keys(strategies);
        setAvailableStrategies(strategyNames);
        
        // Set first strategy as default if current selection is not available
        if (strategyNames.length > 0 && !strategyNames.includes(selectedStrategy)) {
          setSelectedStrategy(strategyNames[0]);
        }
      } catch (error) {
        console.error('Failed to load strategies:', error);
      }
    };
    
    loadStrategies();
  }, []);

  // Load strategy details when selection changes
  useEffect(() => {
    const loadStrategyDetails = async () => {
      try {
        const response = await fetch('/api/strategies');
        const strategies = await response.json();
        setStrategyDetails(strategies[selectedStrategy]);
      } catch (error) {
        console.error('Failed to load strategy details:', error);
      }
    };
    
    if (selectedStrategy) {
      loadStrategyDetails();
    }
  }, [selectedStrategy]);

  // Listen for strategy status updates
  useEffect(() => {
    if (ws) {
      ws.onMessage('strategy_status_update', (payload: any) => {
        if (payload.strategyName === selectedStrategy) {
          setIsStrategyRunning(payload.isRunning);
        }
      });
      
      ws.onMessage('strategy_executed', (payload: any) => {
        if (payload.strategyName === selectedStrategy) {
          setStrategyStatus(prev => ({
            ...prev,
            lastExecution: new Date().toLocaleTimeString('ko-KR', { hour12: false }),
            totalExecutions: prev.totalExecutions + 1
          }));
        }
      });
      
      ws.onMessage('strategy_stopped', (payload: any) => {
        if (payload.strategyName === selectedStrategy) {
          setIsStrategyRunning(false);
        }
      });
      
      ws.onMessage('strategy_completed', (payload: any) => {
        if (payload.strategyName === selectedStrategy) {
          setIsStrategyRunning(false);
        }
      });

      ws.onMessage('strategy_executed', (payload: any) => {
        if (payload.strategyName === selectedStrategy) {
          setIsStrategyRunning(true);
        }
      });

      ws.onMessage('strategy_completed', (payload: any) => {
        if (payload.strategyName === selectedStrategy) {
          setIsStrategyRunning(false);
        }
      });

      ws.onMessage('strategy_stopped', (payload: any) => {
        if (payload.strategyName === selectedStrategy) {
          setIsStrategyRunning(false);
        }
      });

      // 자동매매 전용 상태창을 위한 이벤트 리스너
      ws.onMessage('countdown_update', (payload: any) => {
        const { seconds, action } = payload;
        if (seconds > 0) {
          setCurrentCountdown(`⏱️ ${action} 까지 ${seconds}초...`);
        } else {
          setCurrentCountdown(`⚡ ${action} 실행!`);
          setTimeout(() => setCurrentCountdown(''), 2000); // 2초 후 메시지 제거
        }
      });

      ws.onMessage('cycle_update', (payload: any) => {
        const { currentRound, totalRounds, message } = payload;
        const time = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
        setTradingMessages(prev => [`[${time}] 🔄 ${message} (${currentRound}/${totalRounds})`, ...prev.slice(0, 4)]);
      });
    }
  }, [ws, selectedStrategy]);

  const handleCommandExecuted = (command: string) => {
    const time = new Date().toLocaleTimeString('ko-KR', { hour12: false, hour: '2-digit', minute: '2-digit' });
    setCommandHistory(prev => [...prev, { command: command.toLowerCase(), time }]);
  };

  return (
    <div className="flex h-screen bg-gray-900 text-white" data-testid="trading-dashboard">
      {/* Left Sidebar */}
      <div className="w-80 bg-gray-800 flex flex-col">
        {/* Account Info Section - Blue */}
        <div className="bg-blue-900/30 border border-blue-500/30 m-2 rounded" data-testid="account-section">
          <div className="bg-blue-600 text-white px-3 py-1 text-sm font-medium flex items-center">
            <span className="mr-2">💼</span> 계좌 정보
          </div>
          <div className="p-3 space-y-2 text-xs">
            {/* Account Selection */}
            <div className="space-y-1">
              <label className="text-blue-300 text-xs font-medium">계좌 선택:</label>
              <select 
                value={selectedAccount} 
                onChange={(e) => setSelectedAccount(e.target.value)}
                className="w-full bg-blue-950 border border-blue-500/50 text-white text-xs rounded px-2 py-1"
                data-testid="account-select"
              >
                <option value="live-account-1">Live Account</option>
                <option value="paper-account-1">Paper Account #1</option>
                <option value="paper-account-2">Paper Account #2</option>
                <option value="paper-account-3">Paper Account #3</option>
              </select>
            </div>
            
            <div className="border-t border-blue-500/30 pt-2 space-y-1">
              <div className="flex justify-between">
                <span className="text-blue-300">연결:</span>
                <span className="text-white">정상</span>
              </div>
              <div className="flex justify-between">
                <span className="text-blue-300">시간:</span>
                <span className="text-white">{new Date().toLocaleTimeString('ko-KR', { hour12: false })}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-blue-300">자산:</span>
                <span className="text-white">${(status as any)?.portfolio?.totalValue?.toLocaleString() || '52,430'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-blue-300">현금:</span>
                <span className="text-white">$15,420</span>
              </div>
              <div className="flex justify-between">
                <span className="text-blue-300">수익률:</span>
                <span className={`${((status as any)?.portfolio?.dayChangePercent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {((status as any)?.portfolio?.dayChangePercent || 0) >= 0 ? '+' : ''}{((status as any)?.portfolio?.dayChangePercent || 2.4).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Auto Trading Section - Purple */}
        <div className="bg-purple-900/30 border border-purple-500/30 m-2 rounded" data-testid="auto-trading-section">
          <div className="bg-purple-600 text-white px-3 py-1 text-sm font-medium flex items-center">
            <span className="mr-2">⚡</span> 자동매매
          </div>
          <div className="p-3 space-y-3">
            {/* Strategy Selection */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-purple-300">전략 선택:</label>
              <select 
                value={selectedStrategy} 
                onChange={(e) => setSelectedStrategy(e.target.value)}
                className="w-full bg-purple-950 border border-purple-500/50 text-white text-xs rounded px-2 py-1"
                data-testid="strategy-select"
              >
                {availableStrategies.map((strategyName) => (
                  <option key={strategyName} value={strategyName}>
                    {strategyName}
                  </option>
                ))}
              </select>
            </div>

            {/* Control Buttons */}
            <div className="flex space-x-2">
              <button
                onClick={handleStrategyToggle}
                className={`flex-1 px-3 py-2 rounded text-xs font-medium transition-colors ${
                  isStrategyRunning 
                    ? 'bg-purple-700 hover:bg-purple-600 text-white' 
                    : 'bg-green-700 hover:bg-green-600 text-white'
                }`}
                data-testid={isStrategyRunning ? "button-stop-strategy" : "button-start-strategy"}
              >
                {isStrategyRunning ? '중지' : '시작'}
              </button>
            </div>

            {/* Collapsible Strategy Info */}
            <div className="border-t border-purple-500/30 pt-2">
              <button
                onClick={() => setIsStrategyInfoExpanded(!isStrategyInfoExpanded)}
                className="flex items-center justify-between w-full text-xs text-purple-300 hover:text-purple-200"
                data-testid="button-toggle-strategy-info"
              >
                <span>전략 정보</span>
                {isStrategyInfoExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              
              {isStrategyInfoExpanded && (
                <div className="bg-purple-950/50 border border-purple-500/30 rounded p-2 space-y-2 mt-2">
                  {/* Strategy Description */}
                  {strategyDetails && (
                    <div className="text-xs text-purple-200 mb-2 border-b border-purple-500/30 pb-2">
                      {strategyDetails.description}
                    </div>
                  )}
                  
                  {/* Buy Conditions */}
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-purple-300">📈 매수 조건:</div>
                    {strategyDetails?.conditions?.buy && (
                      <div className="text-xs space-y-1 ml-2">
                        {Array.isArray(strategyDetails.conditions.buy) 
                          ? strategyDetails.conditions.buy.map((condition: string, index: number) => (
                              <div key={index} className="text-purple-200">• {condition}</div>
                            ))
                          : Object.entries(strategyDetails.conditions.buy).map(([key, value], index) => (
                              <div key={index} className="text-purple-200">• {key}: {String(value)}</div>
                            ))
                        }
                      </div>
                    )}
                  </div>
                  
                  {/* Sell Conditions */}
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-purple-300">📉 매도 조건:</div>
                    {strategyDetails?.conditions?.sell && (
                      <div className="text-xs space-y-1 ml-2">
                        {Array.isArray(strategyDetails.conditions.sell) 
                          ? strategyDetails.conditions.sell.map((condition: string, index: number) => (
                              <div key={index} className="text-purple-200">• {condition}</div>
                            ))
                          : Object.entries(strategyDetails.conditions.sell).map(([key, value], index) => (
                              <div key={index} className="text-purple-200">• {key}: {String(value)}</div>
                            ))
                        }
                      </div>
                    )}
                  </div>
                  
                  {/* Status Info */}
                  <div className="border-t border-purple-500/30 pt-2 space-y-1">
                    <div className="flex justify-between">
                      <span className="text-purple-400">현재 상태:</span>
                      <span className={`${isStrategyRunning ? 'text-green-400' : 'text-gray-400'}`}>
                        {isStrategyRunning ? '🟢 실행중' : '🔴 중지됨'}
                      </span>
                    </div>
                    
                    {/* 카운트다운 메시지 */}
                    {currentCountdown && (
                      <div className="text-yellow-200 text-center py-1 bg-yellow-900/30 rounded border border-yellow-600/30 mt-2">
                        {currentCountdown}
                      </div>
                    )}
                    
                    {/* 실행중 메시지 */}
                    {isStrategyRunning && !currentCountdown && (
                      <div className="text-purple-200 text-center py-1 bg-purple-950/50 rounded animate-pulse mt-2">
                        {selectedStrategy} 전략 실행 중...
                      </div>
                    )}
                    
                    <div className="flex justify-between">
                      <span className="text-purple-400">다음 실행:</span>
                      <span className="text-white">{strategyDetails?.parameters?.executionTime || '14:00'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-purple-400">최근 실행:</span>
                      <span className="text-white">{strategyStatus.lastExecution || '-'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-purple-400">총 실행 횟수:</span>
                      <span className="text-white">{strategyStatus.totalExecutions}</span>
                    </div>
                    
                    {/* 실시간 자동매매 메시지 */}
                    {tradingMessages.length > 0 && (
                      <div className="mt-3 space-y-1">
                        <div className="text-xs font-medium text-purple-300">📊 실시간 진행상황:</div>
                        {tradingMessages.slice(0, 3).map((message, index) => (
                          <div key={index} className="text-xs text-purple-200 bg-purple-950/30 px-2 py-1 rounded">
                            {message}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>


        {/* Command History Section - Green */}
        <div className="bg-green-900/30 border border-green-500/30 m-2 rounded" data-testid="history-section">
          <div className="bg-green-600 text-white px-3 py-1 text-sm font-medium flex items-center">
            <span className="mr-2">📜</span> 명령어 히스토리
          </div>
          <div className="p-3 max-h-28 overflow-y-auto">
            <div className="grid grid-cols-2 gap-2">
              {commandHistory.slice(-4).map((cmd, index) => (
                <div key={index} className="text-xs text-green-300 flex justify-between border-r border-green-700/30 pr-2 last:border-r-0">
                  <span className="truncate">{cmd.command}</span>
                  <span className="text-gray-400 ml-1">{cmd.time}</span>
                </div>
              ))}
              {commandHistory.length === 0 && (
                <>
                  <div className="text-xs text-green-300 flex justify-between border-r border-green-700/30 pr-2">
                    <span>help</span>
                    <span className="text-gray-400 ml-1">20:26:12</span>
                  </div>
                  <div className="text-xs text-green-300 flex justify-between">
                    <span>status</span>
                    <span className="text-gray-400 ml-1">20:26:08</span>
                  </div>
                </>
              )}
              {commandHistory.length > 0 && commandHistory.length < 4 && (
                Array.from({ length: 4 - commandHistory.length }, (_, i) => (
                  <div key={`empty-${i}`} className="text-xs text-green-700/50">
                    <span>-</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Right Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Terminal Header */}
        <div className="bg-gray-800 border-b border-gray-600 px-4 py-2 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="w-3 h-3 bg-red-500 rounded-full"></span>
            <span className="w-3 h-3 bg-yellow-500 rounded-full"></span>
            <span className="w-3 h-3 bg-green-500 rounded-full"></span>
            <span className="ml-4 text-gray-300 font-medium">터미널</span>
          </div>
          <div className="text-xs text-gray-400">
            [{new Date().toLocaleTimeString('ko-KR', { hour12: false })}] WealthCommander v2.1 - 트레이딩 터미널이 준비되었습니다.
          </div>
        </div>

        {/* Terminal Content - Full Height */}
        <div className="flex-1 bg-black flex flex-col h-full">
          <TerminalInterface onCommandExecuted={handleCommandExecuted} />
        </div>
      </div>
    </div>
  );
}