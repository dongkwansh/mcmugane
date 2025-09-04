interface Messages {
  [key: string]: string;
}

let messages: Messages = {};

// Load messages from API
export async function loadMessages(): Promise<void> {
  try {
    const response = await fetch('/messages.json');
    if (response.ok) {
      messages = await response.json();
    }
  } catch (error) {
    console.error('Failed to load messages:', error);
  }
}

export function getMessage(key: string, params?: Record<string, string>): string {
  let message = messages[key] || key;
  
  if (params) {
    Object.entries(params).forEach(([param, value]) => {
      message = message.replace(`{${param}}`, value);
    });
  }
  
  return message;
}

// Initialize messages
loadMessages();
