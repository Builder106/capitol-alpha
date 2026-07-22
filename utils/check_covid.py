import pandas as pd

def run_check_covid(data_path='data/legislative_trades.csv'):
    df = pd.read_csv(data_path, on_bad_lines='skip', low_memory=False, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
    covid_start = pd.to_datetime('2020-01-01')
    covid_end = pd.to_datetime('2020-04-30')

    trade_volume_covid = df[(df['transaction_date'] >= covid_start) & (df['transaction_date'] <= covid_end) & (df['transaction_type'].str.contains('Sale|sale|S|s', na=False))]

    sales_by_leg = trade_volume_covid.groupby('legislator_name')['amount_avg'].sum().sort_values(ascending=False)
    total_sales = sales_by_leg.sum()
    print(f'Total sales: {total_sales}')

    top_5_pct_count = max(1, int(len(sales_by_leg) * 0.05))
    print(f'Top 5% count: {top_5_pct_count} out of {len(sales_by_leg)}')
    top_sellers = sales_by_leg.head(top_5_pct_count)
    print(f'Top 5% sell amount: {top_sellers.sum()} ({top_sellers.sum() / total_sales * 100:.2f}%)')

    remaining = sales_by_leg.tail(len(sales_by_leg) - top_5_pct_count)
    print(f'Remaining sell amount: {remaining.sum()} ({remaining.sum() / total_sales * 100:.2f}%)')

    remaining_df = trade_volume_covid[trade_volume_covid['legislator_name'].isin(remaining.index)]

    pre_crash = remaining_df[(remaining_df['transaction_date'] >= pd.to_datetime('2020-01-15')) & (remaining_df['transaction_date'] <= pd.to_datetime('2020-02-19'))]
    print(f"Pre-crash sales (Jan 15 to Feb 19): {pre_crash['amount_avg'].sum()} for remaining 95%")

    post_crash = remaining_df[(remaining_df['transaction_date'] >= pd.to_datetime('2020-02-20')) & (remaining_df['transaction_date'] <= pd.to_datetime('2020-03-31'))]
    print(f"Post-crash sales (Feb 20 to Mar 31): {post_crash['amount_avg'].sum()} for remaining 95%")
    return total_sales, top_sellers.sum(), remaining.sum()

if __name__ == '__main__':
    run_check_covid()

