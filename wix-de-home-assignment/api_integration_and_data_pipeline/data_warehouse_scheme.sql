-- Fact Table
CREATE TABLE stock_daily_currency (
    fact_id INT PRIMARY KEY AUTO_INCREMENT,
    date_id INT,
    ticker_symbol VARCHAR(10) NOT NULL,
    price_type VARCHAR(50),
    ticker_currency VARCHAR(10) NOT NULL,
    price DECIMAL(18, 6),
    target_currency VARCHAR(10) NOT NULL,
    exchange_rate DECIMAL(18, 6),
    currency_price DECIMAL(18, 6),
    FOREIGN KEY (date_id) REFERENCES date_dimension(date_id),
    FOREIGN KEY (ticker_symbol) REFERENCES stock_dimension(ticker_symbol),
    FOREIGN KEY (target_currency) REFERENCES currency_dimension(currency_code)
);

-- Fact Table

CREATE TABLE stock_daily_price (
    date DATE NOT NULL,
    status VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open_price DECIMAL(10, 2) NOT NULL,
    close_price DECIMAL(10, 2) NOT NULL,
    high_price DECIMAL(10, 2) NOT NULL,
    low_price DECIMAL(10, 2) NOT NULL,
    after_hours_price DECIMAL(10, 2),
    pre_market_price DECIMAL(10, 2),
    volume BIGINT NOT NULL,
    PRIMARY KEY (date, symbol)
);

-- Dimension Table
CREATE TABLE currencies (
    currency_code VARCHAR(10) PRIMARY KEY,
    currency_name VARCHAR(100) NOT NULL
);



