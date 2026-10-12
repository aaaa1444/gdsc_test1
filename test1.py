import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text

# ---------------------------------------------------------
# 1. MySQL 資料庫連線設定
# ---------------------------------------------------------
DB_USER = "root"          # 請修改為你的 MySQL 帳號
DB_PASS = "!Pan630826"        # 請修改為你的 MySQL 密碼
DB_HOST = "localhost"     # MySQL 主機位置 (或 localhost)
DB_PORT = "3306"          # MySQL 連線 Port
DB_NAME = "sales_db"      # 資料庫名稱

def create_database_if_not_exists():
    """連線至 MySQL 伺服器，若 sales_db 資料庫不存在則自動建立"""
    try:
        base_engine = create_engine(
            f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/?charset=utf8mb4"
        )
        with base_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4;"))
        base_engine.dispose()
        print(f"✅ 資料庫 [{DB_NAME}] 已確認/自動建立完成。")
    except Exception as e:
        print(f"❌ 建立資料庫失敗，請確認 MySQL 帳號密碼與服務狀態: {e}")
        raise e

# 執行自動建立資料庫
create_database_if_not_exists()

# 建立指定連結至 sales_db 的 SQLAlchemy Engine
engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

# 自動定位當前 Python 檔案所在目錄
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()

# 設定 Matplotlib / Seaborn 中文字型與主題
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False
sns.set_theme(style="whitegrid", font='Microsoft JhengHei')

def init_db():
    """於 MySQL 資料庫建立 daily_sales 資料表結構"""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_sales (
                sale_id INT PRIMARY KEY,
                sale_date DATE,
                product_id VARCHAR(50),
                product_name VARCHAR(100),
                category VARCHAR(50),
                channel VARCHAR(50),
                unit_price INT,
                quantity INT,
                returned_quantity INT,
                net_revenue INT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))
    print("✅ MySQL 資料表 (daily_sales) 初始化檢查完成。")

def import_csv_to_mysql(file_name):
    """讀取 CSV 檔並透過 ON DUPLICATE KEY UPDATE (UPSERT) 寫入/更新至 MySQL"""
    full_path = os.path.join(script_dir, file_name)
    if not os.path.exists(full_path):
        print(f"⚠️ 找不到 CSV 檔案: [{file_name}]，請確認檔案已放置於: {script_dir}")
        return False

    try:
        df = pd.read_csv(full_path, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(full_path, encoding="big5")

    # 計算淨銷售額 (若 CSV 中未預先計算)
    if 'net_revenue' not in df.columns:
        df['net_revenue'] = df['unit_price'] * (df['quantity'] - df['returned_quantity'])

    with engine.begin() as conn:
        for _, row in df.iterrows():
            sql = text("""
                INSERT INTO daily_sales (
                    sale_id, sale_date, product_id, product_name, category,
                    channel, unit_price, quantity, returned_quantity, net_revenue
                ) VALUES (
                    :sale_id, :sale_date, :product_id, :product_name, :category,
                    :channel, :unit_price, :quantity, :returned_quantity, :net_revenue
                )
                ON DUPLICATE KEY UPDATE
                    sale_date = VALUES(sale_date),
                    product_id = VALUES(product_id),
                    product_name = VALUES(product_name),
                    category = VALUES(category),
                    channel = VALUES(channel),
                    unit_price = VALUES(unit_price),
                    quantity = VALUES(quantity),
                    returned_quantity = VALUES(returned_quantity),
                    net_revenue = VALUES(net_revenue);
            """)
            conn.execute(sql, row.to_dict())

    print(f"✅ 成功將 CSV 資料寫入/覆蓋更新至 MySQL: [{file_name}]")
    return True

def generate_dashboard():
    """自 MySQL 讀取銷售資料、繪製視覺化圖表並生成 index.html"""
    try:
        df = pd.read_sql("SELECT * FROM daily_sales", engine)
    except Exception as e:
        print(f"❌ 讀取 MySQL 資料庫失敗: {e}")
        return

    if df.empty:
        print("⚠️ MySQL 資料庫中無任何資料，無法繪製看板。")
        return

    # 計算四大關鍵指標
    records_count = len(df)
    total_qty = df['quantity'].sum()
    total_returns = df['returned_quantity'].sum()
    total_net_rev = df['net_revenue'].sum()

    print("\n================ 📊 MySQL 資料統計指標 ================")
    print(f"總紀錄數 (records)    : {records_count} 筆")
    print(f"總售出數 (quantity)   : {total_qty} 件")
    print(f"總退貨數 (returns)    : {total_returns} 件")
    print(f"淨銷售額 (netRevenue) : NT$ {total_net_rev:,}")
    print("=======================================================\n")

    # 繪製圖表 (2x2 版面配置)
    df['sale_date'] = pd.to_datetime(df['sale_date'])
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    # 【圖 1】每日淨銷售額趨勢 (折線圖)
    daily_rev = df.groupby('sale_date')['net_revenue'].sum().reset_index()
    sns.lineplot(data=daily_rev, x='sale_date', y='net_revenue', marker='o', ax=axes[0, 0], color='#1f77b4', linewidth=2)
    axes[0, 0].set_title("每日淨銷售額趨勢", fontsize=13, fontweight='bold')
    axes[0, 0].set_xlabel("日期")
    axes[0, 0].set_ylabel("淨銷售額 (NT$)")

    # 【圖 2】各商品淨銷售額排行 (長條圖)
    prod_rev = df.groupby('product_name')['net_revenue'].sum().reset_index().sort_values(by='net_revenue', ascending=False)
    sns.barplot(
        data=prod_rev,
        x='net_revenue',
        y='product_name',
        hue='product_name',
        palette='Blues_r',
        legend=False,
        ax=axes[0, 1]
    )
    axes[0, 1].set_title("各商品總淨銷售額排行", fontsize=13, fontweight='bold')
    axes[0, 1].set_xlabel("淨銷售額 (NT$)")
    axes[0, 1].set_ylabel("商品名稱")

    # 【圖 3】各分類淨銷售額占比 (圓餅圖)
    cat_rev = df.groupby('category')['net_revenue'].sum()
    axes[1, 0].pie(
        cat_rev,
        labels=cat_rev.index,
        autopct='%1.1f%%',
        startangle=140,
        colors=sns.color_palette('Pastel1')
    )
    axes[1, 0].set_title("各分類淨銷售額占比", fontsize=13, fontweight='bold')

    # 【圖 4】通路比較與售出數量 vs 淨銷售額 (散佈圖)
    sns.scatterplot(data=df, x='quantity', y='net_revenue', hue='channel', style='channel', s=90, ax=axes[1, 1])
    axes[1, 1].set_title("售出數量與淨銷售額散佈圖（依通路區分）", fontsize=13, fontweight='bold')
    axes[1, 1].set_xlabel("售出數量（件）")
    axes[1, 1].set_ylabel("淨銷售額 (NT$)")

    plt.tight_layout()
    chart_path = os.path.join(script_dir, "sales_dashboard.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    print(f"📈 分析圖表已匯出至: {chart_path}")

    # 生成 index.html 靜態網頁
    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>銷售資料分析看板 (MySQL)</title>
    <style>
        body {{ font-family: 'Microsoft JhengHei', 'Segoe UI', sans-serif; margin: 30px; background-color: #f4f7f6; }}
        .container {{ max-width: 1100px; margin: auto; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        h1 {{ text-align: center; color: #2c3e50; margin-bottom: 25px; }}
        .metrics {{ display: flex; justify-content: space-around; margin-bottom: 25px; flex-wrap: wrap; gap: 12px; }}
        .card {{ background: #edf2f7; padding: 15px 20px; border-radius: 8px; text-align: center; flex: 1; min-width: 180px; }}
        .card h3 {{ margin: 0; color: #4a5568; font-size: 13px; text-transform: uppercase; }}
        .card p {{ margin: 8px 0 0; font-size: 20px; font-weight: bold; color: #2b6cb0; }}
        img {{ width: 100%; height: auto; border-radius: 8px; margin-top: 15px; border: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>銷售資料分析看板 (MySQL 資料源)</h1>
        <div class="metrics">
            <div class="card"><h3>總紀錄數</h3><p>{records_count:,} 筆</p></div>
            <div class="card"><h3>總售出數量</h3><p>{total_qty:,} 件</p></div>
            <div class="card"><h3>總退貨數量</h3><p>{total_returns:,} 件</p></div>
            <div class="card"><h3>總淨銷售額</h3><p>NT$ {total_net_rev:,}</p></div>
        </div>
        <hr style="border: 0; height: 1px; background: #e2e8f0;">
        <img src="sales_dashboard.png" alt="銷售分析圖表">
    </div>
</body>
</html>"""

    html_path = os.path.join(script_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"🌐 靜態網頁已更新完成: {html_path}\n")

if __name__ == "__main__":
    # 1. 初始化 MySQL 資料表結構
    init_db()

    # 2. 自動載入/更新 CSV 資料至 MySQL (請修改為你資料夾中實際的 CSV 檔名)
    import_csv_to_mysql("sales_original_300.csv")
    import_csv_to_mysql("updated_sales_202609.csv")

    # 3. 自 MySQL 撈取資料並產生視覺化圖表與 HTML
    generate_dashboard()
