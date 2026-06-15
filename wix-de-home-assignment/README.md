This repository contains the work I completed for the Data Engineer role home assignment from WIX. It showcases my skills in data engineering, including data processing, cleaning, and analysis, based on the tasks outlined in the assignment.


## Setup Instructions

To set up the environment for running the code, you can install all necessary dependencies by running the following command:

```bash
pip install -r requirements.txt

This will install the required Python packages listed in the requirements.txt file.

To run the Python script, use the following command:
python wix-api-integration-and-data-pipeline-task.py -t <ticker_name> -d <yyyy-mm-dd> -s <currency-one,currency-two,etc.>

-t <ticker_name>: Specify the stock ticker (e.g., AAPL for Apple).
-d <yyyy-mm-dd>: Specify the date for the stock data you wish to retrieve.
-s <currency-one,currency-two,etc.>: (Optional) Specify the currencies you want to convert the stock price to. If you don’t provide this flag, the script will use all available currencies.
The script will fetch the stock data, perform the currency conversion, and save the results to a CSV file in the tmp folder. Further details can be found in the explanation document.

Task #1: Stock Data and Currency Conversion
I integrated a specific API to retrieve daily stock data. For the same date, I fetched currency data, allowing you to see the stock price in multiple currencies. The script also checks the currency in which the stock is priced and allows you to convert the price into other currencies. The data is saved as a CSV file in the tmp folder.

I also included SQL code to create a data warehouse table for storing this data. For more detailed information, please refer to the explanation document.

Task #2: Data Hierarchy and Database Design
For Task #2, I analyzed the data hierarchy and created dimension tables for each level of aggregation. The ad table, being the last level in the hierarchy, acts as the fact table, using foreign keys from the dimension tables. This structure facilitates the management and querying of campaign data. The explanation document and ERD chart provide further details.

Task #3: Data Storage and Pipelines
In this task, I addressed the different data update frequencies. Some data is updated in real-time (e.g., stock and currency data), while other data updates less frequently (e.g., ad campaign details). To handle large amounts of rapidly changing data, I decided to store frequently updated data in BigQuery, while less frequently updated data will be stored in an SQL database (MySQL).

To process the raw data and transfer it to the appropriate data stores, we will use Airflow pipelines. Metabase will be used by the analytics and marketing teams to pull scheduled reports and access the data.

3. Assumptions Made
The amount of data processed in BigQuery is expected to grow quickly due to frequent updates, while the SQL database will contain less frequently changing data.
Airflow will be set up and configured to handle the ETL process for both BigQuery and MySQL.
Metabase will be used as the business intelligence tool for data access and reporting.

4. Challenges Encountered and Solutions
1. Inconsistent API Data
Some stock tickers returned incomplete or misaligned data, making processing difficult.
Solution: Added validation checks, standardized formats, and implemented retry logic for failed API calls.

2. Data Warehouse Design Complexity
Structuring time-series stock data and multi-dimensional currency data efficiently was challenging.
Solution: Balanced normalization and denormalization, optimized indexing, and ensured referential integrity.

3. Efficient Data Flow Optimization
Stock and currency data update at different frequencies, requiring a scalable ETL process.
Solution: Used BigQuery for high-frequency data, MySQL for lower-frequency data, and Airflow for automated pipeline orchestration.