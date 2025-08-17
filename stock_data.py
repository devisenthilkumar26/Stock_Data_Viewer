import yfinance as yf

# Create Ticker object for Infosys
ticker = yf.Ticker("INFY.NS")

# Get last 1 year data
data = ticker.history(period="5y")

# Save to CSV
data.to_csv("infosys_stock_data.csv")

print("Data saved to infosys_stock_data.csv")
