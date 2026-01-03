import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Create plots directory
OUTPUT_DIR = "results/plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load data
df = pd.read_csv("summary_report.csv")

# Set plotting style
sns.set_theme(style="whitegrid")
plt.rcParams.update({'figure.figsize': (12, 6)})

def plot_metric(metric, title, filename):
    plt.figure(figsize=(14, 8))
    
    # Create the plot
    g = sns.catplot(
        data=df, 
        kind="bar",
        x="Users", 
        y=metric, 
        hue="Pool Mode", 
        col="Framework",
        height=5, 
        aspect=0.8,
        palette="viridis",
        errorbar=None
    )
    
    g.fig.subplots_adjust(top=0.85)
    g.fig.suptitle(title, fontsize=16)
    
    # Save
    save_path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(save_path)
    print(f"Saved {save_path}")
    plt.close()

# 1. RPS Comparison
plot_metric("RPS", "Requests Per Second (RPS) Comparison", "rps_comparison.png")

# 2. P95 Latency Comparison
plot_metric("P95 Latency (ms)", "P95 Latency Comparison (Lower is Better)", "p95_latency_comparison.png")

print("Visualization complete.")
