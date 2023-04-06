import creds
import requests
import logging
import requests
import urllib3
import pandas as pd

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
    session.mount("http://", adapter)
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


if __name__ == '__main__':
    token = creds.githubToken
    try:
        jsonData = getResponse(token)
    except:
        print("No JSON Data recieved.")
    else:
        repoDataDf, ownerDataDf = normalize(jsonData)
        print(ownerDataDf)
    
    
