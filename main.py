# importing required libraries
import creds
import sys
import requests
import urllib3
import psycopg2
import pandas as pd
import time
import redis
import pickle
from sqlalchemy import create_engine
from logging_config import get_logger

# Initialize logger
logger = get_logger(__name__, '/var/lib/postgresql/data/mylog.log')

# Function to perform Github OAuth Device Flow to obtain access token
def perform_github_device_flow_oauth(client_id):
    device_code_url = f'https://github.com/login/device/code?client_id={client_id}&scope=repo'
    try:
        response = requests.post(device_code_url, headers={'Accept': 'application/json'})
    except requests.exceptions.RequestException as e:
        logger.error("Request failed with error: %s", str(e))
        raise Exception(f"Error while posting request: {e}")
    else:
        if response.status_code != 200:
            logger.error("Request failed with error: %s", str(e))
            raise Exception(f"Failed to obtain device code: {response.text}")
        response_json = response.json()
        device_code = response_json.get('device_code')
        user_code = response_json.get('user_code')
        verification_uri = response_json.get('verification_uri')
    logger.info("Authentication flow started.")
    print(f"Please visit this URL on any device and enter the following code to authorize the application:\n{verification_uri}\nCode: {user_code}")
    token_url = 'https://github.com/login/oauth/access_token'
    headers = {'Accept': 'application/json'}
    data = {
        'client_id': client_id,
        'device_code': device_code,
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
    }

    # Polling for access token
    while True:
        response = requests.post(token_url, headers=headers, data=data)
        error = response.json().get('error')
        if error == 'authorization_pending':
            logger.info("Authorization pending. Polling again in 5 seconds...")
            print("Authorization pending. Polling again in 5 seconds...")
            time.sleep(5)
        elif error == 'slow_down':
            logger.info("Polling too frequently. Waiting 10 seconds before polling again...")
            print("Polling too frequently. Waiting 10 seconds before polling again...")
            time.sleep(10)
        elif error is None:
            access_token = response.json().get('access_token')
            print("Authentication flow completed. Token has been obtained from Github.")
            logger.info("Authentication flow completed. Token has been obtained from Github.")
            return access_token
        else: 
            logger.error("Request failed with error: %s", str(e))
            raise Exception(f"Failed to obtain access token: {response.text}")

# Function to make requests with retry
def make_request_with_retry(url, headers, retries=5):
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

# Function to fetch required json data from Github
def getResponse(token):
    headers = {"Authorization": "Bearer "+token}
    url = "https://api.github.com/user/repos"
    try:
        data = make_request_with_retry(url, headers, retries=5)
        logger.info("Data fetched successfully from Github.")
        return data
    except requests.exceptions.HTTPError as e:
        logger.error("Request failed with error: %s", str(e))
        raise
    except requests.exceptions.RequestException as e:
        logger.error("Request failed with error: %s", str(e))
        raise
    except ValueError as e:
        logger.error("Invalid JSON response: %s", str(e))
        raise       

# Function to deduplicate data
def removeDuplicates(df):
    return df.drop_duplicates(subset=['id'], keep='first')

# Function to normalize data
def normalize(jsonData):
    ownerData=[]
    repoData=[]
    try:
        for repo in jsonData:
            ownerData+=[repo['owner']]
            repo['owner_id']=repo['owner']['id']
            repo.pop('owner', None)
            repoData+=[repo]
    except KeyError:
        logger.error("Key not found in JSON data")
        raise Exception("Key not found in JSON data")
    else:
        repoDataDf = removeDuplicates(pd.json_normalize(repoData))
        ownerDataDf = removeDuplicates(pd.json_normalize(ownerData))
        logger.info("Data normalized, deduplicated successfully.")
        return repoDataDf, ownerDataDf

# Function to load data to postgres DB
def loadToDB(df,name):
    try:
        engine = create_engine(f'postgresql://{creds.dbUser}:{creds.dbPassword}@{creds.dbHost}:{creds.dbPort}/{creds.dbName}')
    except (Exception) as error :
        logger.error("Error while connecting to PostgreSQL", error)
        raise Exception(f"Error while connecting to PostgreSQL: {error}")
    else:
        logger.info("Connected to postgres DB successfully.")
        df.to_sql(name, con=engine, if_exists='replace')
        engine.dispose()
        logger.info("Data loaded to postgres DB successfully.")
        print("Data loaded to DB successfully.")

# Function to make the required postgres query and write the output to a csv file
def postgresToCSV(csvFileName):
    try:
        conn = psycopg2.connect(f"dbname={creds.dbName} user={creds.dbUser} password={creds.dbPassword} host={creds.dbHost} port={creds.dbPort}")
        cur = conn.cursor()
    except (Exception) as error :
        logger.error("Error while connecting to PostgreSQL", error)
        raise Exception(f"Error while connecting to PostgreSQL: {error}")
    else:
        logger.info("PostgreSQL connection to query data successful.")
        try:
            sql = "COPY (select r.id as RepoID,r.name as RepoName,r.visibility as Status,r.stargazers_count as starsCount,o.id as ownerId,o.login as ownerName,o.gravatar_id as ownerEmail from repos r join owners o on r.owner_id = o.id) TO STDOUT WITH CSV DELIMITER ',' header"
            with open(csvFileName, "w") as file:
                cur.copy_expert(sql, file)
        except (Exception) as error :
            logger.error("Error in Postgres SQL Query", error)
            raise Exception(f"Error in Postgres SQL Query: {error}")
        else:
            logger.info("Data loaded from DB to CSV successfully.")
            conn.commit()
            cur.close()
            print(f"Data loaded to CSV successfully in {csvFileName}.")
            return pd.read_csv(csvFileName)

# Function to establish connection with Redis
def redis_connection():
    try:
        pool = redis.ConnectionPool(host=creds.redisHost, port=creds.redisPort, db=creds.redisDB)
        r = redis.Redis(connection_pool=pool)
    except (Exception) as e:
        logger.error("Redis connection is not ready. Error: " + str(e))
        raise Exception(f"Redis connection is not ready. Error: {str(e)}")
    else:
        logger.info("Redis connection successful.")
        return r

# Function to store data in Redis
def storeDataframeInRedis(r, key, df):
    try:
        df_serialized = pickle.dumps(df)
        r.set(key, df_serialized)
    except Exception as e:
        logger.error("Error while storing data in Redis. Error: " + str(e))
        raise Exception(f"Error while storing data in Redis. Error: {str(e)}")
    else:
        logger.info("Data stored in Redis successfully.")

# Function to get data from Redis
def getDataframeFromRedis(r, key):
    try:
        df_serialized = r.get(key)
        df = pickle.loads(df_serialized)
    except Exception as e:
        logger.error("Error while getting data from Redis. Error: " + str(e))
        raise Exception(f"Error while getting data from Redis. Error: {str(e)}")
    else:
        logger.info("Data loaded from Redis successfully.")
        return df

# Driver code
def main():
    logger.info("Starting the program.")
    # Get Github OAuth token
    try:
        token = perform_github_device_flow_oauth(creds.githubClientID)
    except Exception as e:
        print("Error while getting token from Github API."+str(e))
        print("Would you like to try again? (Y/N)")
        choice = input()
        while True:
            if choice == 'Y' or choice == 'y':
                try:
                    logger.info("Trying to get Github OAuth token again.")
                    token = perform_github_device_flow_oauth(creds.githubClientID)
                except Exception as e:
                    print("Error while getting token from Github API."+str(e))
                    print("Would you like to try again? (Y/N)")
                    choice = input()
                else:
                    logger.info("Github OAuth token fetched successfully.")
                    break
            elif choice == 'N' or choice == 'n':
                logger.info("User chose not to get Github OAuth token.")
                logger.info("Exiting the program.")
                logger.info("\n")
                print("Exiting the program.")
                sys.exit()
            else:
                print("Invalid choice. Please enter Y/N.")
                logger.info("Invalid choice entered by user while trying to get Github OAuth token.")
                choice = input()

    # Get data from Github API
    try:
        jsonData = getResponse(token)
    except Exception as e:
        print("Error while getting data from Github API despite retrying. No JSON Data recieved.")
        print("Exiting the program.")
        logger.error("Error while getting data from Github API despite retrying. No JSON Data recieved. Error: "+str(e))
        logger.info("Exiting the program.")
        logger.info("\n")
        sys.exit()
    
    # Normalize the data and store it in postgres DB
    try:
        repoDataDf, ownerDataDf = normalize(jsonData)
        loadToDB(repoDataDf, 'repos')
        loadToDB(ownerDataDf, 'owners')
    except Exception as e:
        print("Error while loading data to postgres DB."+str(e))
        print("Exiting the program.")
        logger.error("Error while loading data to postgres DB."+str(e))
        logger.info("Exiting the program.")
        logger.info("\n")
        sys.exit()
    logger.info("Data loaded to postgres DB successfully.")

    # Cache the data in Redis
    try:
        r = redis_connection()
        storeDataframeInRedis(r, 'repos', repoDataDf)
        storeDataframeInRedis(r, 'owners', ownerDataDf)
        r.close()
    except Exception as e:
        print("Error while caching data in Redis."+str(e))
        print("Exiting the program.")
        logger.error("Error while caching data in Redis."+str(e))
        logger.info("Exiting the program.")
        logger.info("\n")
        sys.exit()
    logger.info("Data cached in Redis successfully.")

    # Get data from postgres DB and store it in CSV
    try:
        resultDf = postgresToCSV("/var/lib/postgresql/data/result.csv")
    except Exception as e:
        print("Error while loading data to CSV."+str(e))
        print("Exiting the program.")
        logger.error("Error while loading data to CSV."+str(e))
        logger.info("Exiting the program.")
        logger.info("\n")
        sys.exit()
    
    # Cache the result data in Redis
    try:
        r = redis_connection()
        storeDataframeInRedis(r, 'result', resultDf)
        r.close()
    except Exception as e:
        print("Error while caching result data in Redis."+str(e))
        print("Exiting the program.")
        logger.error("Error while caching result data in Redis."+str(e))
        logger.info("Exiting the program.")
        logger.info("\n")
        sys.exit()
    
    # Get cached repos and owners data from Redis and print it if required by the user
    print("Would you like to view the cached repos.csv and owners.csv from Redis? (Y/N)")
    choice = input()
    while True:
        if choice == 'Y' or choice == 'y':
            logger.info("User chose to view the repos.csv and owners.csv from Redis.")
            try:
                r = redis_connection()
                reposRedisDf = getDataframeFromRedis(r, 'repos')
                ownersRedisDf = getDataframeFromRedis(r, 'owners')
                print(reposRedisDf)
                print(ownersRedisDf)
                logger.info("Repos and Owners data loaded from Redis successfully.")
                r.close()
            except Exception as e:
                logger.error("Error while getting data from Redis."+str(e))
                print("Error while getting data from Redis."+str(e))               
            finally:
                print("Thank you for using the application.")
                logger.info("Natural end of program.")
                logger.info("\n")
                break
        elif choice == 'N' or choice == 'n':
            print("Thank you for using the application.")
            logger.info("User chose not to view the cached repos.csv and owners.csv from Redis.")
            logger.info("Natural end of program.")
            logger.info("\n")
            break
        else:
            print("Invalid choice. Please enter Y/N.")
            logger.info("Invalid choice entered by user while trying to view the cached repos.csv and owners.csv from Redis.")
            choice = input()

    # Get cached result data from Redis and print it if required by the user
    print("Would you like to view the cached result.csv from Redis? (Y/N)")
    choice = input()
    while True:
        if choice == 'Y' or choice == 'y':
            logger.info("User chose to view the result.csv from Redis.")
            try:
                r = redis_connection()
                resultRedisDf = getDataframeFromRedis(r, 'result')
                print(resultRedisDf)
                logger.info("Result data loaded from Redis successfully.")
                r.close()
            except Exception as e:
                logger.error("Error while getting data from Redis."+str(e))
                print("Error while getting data from Redis."+str(e))               
            finally:
                print("Thank you for using the application.")
                logger.info("Natural end of program.")
                logger.info("\n")
                break
        elif choice == 'N' or choice == 'n':
            print("Thank you for using the application.")
            logger.info("User chose not to view the result.csv from Redis.")
            logger.info("Natural end of program.")
            logger.info("\n")
            break
        else:
            print("Please enter a valid choice.")
            logger.info("Invalid choice entered by user while trying to view the result.csv from Redis.")
            choice = input()