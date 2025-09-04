# Overview

WealthCommander is a Korean-language trading terminal application that provides automated trading functionality with real-time market data, portfolio management, and strategy execution. The application features a modern React frontend built with TypeScript and shadcn/ui components, connected to an Express.js backend with WebSocket support for real-time communication. The system integrates with Alpaca trading APIs for executing trades and managing positions.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Framework**: React 18 with TypeScript using Vite as the build tool
- **UI Components**: shadcn/ui component library with Radix UI primitives for consistent design
- **Styling**: Tailwind CSS with CSS variables for theming, supporting dark mode
- **State Management**: TanStack Query (React Query) for server state management and caching
- **Routing**: Wouter for lightweight client-side routing
- **Real-time Communication**: Custom WebSocket client for live data updates

## Backend Architecture
- **Runtime**: Node.js with Express.js framework
- **Language**: TypeScript with ES modules
- **API Design**: RESTful APIs with WebSocket endpoints for real-time features
- **Session Management**: Express sessions with PostgreSQL session store
- **Development**: Hot module reloading with Vite in development mode

## Data Storage Solutions
- **Primary Database**: PostgreSQL with Drizzle ORM for type-safe database operations
- **Schema Management**: Drizzle Kit for database migrations and schema management
- **Connection**: Neon Database serverless PostgreSQL for production
- **Session Storage**: PostgreSQL-backed session store for user authentication
- **Data Models**: Users, accounts, strategies, orders, positions, and market data entities

## Authentication and Authorization
- **Account Management**: Multi-account support with Alpaca API integration
- **Trading Accounts**: Support for both paper trading and live trading environments
- **API Keys**: Secure storage of Alpaca API credentials per trading account
- **Session-based Authentication**: Express sessions for user state management

## External Service Integrations
- **Trading Platform**: Alpaca Markets API for order execution and portfolio management
- **Market Data**: Real-time market data feeds through WebSocket connections
- **Order Management**: Integration with Alpaca's order management system
- **Position Tracking**: Real-time position updates and portfolio valuation

## Key Design Patterns
- **Component Architecture**: Modular React components with clear separation of concerns
- **Type Safety**: Full TypeScript coverage across frontend, backend, and shared schemas
- **Real-time Updates**: WebSocket-based architecture for live trading data
- **Internationalization**: Korean language support with centralized message management
- **Responsive Design**: Mobile-first approach with adaptive layouts
- **Error Handling**: Comprehensive error boundaries and user feedback systems
- **Strategy System**: Pluggable trading strategy architecture supporting multiple algorithm types