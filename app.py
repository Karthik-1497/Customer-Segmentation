from flask import Flask, render_template, request
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

app = Flask(__name__, static_url_path='/static')

# Load the original data (assuming the 'data.csv' file is in the same directory as app.py)
df = pd.read_csv('data.csv')

# Data Wrangling for RFM Analysis
df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'])
df_new = df.dropna()
df_new = df_new[df_new.Quantity > 0]
df_new = df_new[df_new.UnitPrice > 0]

df_new['Revenue'] = df_new['Quantity'] * df_new['UnitPrice']
df_new['CustomerID'] = df_new['CustomerID'].astype('int64')

# RFM Analysis
NOW = pd.to_datetime('2011-12-10')
rfmTable = df_new.groupby(['CustomerID'], as_index=False).agg({
    'InvoiceDate': lambda x: (NOW - x.max()).days,
    'InvoiceNo': lambda x: len(x),
    'Revenue': lambda x: x.sum()
})
rfmTable['InvoiceDate'] = rfmTable['InvoiceDate'].astype(int)
rfmTable.rename(columns={'InvoiceDate': 'Recency',
                         'InvoiceNo': 'Frequency',
                         'Revenue': 'Monetary'}, inplace=True)

quantiles = rfmTable.quantile(q=[0.25, 0.5, 0.75])
quantiles = quantiles.to_dict()

segmented_rfm = rfmTable.copy()

def RScore(x, p, d):
    if x <= d[p][0.25]:
        return 4
    elif x <= d[p][0.50]:
        return 3
    elif x <= d[p][0.75]:
        return 2
    else:
        return 1

def FMScore(x, p, d):
    if x <= d[p][0.25]:
        return 1
    elif x <= d[p][0.50]:
        return 2
    elif x <= d[p][0.75]:
        return 3
    else:
        return 4

segmented_rfm['r_quartile'] = segmented_rfm['Recency'].apply(RScore, args=('Recency', quantiles,))
segmented_rfm['f_quartile'] = segmented_rfm['Frequency'].apply(FMScore, args=('Frequency', quantiles,))
segmented_rfm['m_quartile'] = segmented_rfm['Monetary'].apply(FMScore, args=('Monetary', quantiles,))

kmeans = KMeans(n_clusters=4, random_state=1)

# Compute k-means clustering on pre-processed data
kmeans.fit(segmented_rfm[['r_quartile', 'f_quartile', 'm_quartile']])

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Get user input from the form
        invoiceno = request.form['invoiceno']
        stockcode = request.form['stockcode']
        description = request.form['description']
        quantity = float(request.form['quantity'])
        invoicedate = pd.to_datetime(request.form['invoicedate'])
        unitprice = float(request.form['unitprice'])
        customerid = int(request.form['customerid'])
        country = request.form['country']

        # Calculate Revenue based on Quantity and UnitPrice
        revenue = quantity * unitprice

        # Calculate Recency based on the provided InvoiceDate
        recency = (NOW - invoicedate).days

        # Prepare the data for clustering
        user_data = pd.DataFrame({
            'Recency': [recency],
            'Frequency': [1],  # Set Frequency as 1 for the user as it's a single transaction
            'Monetary': [revenue],
            'CustomerID': [customerid]
        })

        # Calculate quartile values for Recency, Frequency, and Monetary
        user_data['r_quartile'] = user_data['Recency'].apply(RScore, args=('Recency', quantiles,))
        user_data['f_quartile'] = user_data['Frequency'].apply(FMScore, args=('Frequency', quantiles,))
        user_data['m_quartile'] = user_data['Monetary'].apply(FMScore, args=('Monetary', quantiles,))

        # Assign cluster label to the user data using the KMeans model
        user_cluster = kmeans.predict(user_data[['r_quartile', 'f_quartile', 'm_quartile']])[0]
        user_data['Cluster'] = user_cluster

        # Determine the segment based on the cluster label
        if user_cluster == 0:
            segment = 'Best Customers'
        elif user_cluster == 1:
            segment = 'Loyal Customers'
        elif user_cluster == 2:
            segment = 'Potential Loyalists'
        else:
            segment = 'Needs Attention'

        return render_template('result.html', segment=segment)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
