import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { WebSocketClient } from "@/lib/websocket";

interface WebSocketContextType {
  ws: WebSocketClient | null;
  isConnected: boolean;
  sendCommand: (command: string) => void;
}

const WebSocketContext = createContext<WebSocketContextType>({
  ws: null,
  isConnected: false,
  sendCommand: () => {},
});

export function useWebSocket() {
  return useContext(WebSocketContext);
}

interface WebSocketProviderProps {
  children: ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const [ws, setWs] = useState<WebSocketClient | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const client = new WebSocketClient(window.location.origin);
    
    client.connect()
      .then(() => {
        setIsConnected(true);
        setWs(client);
      })
      .catch(console.error);

    return () => {
      client.disconnect();
    };
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      if (ws) {
        setIsConnected(ws.isConnected);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [ws]);

  const sendCommand = (command: string) => {
    if (ws) {
      ws.sendCommand(command);
    }
  };

  return (
    <WebSocketContext.Provider value={{ ws, isConnected, sendCommand }}>
      {children}
    </WebSocketContext.Provider>
  );
}
