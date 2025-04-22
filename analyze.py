import pandas as pd
import json
import os
from datetime import datetime


os.makedirs("output", exist_ok=True)

try:
    df = pd.read_csv("input/market_history.csv", decimal=",")
except FileNotFoundError:
    print("Error: 'market_history.csv' not found in the current directory.")
    exit(1)

df.columns = [col.strip().strip('"').strip("'") for col in df.columns]
print("Cleaned column names:", df.columns.tolist())

price_col = next((col for col in df.columns if "Price" in col and "Cents" in col), None)
if not price_col:
    print("Error: No column found containing 'Price' and 'Cents'. Available columns:", df.columns.tolist())
    exit(1)

 
required_cols = ["Game Name", "Acted On", "Type", "Market Name"]
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    print(f"Error: Missing required columns: {missing_cols}. Available columns:", df.columns.tolist())
    exit(1)

 
cs2_df = df[df["Game Name"] == "Counter-Strike 2"].copy()
print(f"Rows after CS2 filter: {len(cs2_df)}")

 
def normalize_type(type_val):
    if pd.isna(type_val):
        return None
    type_val = str(type_val).strip().lower()
    if type_val in ["purchase", "buy", "bought"]:
        return "purchase"
    elif type_val in ["sale", "sell", "sold"]:
        return "sale"
    return type_val

cs2_df["Type"] = cs2_df["Type"].apply(normalize_type)
print("Unique Type values after normalization:", cs2_df["Type"].unique().tolist())

 
cs2_df[price_col] = pd.to_numeric(cs2_df[price_col], errors="coerce")
cs2_df = cs2_df.dropna(subset=[price_col, "Acted On", "Type", "Market Name"])
print(f"Rows after dropping NaN in {price_col}, Acted On, Type, Market Name: {len(cs2_df)}")

 
cs2_df["Acted On"] = pd.to_datetime(cs2_df["Acted On"], format="%d %b", errors="coerce")
cs2_df = cs2_df.dropna(subset=["Acted On"])
print(f"Rows after date parsing: {len(cs2_df)}")

 
if not cs2_df["Type"].isin(["purchase", "sale"]).any():
    print("Error: No valid 'purchase' or 'sale' transactions found in Type column.")
    exit(1)

 
purchases = cs2_df[cs2_df["Type"] == "purchase"]
sales = cs2_df[cs2_df["Type"] == "sale"]
total_spent = purchases[price_col].sum() / 100
total_earned = sales[price_col].sum() / 100
net_flow = total_earned - total_spent
purchase_count = len(purchases)
sale_count = len(sales)
most_purchased_item = purchases["Market Name"].value_counts().idxmax() if not purchases.empty else "None"
highest_transaction = cs2_df.loc[cs2_df[price_col].idxmax()] if not cs2_df.empty else {}

 
item_details = cs2_df.groupby("Market Name").agg({
    price_col: ["count", "sum"],
    "Type": lambda x: x.value_counts().to_dict()
}).reset_index()
 
item_details.columns = ["Market Name", "transaction_count", "price_sum", "type_breakdown"]
item_details["total_eur"] = item_details["price_sum"] / 100
print("Item details columns:", item_details.columns.tolist())
 
item_details = item_details[["Market Name", "transaction_count", "total_eur", "type_breakdown"]].to_dict(orient="records")

 
summary = {
    "total_spent": round(total_spent, 2),
    "total_earned": round(total_earned, 2),
    "net_flow": round(net_flow, 2),
    "purchase_count": purchase_count,
    "sale_count": sale_count,
    "most_purchased_item": most_purchased_item,
    "highest_transaction": {
        "market_name": highest_transaction.get("Market Name", "None"),
        "price_eur": round(highest_transaction.get(price_col, 0) / 100, 2),
        "type": highest_transaction.get("Type", "")
    },
    "item_details": item_details
}

 
with open("output/summary.json", "w") as f:
    json.dump(summary, f, indent=2)

 
def categorize_item(market_name):
    if pd.isna(market_name):
        return "Unknown"
    market_name = str(market_name)
    if "Capsule" in market_name:
        return "Capsules"
    elif "Case" in market_name:
        return "Cases"
    elif "Charm" in market_name:
        return "Charms"
    elif "Sticker" in market_name:
        return "Stickers"
    else:
        return "Weapons"

cs2_df["Category"] = cs2_df["Market Name"].apply(categorize_item)
bar_data = cs2_df.groupby(["Category", "Type"])[price_col].sum().unstack(fill_value=0) / 100
bar_data = bar_data.reset_index().melt(id_vars="Category", value_vars=["purchase", "sale"], var_name="Type", value_name="Amount")
bar_data = bar_data.pivot(index="Category", columns="Type", values="Amount").fillna(0).reset_index()
bar_data = bar_data.rename(columns={"purchase": "spent", "sale": "earned"}).to_dict(orient="records")

 
with open("output/bar_data.json", "w") as f:
    json.dump(bar_data, f, indent=2)

cs2_df["Date"] = cs2_df["Acted On"].dt.strftime("%Y-%m-%d")
line_data = cs2_df.groupby(["Date", "Market Name"]).agg({
    price_col: ["sum"],
    "Market Name": ["count"]
}).reset_index()
 
line_data.columns = ["Date", "Market Name", "value", "count"]
line_data["value"] = line_data["value"] / 100
print("Line data columns:", line_data.columns.tolist())
line_data = line_data.to_dict(orient="records")

 
with open("output/line_data.json", "w") as f:
    json.dump(line_data, f, indent=2)

pie_data = [
    {"name": "Purchases", "value": purchase_count},
    {"name": "Sales", "value": sale_count}
]


with open("output/pie_data.json", "w") as f:
    json.dump(pie_data, f, indent=2)

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CS2 Market Transaction Analysis</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-100 font-sans">
  <div class="container mx-auto p-4">
    <div id="app" class="bg-white rounded-lg shadow-lg p-6">
      <h1 class="text-3xl font-bold text-blue-800 mb-6 text-center">Counter-Strike 2 Market Transaction Analysis</h1>
      <div id="loading" class="text-center text-xl font-semibold text-gray-700 py-10">Loading data...</div>
      <div id="content" class="hidden">
        <section class="mb-8">
          <h2 class="text-2xl font-semibold text-gray-800 mb-4">Summary</h2>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div class="bg-blue-100 p-4 rounded-lg">
              <p class="text-lg font-medium text-blue-800">Total Spent</p>
              <p id="total-spent" class="text-2xl font-bold text-blue-900"></p>
            </div>
            <div class="bg-green-100 p-4 rounded-lg">
              <p class="text-lg font-medium text-green-800">Total Earned</p>
              <p id="total-earned" class="text-2xl font-bold text-green-900"></p>
            </div>
            <div class="bg-purple-100 p-4 rounded-lg">
              <p class="text-lg font-medium text-purple-800">Net Flow</p>
              <p id="net-flow" class="text-2xl font-bold text-purple-900"></p>
            </div>
            <div class="bg-yellow-100 p-4 rounded-lg">
              <p class="text-lg font-medium text-yellow-800">Purchases</p>
              <p id="purchase-count" class="text-2xl font-bold text-yellow-900"></p>
            </div>
            <div class="bg-red-100 p-4 rounded-lg">
              <p class="text-lg font-medium text-red-800">Sales</p>
              <p id="sale-count" class="text-2xl font-bold text-red-900"></p>
            </div>
            <div class="bg-teal-100 p-4 rounded-lg">
              <p class="text-lg font-medium text-teal-800">Most Purchased Item</p>
              <p id="most-purchased" class="text-xl font-bold text-teal-900"></p>
            </div>
          </div>
          <div class="mt-6 p-4 bg-indigo-100 rounded-lg">
            <p class="text-lg font-semibold text-indigo-800">Highest Transaction</p>
            <p id="highest-transaction" class="text-md text-indigo-900"></p>
          </div>
        </section>
        <section class="mb-8">
          <h2 class="text-2xl font-semibold text-gray-800 mb-4">Item Details</h2>
          <div class="mb-4">
            <label for="item-select" class="text-lg font-medium text-gray-700">Select Item:</label>
            <select id="item-select" class="ml-2 p-2 border rounded-lg">
              <option value="">-- Select an Item --</option>
            </select>
          </div>
          <div id="item-details" class="hidden bg-orange-100 p-4 rounded-lg">
            <p class="text-lg font-semibold text-orange-800 mb-2" id="item-name"></p>
            <table class="w-full text-left text-sm text-gray-700 mb-4">
              <thead>
                <tr class="bg-orange-200">
                  <th class="p-2">Metric</th>
                  <th class="p-2">Value</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="p-2">Transaction Count</td>
                  <td id="item-transaction-count" class="p-2"></td>
                </tr>
                <tr>
                  <td class="p-2">Total Value (€)</td>
                  <td id="item-total-eur" class="p-2"></td>
                </tr>
                <tr>
                  <td class="p-2">Purchases</td>
                  <td id="item-purchases" class="p-2"></td>
                </tr>
                <tr>
                  <td class="p-2">Sales</td>
                  <td id="item-sales" class="p-2"></td>
                </tr>
              </tbody>
            </table>
            <canvas id="item-pie-chart" class="bg-white p-4 rounded-lg shadow"></canvas>
          </div>
        </section>
        <section class="mb-8">
          <h2 class="text-2xl font-semibold text-gray-800 mb-4">Visualizations</h2>
          <div class="mb-8">
            <h3 class="text-xl font-medium text-gray-700 mb-2">Money Spent vs. Earned by Category</h3>
            <canvas id="bar-chart" class="bg-white p-4 rounded-lg shadow"></canvas>
          </div>
          <div class="mb-8">
            <h3 class="text-xl font-medium text-gray-700 mb-2">Transaction Volume Over Time</h3>
            <canvas id="line-chart" class="bg-white p-4 rounded-lg shadow"></canvas>
          </div>
          <div>
            <h3 class="text-xl font-medium text-gray-700 mb-2">Distribution of Transaction Types</h3>
            <canvas id="pie-chart" class="bg-white p-4 rounded-lg shadow"></canvas>
          </div>
        </section>
        <section>
          <h2 class="text-2xl font-semibold text-gray-800 mb-4">Conclusion</h2>
          <p id="conclusion" class="text-gray-700"></p>
        </section>
      </div>
    </div>
  </div>

  <script>
    let itemPieChart = null;

    async function loadData() {
      try {
        const [summary, barData, lineData, pieData] = await Promise.all([
          fetch("output/summary.json").then(res => res.json()),
          fetch("output/bar_data.json").then(res => res.json()),
          fetch("output/line_data.json").then(res => res.json()),
          fetch("output/pie_data.json").then(res => res.json())
        ]);

        // Hide loading and show content
        document.getElementById("loading").classList.add("hidden");
        document.getElementById("content").classList.remove("hidden");

        // Populate summary
        document.getElementById("total-spent").textContent = `€${summary.total_spent.toFixed(2)}`;
        document.getElementById("total-earned").textContent = `€${summary.total_earned.toFixed(2)}`;
        document.getElementById("net-flow").textContent = `€${summary.net_flow.toFixed(2)} ${summary.net_flow >= 0 ? "(Profit)" : "(Loss)"}`;
        document.getElementById("purchase-count").textContent = summary.purchase_count;
        document.getElementById("sale-count").textContent = summary.sale_count;
        document.getElementById("most-purchased").textContent = summary.most_purchased_item;
        document.getElementById("highest-transaction").textContent = 
          `Your highest-value transaction was a ${summary.highest_transaction.type} of "${summary.highest_transaction.market_name}" for €${summary.highest_transaction.price_eur.toFixed(2)}!`;

        // Populate conclusion
        document.getElementById("conclusion").textContent = 
          `This analysis reveals your trading activity in Counter-Strike 2. You spent €${summary.total_spent.toFixed(2)} and earned €${summary.total_earned.toFixed(2)}, resulting in a net ${summary.net_flow >= 0 ? "profit" : "loss"} of €${Math.abs(summary.net_flow).toFixed(2)}. Your most frequently purchased item was "${summary.most_purchased_item}", indicating a preference for these items. Use the dropdown below to explore detailed transaction data for each item.`;

        // Populate item dropdown
        const itemSelect = document.getElementById("item-select");
        summary.item_details.forEach(item => {
          const option = document.createElement("option");
          option.value = item["Market Name"];
          option.textContent = item["Market Name"];
          itemSelect.appendChild(option);
        });

        // Handle item selection
        itemSelect.addEventListener("change", () => {
          const selectedItem = itemSelect.value;
          const detailsDiv = document.getElementById("item-details");
          if (selectedItem) {
            const item = summary.item_details.find(i => i["Market Name"] === selectedItem);
            document.getElementById("item-name").textContent = item["Market Name"];
            document.getElementById("item-transaction-count").textContent = item.transaction_count;
            document.getElementById("item-total-eur").textContent = `€${item.total_eur.toFixed(2)}`;
            document.getElementById("item-purchases").textContent = item.type_breakdown.purchase || 0;
            document.getElementById("item-sales").textContent = item.type_breakdown.sale || 0;
            detailsDiv.classList.remove("hidden");

            // Update item-specific pie chart
            if (itemPieChart) itemPieChart.destroy();
            itemPieChart = new Chart(document.getElementById("item-pie-chart"), {
              type: "pie",
              data: {
                labels: ["Purchases", "Sales"],
                datasets: [{
                  data: [item.type_breakdown.purchase || 0, item.type_breakdown.sale || 0],
                  backgroundColor: ["#F59E0B", "#EC4899"]
                }]
              },
              options: {
                responsive: true,
                plugins: {
                  legend: { position: "top" },
                  tooltip: {
                    callbacks: {
                      label: ctx => `${ctx.label}: ${ctx.raw} (${((ctx.raw / (item.type_breakdown.purchase || 0 + item.type_breakdown.sale || 0)) * 100).toFixed(1)}%)`
                    }
                  }
                }
              }
            });
          } else {
            detailsDiv.classList.add("hidden");
          }
        });

        // Render bar chart
        new Chart(document.getElementById("bar-chart"), {
          type: "bar",
          data: {
            labels: barData.map(d => d.Category),
            datasets: [
              {
                label: "Spent (€)",
                data: barData.map(d => d.spent),
                backgroundColor: "#3B82F6"
              },
              {
                label: "Earned (€)",
                data: barData.map(d => d.earned),
                backgroundColor: "#10B981"
              }
            ]
          },
          options: {
            responsive: true,
            scales: {
              y: { beginAtZero: true, title: { display: true, text: "Amount (€)" } }
            }
          }
        });

        // Render line chart
        const uniqueDates = [...new Set(lineData.map(d => d.Date))];
        const marketNames = [...new Set(lineData.map(d => d["Market Name"]))];
        const datasets = marketNames.map(name => ({
          label: name,
          data: uniqueDates.map(date => {
            const entry = lineData.find(d => d.Date === date && d["Market Name"] === name);
            return entry ? entry.count : 0;
          }),
          borderColor: "#" + Math.floor(Math.random()*16777215).toString(16),
          fill: false
        }));
        new Chart(document.getElementById("line-chart"), {
          type: "line",
          data: {
            labels: uniqueDates,
            datasets: datasets
          },
          options: {
            responsive: true,
            scales: {
              y: { beginAtZero: true, title: { display: true, text: "Transaction Count" } }
            }
          }
        });

        // Render pie chart
        new Chart(document.getElementById("pie-chart"), {
          type: "pie",
          data: {
            labels: pieData.map(d => d.name),
            datasets: [{
              data: pieData.map(d => d.value),
              backgroundColor: ["#F59E0B", "#EC4899"]
            }]
          },
          options: {
            responsive: true,
            plugins: {
              legend: { position: "top" },
              tooltip: {
                callbacks: {
                  label: ctx => `${ctx.label}: ${ctx.raw} (${((ctx.raw / pieData.reduce((a, b) => a + b.value, 0)) * 100).toFixed(1)}%)`
                }
              }
            }
          }
        });
      } catch (error) {
        console.error("Error loading data:", error);
        document.getElementById("loading").textContent = "Error loading data. Please check the console.";
      }
    }

    // Initialize
    loadData();
  </script>
</body>
</html>
"""
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Analysis complete. Results saved to output/ directory. index.html generated.")