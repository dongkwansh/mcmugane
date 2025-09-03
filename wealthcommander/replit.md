# WealthCommander Trading System

## Overview

WealthCommander is an automated trading system built with FastAPI, designed for deployment on Synology NAS environments. The system provides a web-based interface for managing automated trading strategies using the Alpaca broker API. It features real-time WebSocket communication, configurable trading strategies, portfolio management, and a terminal-style command interface for interactive trading operations.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Framework
- **Backend**: FastAPI with asyncio for high-performance async operations
- **WebSocket Management**: Real-time communication between client and server using FastAPI WebSockets
- **Task Scheduling**: APScheduler with AsyncIOScheduler for automated trading execution
- **Container Optimization**: Designed for deployment in Docker containers with optimized logging and file handling

### Trading Engine
- **Broker Integration**: Alpaca API client for paper and live trading
- **Strategy System**: JSON-based strategy configuration with multiple strategy types (Simple Buy, SMA Crossover, RSI Mean Reversion, Breakout Donchian)
- **Portfolio Management**: Real-time position tracking, order management, and account information
- **Risk Management**: Configurable stop-loss, take-profit, and position sizing rules

### Frontend Architecture
- **Web Interface**: Single-page application with terminal-style interface
- **Real-time Updates**: WebSocket-based live data streaming for market status, portfolio updates, and trading notifications
- **Responsive Design**: Optimized for both desktop and mobile viewing
- **Command System**: Terminal-like command processing for trading operations

### Configuration Management
- **Multi-Account Support**: Support for multiple Alpaca accounts (live and paper trading)
- **Strategy Configuration**: JSON-based strategy definitions with hot-reloading capability
- **Internationalization**: Korean language support with message templating
- **Environment-based Settings**: Container-friendly configuration using environment variables

### Data Storage
- **File-based Configuration**: JSON files for settings, strategies, and custom ETF definitions
- **Logging System**: Structured logging with file and console output for container environments
- **No Database Dependency**: Lightweight architecture using file-based storage for configuration

## External Dependencies

### Trading Services
- **Alpaca Markets API**: Primary broker for executing trades and retrieving market data
- **Market Data**: Real-time and historical market data through Alpaca's data feed

### Core Libraries
- **FastAPI**: Web framework for API and WebSocket handling
- **APScheduler**: Task scheduling for automated trading execution
- **Pandas/NumPy**: Data processing and analysis for trading strategies
- **Uvicorn**: ASGI server for production deployment

### Container Environment
- **Uvloop**: High-performance event loop for Linux containers
- **Gunicorn**: Production WSGI server for scaling
- **PSUtil**: System monitoring for resource optimization
- **AIOFiles**: Async file operations for improved I/O performance

### Development Tools
- **Python-dotenv**: Environment variable management
- **Pydantic**: Data validation and settings management
- **StructLog**: Structured logging for better observability
- **HTTPX**: Modern HTTP client for API communications