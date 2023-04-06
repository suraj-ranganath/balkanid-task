import creds
import os
import requests
import logging
import requests
import urllib3
import psycopg2
import pandas as pd
from sqlalchemy import create_engine

def normalize(jsonData):
    ownerData=[]
    repoData=[]
    for repo in jsonData:
        ownerData+=[repo['owner']]
        repo['owner_id']=repo['owner']['id']
        repo.pop('owner', None)
        repoData+=[repo]
    repoDataDf = removeDuplicates(pd.json_normalize(repoData))
    ownerDataDf = removeDuplicates(pd.json_normalize(ownerData))
    return repoDataDf, ownerDataDf

def removeDuplicates(df):
    return df.drop_duplicates(subset=['id'], keep='first')

def make_request_with_retry(url, headers, retries=5):
    logger = logging.getLogger("retries")
    logging.basicConfig(level=logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    retry = urllib3.util.Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    try:
        response = session.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data
        elif response.status_code >= 400:
            raise requests.exceptions.HTTPError(response.text)
    except requests.exceptions.RequestException as e:
        logger.error("Request failed with error: %s", str(e))
        raise
    except ValueError as e:
        logger.error("Invalid JSON response: %s", str(e))
        raise

def getResponse(token):
    headers = {"Authorization": "Bearer "+token}
    url = "https://api.github.com/user/repos"
    try:
        data = make_request_with_retry(url, headers, retries=5)
        return data
    except requests.exceptions.HTTPError as e:
        print("Request failed with error:", str(e))
    except requests.exceptions.RequestException as e:
        print("Request failed with error:", str(e))
    except ValueError as e:
        print("Invalid JSON response:", str(e))

#Load data to PostgreSQL DB
def loadToDB(df,name):
    try:
        engine = create_engine(f'postgresql://{creds.dbUser}:{creds.dbPassword}@{creds.dbHost}:{creds.dbPort}/{creds.dbName}')
    except (Exception) as error :
        print ("Error while connecting to PostgreSQL", error)
    else:
        df.to_sql(name, con=engine, if_exists='replace')
        engine.dispose()
        print("Data loaded to DB successfully.")

def postgresToCSV(csvFileName):
    try:
        conn = psycopg2.connect(f"dbname={creds.dbName} user={creds.dbUser} password={creds.dbPassword} host={creds.dbHost} port={creds.dbPort}")
        cur = conn.cursor()
    except (Exception) as error :
        print ("Error while connecting to PostgreSQL", error)
    try:
        sql = "COPY (select r.id as RepoID,r.name as RepoName,r.visibility as Status,r.stargazers_count as starsCount,o.id as ownerId,o.login as ownerName,o.gravatar_id as ownerEmail from repos r join owners o on r.owner_id = o.id) TO STDOUT WITH CSV DELIMITER ',' header"
        with open(os.path.join(creds.csvResultPath,csvFileName), "w") as file:
            cur.copy_expert(sql, file)
    except (Exception) as error :
        print ("Error Postgres SQL Query", error)
    else:
        conn.commit()
        cur.close()
        print(f"Data loaded to CSV successfully in {csvFileName}.")

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    token = creds.githubToken
    try:
        jsonData = getResponse(token)
    except:
        print("No JSON Data recieved.")
    else:
        repoDataDf, ownerDataDf = normalize(jsonData)
        loadToDB(repoDataDf, 'repos')
        loadToDB(ownerDataDf, 'owners')
        postgresToCSV("result.csv")
        
    
    
