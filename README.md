[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-c66648af7eb3fe8bc4f294546bfd86ef473780cde1dea487d3c4ff354943c9ae.svg)](https://classroom.github.com/online_ide?assignment_repo_id=10771702&assignment_repo_type=AssignmentRepo)

## How to run the project
1. Clone the project
2. Open the project in Visual Studio Code
3. Ensure you have docker, redis and postgres installed
4. Create a folder called 'dbVol' in the root of the project
5. Create a file called creds.py in the root of the project. It should contain the following fields.

```python
#Create a new OAuth app in your github account from developer settings and get the client ID
githubClientID = "your github client id"

#Default user for postgres
dbUser = "postgres" 
dbPassword = "root"

#Get host ip as described in Appendix A
dbHost = "172.17.0.2" 
dbPort = "5432"
dbName = "balkanid"

#Get host ip as described in Appendix A
redisHost = "172.17.0.3"
redisPort = "6379"
redisDB = "0"
```

6. Open a terminal in Visual Studio Code
7. Run the following docker command to pull the postgres image and run it. This will create a container called postgres-container.

```
docker run --name postgres-container -e POSTGRES_PASSWORD=root -e POSTGRES_USER=postgres -e POSTGRES_DB=balkanid -v "path-to-dbVol:/var/lib/postgresql/data:rw" -p 5432:5432 -d postgres:14
```

8. Run the following docker command to pull the redis image and run it. This will create a container called redis-container.

```
docker run --name redis-container -d redis
```

9. Run the following docker command to build an image for the python project. 

```
docker build -t python-postgres-app .
```

10. Run the following docker command to create and run the python container. This will create a container called python-container.

```
docker run --name python-container -e POSTGRES_DB=balkanid -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=root -e POSTGRES_HOST=postgres-container -it python-postgres-app
```

11. Now follow the on-screen instructions to generate an OAuth token for the github API and run the program to completion.

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
