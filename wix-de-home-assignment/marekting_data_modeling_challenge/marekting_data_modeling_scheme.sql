-- Dimension Table
CREATE TABLE Accounts (
    account_id INT NOT NULL PRIMARY KEY,
    account_name VARCHAR(255) NOT NULL
);

-- Dimension Table
CREATE TABLE SubAccounts (
    sub_account_id INT NOT NULL PRIMARY KEY,
    sub_account_name VARCHAR(255) NOT NULL,
    account_id INT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES Accounts(account_id)
);

-- Dimension Table
CREATE TABLE Portfolios (
    portfolio_id INT NOT NULL PRIMARY KEY,
    portfolio_name VARCHAR(255) NOT NULL,
    sub_account_id INT NOT NULL,
    account_id INT NOT NULL,
    FOREIGN KEY (sub_account_id) REFERENCES SubAccounts(sub_account_id),
    FOREIGN KEY (account_id) REFERENCES Accounts(account_id)
);

-- Dimension Table
CREATE TABLE Campaigns (
    campaign_id INT NOT NULL PRIMARY KEY,
    campaign_name VARCHAR(255) NOT NULL,
    portfolio_id INT NOT NULL,
    sub_account_id INT NOT NULL,
    account_id INT NOT NULL,
    FOREIGN KEY (portfolio_id) REFERENCES Portfolios(portfolio_id),
    FOREIGN KEY (sub_account_id) REFERENCES SubAccounts(sub_account_id),
    FOREIGN KEY (account_id) REFERENCES Accounts(account_id)
);

-- Dimension Table
CREATE TABLE AdGroups (
    ad_group_id INT NOT NULL PRIMARY KEY,
    ad_group_name VARCHAR(255) NOT NULL,
    campaign_id INT NOT NULL,
    portfolio_id INT NOT NULL,
    sub_account_id INT NOT NULL,
    account_id INT NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES Campaigns(campaign_id),
    FOREIGN KEY (portfolio_id) REFERENCES Portfolios(portfolio_id),
    FOREIGN KEY (sub_account_id) REFERENCES SubAccounts(sub_account_id),
    FOREIGN KEY (account_id) REFERENCES Accounts(account_id)
);

-- Dimension Table
CREATE TABLE Ads (
    ad_id INT NOT NULL PRIMARY KEY,
    ad_name VARCHAR(255) NOT NULL,
    ad_group_id INT NOT NULL,
    campaign_id INT NOT NULL,
    portfolio_id INT NOT NULL,
    sub_account_id INT NOT NULL,
    account_id INT NOT NULL,
    bid DECIMAL(10, 2) NOT NULL,
    label VARCHAR(32),
    impressions INT NOT NULL,
    clicks INT NOT NULL,
    cost DECIMAL(10, 2) NOT NULL,
    device VARCHAR(50) NOT NULL,
    geo VARCHAR(100) NOT NULL,
    click_date DATE,
    view_date DATE,
    FOREIGN KEY (ad_group_id) REFERENCES AdGroups(ad_group_id),
    FOREIGN KEY (campaign_id) REFERENCES Campaigns(campaign_id),
    FOREIGN KEY (portfolio_id) REFERENCES Portfolios(portfolio_id),
    FOREIGN KEY (sub_account_id) REFERENCES SubAccounts(sub_account_id),
    FOREIGN KEY (account_id) REFERENCES Accounts(account_id)
);
