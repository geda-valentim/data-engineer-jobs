import pandas as pd
import os

def load_csv():
    dir = os.path.dirname(__file__)
    df = pd.read_csv( f'{dir}/../../data/local/linkedin_job_listing_sample.csv')

    return df

if __name__ == '__main__':
    df = load_csv()
    print( df.head() )