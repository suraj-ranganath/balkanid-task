# Balkan Internship Selection Task

This is an application that uses the Github API to fetch the repositories of a user in the json format when the user ends a request from port 8080. The user is authenticated using OAuth2. This data is then normalised, checked for duplicates and stored in a postgres database as 2 tables: repos and owners. The table is queried as required and the table is stored as a csv file. The repos, owners and result csv are all cached on Redis and displayed to the user if required. Additionally, the application is dockerized and can be run on any machine by following the steps below.

## Features
1. Github OAuth2 authentication
2. Github API
3. PostgreSQL database
4. Redis caching
5. Dockerization
6. Error handling and logging
7. Retrying failed requests
8. Endpoint for user to run the program

## Requirements
1. Python 3.9
2. Docker
3. Redis
4. Postgres

## How to run the project
You can obtain the image for the project by directly skipping to step 8. If there are IP address and port issues, you will want to build the image yourself. To do so, follow the steps below.

1. Clone the project
2. Open the project in Visual Studio Code
3. Create a folder called 'dbVol' in the root of the project
4. Create a file called creds.py in the root of the project. It should contain the following fields.

```python
#Create a new OAuth app in your github account from developer settings and get the client ID
githubClientID = "your github client id"

#Default user for postgres
dbUser = "postgres" 
dbPassword = "root"

#Get host ip as described in Appendix A
dbHost = "172.17.0.2" 
dbPort = "5432"
dbName = "database name"

#Get host ip as described in Appendix A
redisHost = "172.17.0.3"
redisPort = "6379"
redisDB = "0"
```

5. Open a terminal in Visual Studio Code
6. Run the following docker command to pull the postgres image and run it. This will create a container called postgres-container.

```
docker run --name postgres-container -e POSTGRES_PASSWORD=root -e POSTGRES_USER=postgres -e POSTGRES_DB=balkanid -v "path-to-dbVol:/var/lib/postgresql/data:rw" -p 5432:5432 -d postgres:14
```

7. Run the following docker command to pull the redis image and run it. This will create a container called redis-container.

```
docker run --name redis-container -d redis
```
8. Run the following command to pull the image for the python project from dockerhub. If this runs successfully,there is no need to build the image in step 9. Else, follow the steps below.

```
docker pull surajranganath/balkanid:latest
```

9. Run the following docker command to build an image for the python project. 

```
docker build -t python-postgres-app .
```

10. Run the following docker command to create and run the python container. This will create a container called python-container.

```
docker run --name python-container -e POSTGRES_DB=balkanid -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=root -e POSTGRES_HOST=postgres-container -v "path-to-dbVol:/var/lib/postgresql/data:rw" -p 8080:8080 -it python-postgres-app
```

11. Open a browser and go to http://localhost:8080 or use the curl command below in your terminal. This will run the program.

```
curl http://localhost:8080
```

12. Now follow the on-screen instructions to generate an OAuth token for the github API and run the program to completion. Result.csv will be stored in the dbVol folder.
13. Logs for the project can be found in logFile.log. The logs for the server can by found in server.log as well. It is stored in the dbVol folder and can be used to debug any issues.

## Notes

### Normalisation
The data is stored in the postgres database in the third normal form. To achieve this, the following steps were taken.
1. The data is stored in two tables: repos and owners. This eliminates partial and transitive dependencies. Owner_id is the primary key of the owners table and is a foreign key in the repos table.
2. The pandas.json_normalize() function is used to flatten the json data. This eliminates multivalued attributes.

The data here is put into third normal form to reduce redundancy of owners data. It also ensures data integrity by enforcing referential integrity among the tables. All required data can now be queried faster and more efficiently.

### Error handling and logging
1. The application logs all errors to logFile.log. This file is stored in the dbVol folder and can be used to debug any issues.
2. The application retries failed requests to the github api to fetch repositories 5 times before giving up. This is done to circumvent network issues.
3. The application also polls the github OAuth2 endpoint using device flow until the access token is recieved. Wait time between polls is decided according to the response recieved. 

## Appendix A
If you are running the project on a local machine, you will need to get the IP address of the postgres and redis containers. Follow the steps below to do so.

1. Set dbHost and redisHost to 'localhost' initially.
2. Run the postgres container as described in step 7 and the redis container as described in step 8.
3. Run the following docker command to get the container ID of each container.

```
docker ps
```

4. Run the following docker command to get the IP address of each container.

```
docker inspect <container ID> | grep "IPAddress"
```

5. Set dbHost and redisHost to the IP address of the respective containers.

## Appendix B
For dev purposes, to open in VS Code:


 [![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-c66648af7eb3fe8bc4f294546bfd86ef473780cde1dea487d3c4ff354943c9ae.svg)](https://classroom.github.com/online_ide?assignment_repo_id=10771702&assignment_repo_type=AssignmentRepo)
