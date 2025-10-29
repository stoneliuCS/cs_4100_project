import requests
import pandas as pd

#URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

def _geocode_one_address(address):
    params = {
    "address": address,
    "benchmark": "Public_AR_Current", 
    "format": "json"}

    response = requests.get(URL, params=params)
    data = response.json()

    matches = data["result"]["addressMatches"]

    if matches:
        coords = matches[0]["coordinates"]
        return coords
    else:
        print(f"No match found for {address}")
        return None
    
def reformat_csv(filename, saveFilename, sample_size=20):
    # readin crime csv
    df_crime = pd.read_csv(filename)

    # re-format
    df_addresses = pd.DataFrame({"id": range(1, len(df_crime)+1),
                                "address": df_crime["Block Address"],
                                "city": df_crime["City"],
                                "state": ["MA"] * len(df_crime),
                                "zip": df_crime["Zip Code"]})
    
    df_addresses = df_addresses.fillna("").apply(lambda x: x.astype(str).str.strip())

    df_addresses = df_addresses[
        (df_addresses["address"] != "") & (df_addresses["city"] != "")
    ]

    #df_sample = df_addresses.head(sample_size) 
    #df_sample.to_csv("test.csv", index=False)

    # save 
    df_addresses.to_csv(saveFilename, index=False)
    print(f"Saved")
    

def geocode_csv(filename):
    files = {
    'addressFile': (filename, open(filename, 'rb'), 'text/csv')
    }
    params = {
        'benchmark': 'Public_AR_Current'
    }

    r = requests.post(URL, files=files, params=params)
    if r.status_code == 200:
        with open('geocoded_results.csv', 'wb') as f:
            f.write(r.content)
        print("Geocoded results saved to geocoded_results.csv")
    else:
        print("Error:", r.status_code, r.text)


#address = "100 BLOCK WEBSTER ST, EAST BOSTON, MA 02128"
#coords = _geocode_one_address(address)
#print(coords)

def main():
    filename1 = "Boston_Incidents_View.csv"
    filename2 = "formatted_address.csv"
    reformat_csv(filename1, filename2)

    geocode_csv("test.csv")

main()
#df = pd.read_csv("Boston_Incidents_View.csv")
#print(len(df))