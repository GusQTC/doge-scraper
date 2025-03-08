import pandas as pd

#read contracts_selenium_data.csv

df = pd.read_csv('contracts_selenium_data.csv')
# 
# AGENCY,DESCRIPTION,UPLOADED ON,LINK,VALUE
# filter for not containing SUBSCRIPTION, ANNUAL RENEW, LICENSES, SOFTWARE in DESCRIPTION

df_filtered = df[~df['DESCRIPTION'].str.contains('SUBSCRIPTION|ANNUAL RENEW|LICENSES|SOFTWARE', case=False, na=False)]

# save to contracts_filtered.csv
df_filtered.to_csv('contracts_filtered.csv', index=False)

#get count of total rows and filtered rows
total_rows = df.shape[0]
filtered_rows = df_filtered.shape[0]
print(f"Total rows: {total_rows}")
print(f"Filtered rows: {filtered_rows}")

#get unique agencies
unique_agencies = df_filtered['AGENCY'].unique()
print(f"Unique agencies: {len(unique_agencies)}")
