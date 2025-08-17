import pandas as pd
import matplotlib.pyplot as plt

# Load stock data from CSV
df = pd.read_csv("infosys_stock_data.csv", index_col=0, parse_dates=True)

# Display first 5 rows
print("\n--- First 5 Rows ---")
print(df.head())

# Summary statistics
print("\n--- Summary Statistics ---")
print(df.describe())

# Missing values
print("\n--- Missing Values ---")
print(df.isnull().sum())

# Plot Closing Price over Time
plt.figure(figsize=(10, 6))
plt.plot(df.index, df['Close'], label='Close Price', color='blue')
plt.title("Closing Price Over Time")
plt.xlabel("Date")
plt.ylabel("Price")
plt.legend()
plt.grid(True)
plt.show()
