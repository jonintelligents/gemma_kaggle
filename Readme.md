# Project Setup Guide

## Prerequisites

- Python 3.8+ installed
- Docker installed and running
- `uv` package manager installed (install with `pip install uv` if not already installed)

## Installation

### 1. Install Dependencies

Create a virtual environment and install the required packages:

```bash
uv venv 
source venv/bin/activate  # On Windows: venv\Scripts\activate
uv pip install -r requirements.txt  
```

### 2. Start the Backend Datastore (Neo4j)

Launch the Neo4j database using Docker:

```bash
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -d \
    -v $HOME/neo4j/data:/data \
    -v $HOME/neo4j/logs:/logs \
    -v $HOME/neo4j/import:/var/lib/neo4j/import \
    -v $HOME/neo4j/plugins:/plugins \
    --env NEO4J_AUTH=neo4j/password \
    neo4j:latest
```

**Note:** The default credentials are:
- Username: `neo4j`
- Password: `password`

You can access the Neo4j browser interface at: http://localhost:7474

### 3. Run the Application

Start the Streamlit UI using the module flag to ensure it picks up the correct virtual environment:

```bash
python -m streamlit run app.py
```

**Important:** Always use `python -m streamlit` instead of just `streamlit` to ensure the command uses the Python interpreter from your activated virtual environment and can access all installed dependencies.

The application will be available at: http://localhost:8501

## Useful Cypher Queries

Here are some basic Cypher queries for database management:

### Delete All Data
```cypher
MATCH (n)
DETACH DELETE n
```

### View All Relationships
```cypher
MATCH (n)-[r]-(m)
RETURN n, r, m
```

### View All Nodes
```cypher
MATCH (n)
RETURN n
```

### Count All Nodes
```cypher
MATCH (n)
RETURN count(n)
```

## Troubleshooting

### Common Issues

1. **Docker container already exists**: If you get an error about the container name already being used, remove the existing container:
   ```bash
   docker rm neo4j
   ```

2. **Port conflicts**: If ports 7474 or 7687 are already in use, stop other services using these ports or modify the port mapping in the Docker command.

3. **Permission issues with volumes**: On some systems, you may need to create the directories first:
   ```bash
   mkdir -p $HOME/neo4j/{data,logs,import,plugins}
   ```

4. **Virtual environment activation on Windows**: Use `venv\Scripts\activate` instead of `source venv/bin/activate`

### Stopping the Application

To stop the Neo4j container:
```bash
docker stop neo4j
```

To remove the container (data will persist in volumes):
```bash
docker rm neo4j
```

## Environment Configuration

For production use, consider:
- Changing the default Neo4j password
- Using environment variables for configuration
- Setting up proper data backup procedures
- Configuring appropriate memory limits for Neo4j