import pandas as pd
from scipy.io import arff


data, meta = arff.loadarff('breast-cancer-wisconsin-full-names.arff')

# Converting into dataframe
df = pd.DataFrame(data)

# Decoding data
for col in df.select_dtypes([object]):
    df[col] = df[col].str.decode('utf-8')

# Preview the data
print(df.head())

# Check dataset information
print(df.info())
