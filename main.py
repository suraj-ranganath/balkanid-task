import creds
import os
import requests
import logging
import urllib3
import psycopg2
import pandas as pd
import time
import redis
import pickle
from sqlalchemy import create_engine

def perform_github_device_flow_oauth(client_id):
    device_code_url = f'https://github.com/login/device/code?client_id={client_id}&scope=repo'
    response = requests.post(device_code_url, headers={'Accept': 'application/json'})

    if response.status_code != 200:
        raise Exception(f"Failed to obtain device code: {response.text}")

    response_json = response.json()
    device_code = response_json.get('device_code')
    user_code = response_json.get('user_code')
    verification_uri = response_json.get('verification_uri')

    print(f"Please visit this URL on any device and enter the following code to authorize the application:\n{verification_uri}\nCode: {user_code}")

    token_url = 'https://github.com/login/oauth/access_token'
    headers = {'Accept': 'application/json'}
    data = {
        'client_id': client_id,
        'device_code': device_code,
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
    }

    while True:
        response = requests.post(token_url, headers=headers, data=data)
        error = response.json().get('error')
        if error == 'authorization_pending':
            print("Authorization pending. Polling again in 5 seconds...")
            time.sleep(5)
        elif error == 'slow_down':
            print("Polling too frequently. Waiting 10 seconds before polling again...")
            time.sleep(10)
        elif error is None:
            access_token = response.json().get('access_token')
            print("Access token obtained.")
            return access_token
        else: 
            raise Exception(f"Failed to obtain access token: {response.text}")
        

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
    import time
    try:
        engine = create_engine(f'postgresql://{creds.dbUser}:{creds.dbPassword}@{creds.dbHost}:{creds.dbPort}/{creds.dbName}')
    except (Exception) as error :
        time.sleep(50)
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
        with open(csvFileName, "w") as file:
            cur.copy_expert(sql, file)
    except (Exception) as error :
        print ("Error Postgres SQL Query", error)
    else:
        conn.commit()
        cur.close()
        print(f"Data loaded to CSV successfully in {csvFileName}.")
        return pd.read_csv(csvFileName)

def redis_connection():
	try:
		pool = redis.ConnectionPool(
		host=creds.redisHost,
		port=creds.redisPort,
		db=creds.redisDB
		)
		r = redis.Redis(connection_pool=pool)
	except Exception as e:
		logger.error("Redis connection is not ready yet. Error: " + str(e))
	return r

def storeDataframeInRedis(r, key, df):
    df_serialized = pickle.dumps(df)
    r.set(key, df_serialized)

def getDataframeFromRedis(r, key):
    df_serialized = r.get(key)
    df = pickle.loads(df_serialized)
    return df

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    try:
        token = perform_github_device_flow_oauth(creds.githubClientID)
    except Exception as e:
        print("Error while getting token from Github API."+str(e))
    try:
        jsonData = getResponse(token)
    except:
        print("No JSON Data recieved.")
    else:
        repoDataDf, ownerDataDf = normalize(jsonData)
        loadToDB(repoDataDf, 'repos')
        loadToDB(ownerDataDf, 'owners')
        resultDf = postgresToCSV("result.csv")
        try:
            r = redis_connection()
            storeDataframeInRedis(r, 'result', resultDf)
            r.close()
        except Exception as e:
            print("Error while storing data in Redis."+str(e))
        
        print("Would you like to view the result.csv from Redis? (Y/N)")
        choice = input()
        while True:
            if choice == 'Y' or choice == 'y':
                try:
                    r = redis_connection()
                    resultRedisDf = getDataframeFromRedis(r, 'result')
                    print(resultRedisDf)
                    r.close()
                except Exception as e:
                    print("Error while getting data from Redis."+str(e))
                finally:
                    print("Thank you for using the application.")
                    break
            elif choice == 'N' or choice == 'n':
                print("Thank you for using the application.")
                break
            else:
                print("Please enter a valid choice.")
                choice = input()
        
    
    
