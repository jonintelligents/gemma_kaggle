import datetime
import json
from typing import Dict, Any, Callable, List, Optional
import logging
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, ClientError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Neo4jToolManager:
    """
    Manages tool registration and execution for the LLM system using Neo4j.
    Provides a modular way to handle graph database operations and other tools.
    All operations use upsert functionality - checking for existence and updating if found, creating if not.
    """
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password"):
        """
        Initialize the Neo4j ToolManager.
        
        Args:
            uri: Neo4j database URI
            user: Database username
            password: Database password
        """
        logging.info(f"Initializing Neo4jToolManager with URI: {uri}")
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.tools: Dict[str, Callable] = {}
        self._connect_to_database()
        self._register_tools()
        self._create_constraints()
    
    def _connect_to_database(self):
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test the connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logging.info("Successfully connected to Neo4j database")
        except ServiceUnavailable as e:
            logging.error(f"Failed to connect to Neo4j database: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error connecting to database: {e}")
            raise
    
    def _create_constraints(self):
        """Create necessary constraints and indexes."""
        try:
            with self.driver.session() as session:
                # Create unique constraint for Contact nodes
                session.run("CREATE CONSTRAINT contact_name_unique IF NOT EXISTS FOR (c:Contact) REQUIRE c.name IS UNIQUE")
                
                # Create indexes for better performance
                session.run("CREATE INDEX contact_id_index IF NOT EXISTS FOR (c:Contact) ON (c.id)")
                session.run("CREATE INDEX entity_id_index IF NOT EXISTS FOR (e:Entity) ON (e.id)")
                
                logging.info("Database constraints and indexes created successfully")
        except ClientError as e:
            logging.warning(f"Some constraints may already exist: {e}")
        except Exception as e:
            logging.error(f"Error creating constraints: {e}")
    
    def _register_tools(self):
        """Register all available tools."""
        logging.info("Registering tools...")
        self.tools = {
            "get_current_datetime": self.get_current_datetime,
            "add_contact": self.add_contact,
            "get_contact": self.get_contact,
            "delete_contact": self.delete_contact,
            "add_entity": self.add_entity,
            "delete_entity": self.delete_entity,
            "create_relationship": self.create_relationship,
            "delete_relationship": self.delete_relationship,
            "query_graph": self.query_graph,
            "get_contact_network": self.get_contact_network,
            "find_connections": self.find_connections,
            "add_fact_to_contact": self.add_fact_to_contact,
            "delete_fact_from_contact": self.delete_fact_from_contact,
            "bulk_update_graph": self.bulk_update_graph,
        }
        logging.info(f"Tools registered: {list(self.tools.keys())}")
    
    def get_available_tools(self) -> List[str]:
        """Return a list of available tool names."""
        logging.info("Getting available tools.")
        return list(self.tools.keys())
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a tool by name with the provided arguments.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool
            
        Returns:
            String result from the tool execution
        """
        logging.info(f"Attempting to execute tool: {tool_name} with arguments: {arguments}")
        if tool_name not in self.tools:
            logging.error(f"Unknown tool: {tool_name}")
            raise ValueError(f"Unknown tool: {tool_name}")
        
        func = self.tools[tool_name]
        try:
            result = func(**arguments)
            logging.info(f"Tool '{tool_name}' executed successfully.")
            return result
        except TypeError as e:
            logging.error(f"Error: Incorrect arguments for tool '{tool_name}'. Details: {e}. Arguments provided: {arguments}")
            return f"Error: Incorrect arguments for tool '{tool_name}'. Details: {e}. Arguments provided: {arguments}"
        except Exception as e:
            logging.error(f"Error executing tool '{tool_name}': {e}")
            return f"Error executing tool '{tool_name}': {e}"
    
    def register_tool(self, name: str, func: Callable):
        """Register a new tool function."""
        logging.info(f"Registering new tool: {name}")
        self.tools[name] = func
    
    def unregister_tool(self, name: str):
        """Remove a tool from the registry."""
        logging.info(f"Attempting to unregister tool: {name}")
        if name in self.tools:
            del self.tools[name]
            logging.info(f"Tool '{name}' unregistered successfully.")
        else:
            logging.warning(f"Tool '{name}' not found, cannot unregister.")
    
    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            logging.info("Neo4j driver connection closed")
    
    # --- Tool Implementations ---
    
    def get_current_datetime(self) -> str:
        """Returns the current date and time in YYYY-MM-DD HH:MM:SS format."""
        current_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"Returning current datetime: {current_dt}")
        return current_dt
    
    def add_contact(self, name: str, summary: str = None, properties: Dict[str, Any] = None) -> str:
        """
        Adds a new contact or updates existing contact in the graph database (UPSERT).
        
        Args:
            name: Contact name (used as unique identifier)
            summary: Optional summary
            properties: Additional properties as a dictionary
        """
        logging.info(f"Attempting to upsert contact: '{name}' with summary: '{summary}'")
        
        if properties is None:
            properties = {}
        
        # Prepare properties for upsert
        upsert_properties = properties.copy()
        upsert_properties['name'] = name
        if summary is not None:
            upsert_properties['summary'] = summary
        upsert_properties['updated_at'] = datetime.datetime.now().isoformat()
        
        try:
            with self.driver.session() as session:
                # Use MERGE for upsert functionality
                result = session.run(
                    """
                    MERGE (c:Contact {name: $name})
                    ON CREATE SET c += $upsert_properties, c.created_at = $timestamp
                    ON MATCH SET c += $upsert_properties
                    RETURN c.name as name, elementId(c) as id, 
                           CASE WHEN c.created_at = $timestamp THEN 'created' ELSE 'updated' END as action
                    """,
                    name=name, 
                    upsert_properties=upsert_properties,
                    timestamp=datetime.datetime.now().isoformat()
                )
                record = result.single()
                if record:
                    contact_id = record['id']
                    action = record['action']
                    logging.info(f"Contact '{name}' {action} successfully with ID: {contact_id}")
                    return f"Contact '{name}' {action} successfully with ID: {contact_id}"
                else:
                    return f"Error: Failed to upsert contact '{name}'"
                    
        except Exception as e:
            logging.error(f"Error upserting contact: {e}")
            return f"Error upserting contact: {e}"
    
    def get_contact(self, name: str = None, contact_id: str = None, include_relationships: bool = True) -> str:
        """
        Retrieves contact(s) from the graph database.
        
        Args:
            name: Contact name (supports partial matching)
            contact_id: Specific contact ID
            include_relationships: Whether to include related entities and relationships
        """
        logging.info(f"Attempting to retrieve contact(s) with ID: {contact_id}, Name: '{name}'")
        
        try:
            with self.driver.session() as session:
                if contact_id:
                    if include_relationships:
                        query = """
                        MATCH (c:Contact)
                        WHERE elementId(c) = $contact_id
                        OPTIONAL MATCH (c)-[r]-(related)
                        RETURN c, collect({relationship: type(r), direction: startNode(r) = c, related_node: related}) as relationships
                        """
                    else:
                        query = """
                        MATCH (c:Contact)
                        WHERE elementId(c) = $contact_id
                        RETURN c, [] as relationships
                        """
                    result = session.run(query, contact_id=contact_id)
                    
                elif name:
                    if include_relationships:
                        query = """
                        MATCH (c:Contact)
                        WHERE c.name CONTAINS $name
                        OPTIONAL MATCH (c)-[r]-(related)
                        RETURN c, collect({relationship: type(r), direction: startNode(r) = c, related_node: related}) as relationships
                        """
                    else:
                        query = """
                        MATCH (c:Contact)
                        WHERE c.name CONTAINS $name
                        RETURN c, [] as relationships
                        """
                    result = session.run(query, name=name)
                    
                else:
                    if include_relationships:
                        query = """
                        MATCH (c:Contact)
                        OPTIONAL MATCH (c)-[r]-(related)
                        RETURN c, collect({relationship: type(r), direction: startNode(r) = c, related_node: related}) as relationships
                        LIMIT 50
                        """
                    else:
                        query = """
                        MATCH (c:Contact)
                        RETURN c, [] as relationships
                        LIMIT 50
                        """
                    result = session.run(query)
                
                contacts = []
                for record in result:
                    contact_data = dict(record['c'])
                    contact_data['id'] = record['c'].element_id
                    contact_data['relationships'] = record['relationships']
                    contacts.append(contact_data)
                
                if not contacts:
                    logging.info("No contact found matching the criteria.")
                    return "No contact found matching the criteria."
                
                logging.info(f"Retrieved {len(contacts)} contact(s).")
                return json.dumps(contacts, indent=2)
                
        except Exception as e:
            logging.error(f"Error retrieving contact: {e}")
            return f"Error retrieving contact: {e}"
    
    def delete_contact(self, contact_id: str = None, name: str = None) -> str:
        """Deletes a contact and all its relationships from the graph database."""
        logging.info(f"Attempting to delete contact with ID: {contact_id}, Name: '{name}'")
        
        try:
            with self.driver.session() as session:
                if contact_id:
                    query = """
                    MATCH (c:Contact)
                    WHERE elementId(c) = $contact_id
                    DETACH DELETE c
                    RETURN count(c) as deleted_count
                    """
                    result = session.run(query, contact_id=contact_id)
                elif name:
                    query = """
                    MATCH (c:Contact)
                    WHERE c.name = $name
                    DETACH DELETE c
                    RETURN count(c) as deleted_count
                    """
                    result = session.run(query, name=name)
                else:
                    return "Error: Must provide either contact_id or name."
                
                record = result.single()
                deleted_count = record['deleted_count'] if record else 0
                
                if deleted_count > 0:
                    logging.info(f"Contact deleted successfully (count: {deleted_count}).")
                    return f"Contact deleted successfully."
                else:
                    logging.warning("No contact found to delete.")
                    return "No contact found to delete."
                    
        except Exception as e:
            logging.error(f"Error deleting contact: {e}")
            return f"Error deleting contact: {e}"
    
    def add_entity(self, entity_id: str, label: str, properties: Dict[str, Any] = None) -> str:
        """
        Adds a new entity or updates existing entity in the graph database (UPSERT).
        
        Args:
            entity_id: Unique identifier for the entity
            label: Node label (e.g., 'Person', 'Company', 'Event')
            properties: Additional properties as a dictionary
        """
        logging.info(f"Attempting to upsert entity: '{entity_id}' with label: '{label}'")
        
        if properties is None:
            properties = {}
        
        # Prepare properties for upsert
        upsert_properties = properties.copy()
        upsert_properties['id'] = entity_id
        upsert_properties['updated_at'] = datetime.datetime.now().isoformat()
        
        try:
            with self.driver.session() as session:
                # Use MERGE for upsert functionality with dynamic label
                query = f"""
                MERGE (e:{label} {{id: $entity_id}})
                ON CREATE SET e += $upsert_properties, e.created_at = $timestamp
                ON MATCH SET e += $upsert_properties
                RETURN e.id as id, elementId(e) as element_id,
                       CASE WHEN e.created_at = $timestamp THEN 'created' ELSE 'updated' END as action
                """
                result = session.run(query, 
                                   entity_id=entity_id, 
                                   upsert_properties=upsert_properties,
                                   timestamp=datetime.datetime.now().isoformat())
                record = result.single()
                
                if record:
                    element_id = record['element_id']
                    action = record['action']
                    logging.info(f"Entity '{entity_id}' with label '{label}' {action} successfully")
                    return f"Entity '{entity_id}' with label '{label}' {action} successfully with element ID: {element_id}"
                else:
                    return f"Error: Failed to upsert entity '{entity_id}'"
                    
        except Exception as e:
            logging.error(f"Error upserting entity: {e}")
            return f"Error upserting entity: {e}"
    
    def delete_entity(self, entity_id: str) -> str:
        """Deletes an entity and all its relationships from the graph database."""
        logging.info(f"Attempting to delete entity: '{entity_id}'")
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH (e)
                WHERE e.id = $entity_id
                DETACH DELETE e
                RETURN count(e) as deleted_count
                """
                result = session.run(query, entity_id=entity_id)
                record = result.single()
                deleted_count = record['deleted_count'] if record else 0
                
                if deleted_count > 0:
                    logging.info(f"Entity '{entity_id}' deleted successfully.")
                    return f"Entity '{entity_id}' deleted successfully."
                else:
                    logging.warning(f"No entity found with ID '{entity_id}' to delete.")
                    return f"No entity found with ID '{entity_id}' to delete."
                    
        except Exception as e:
            logging.error(f"Error deleting entity: {e}")
            return f"Error deleting entity: {e}"
    
    def create_relationship(self, from_id: str, to_id: str, relationship_type: str, properties: Dict[str, Any] = None) -> str:
        """
        Creates a relationship between two nodes or updates existing relationship (UPSERT).
        
        Args:
            from_id: ID of the source node
            to_id: ID of the target node
            relationship_type: Type of relationship (e.g., 'KNOWS', 'WORKS_AT', 'LOCATED_IN')
            properties: Additional properties for the relationship
        """
        logging.info(f"Attempting to upsert relationship: '{from_id}' -{relationship_type}-> '{to_id}'")
        
        if properties is None:
            properties = {}
        
        # Prepare properties for upsert
        upsert_properties = properties.copy()
        upsert_properties['updated_at'] = datetime.datetime.now().isoformat()
        
        try:
            with self.driver.session() as session:
                # First check if both nodes exist
                check_query = """
                MATCH (from), (to)
                WHERE (from.id = $from_id OR from.name = $from_id OR elementId(from) = $from_id)
                  AND (to.id = $to_id OR to.name = $to_id OR elementId(to) = $to_id)
                RETURN from, to
                """
                check_result = session.run(check_query, from_id=from_id, to_id=to_id)
                
                if not check_result.single():
                    return f"Error: One or both nodes not found (from: '{from_id}', to: '{to_id}')"
                
                # Use MERGE for relationship upsert
                query = f"""
                MATCH (from), (to)
                WHERE (from.id = $from_id OR from.name = $from_id OR elementId(from) = $from_id)
                  AND (to.id = $to_id OR to.name = $to_id OR elementId(to) = $to_id)
                MERGE (from)-[r:{relationship_type}]->(to)
                ON CREATE SET r += $upsert_properties, r.created_at = $timestamp
                ON MATCH SET r += $upsert_properties
                RETURN type(r) as relationship_type, elementId(r) as relationship_id,
                       CASE WHEN r.created_at = $timestamp THEN 'created' ELSE 'updated' END as action
                """
                result = session.run(query, 
                                   from_id=from_id, 
                                   to_id=to_id, 
                                   upsert_properties=upsert_properties,
                                   timestamp=datetime.datetime.now().isoformat())
                record = result.single()
                
                if record:
                    rel_id = record['relationship_id']
                    action = record['action']
                    logging.info(f"Relationship '{relationship_type}' {action} successfully")
                    return f"Relationship '{relationship_type}' {action} successfully between '{from_id}' and '{to_id}' with ID: {rel_id}"
                else:
                    return f"Error: Failed to upsert relationship"
                    
        except Exception as e:
            logging.error(f"Error upserting relationship: {e}")
            return f"Error upserting relationship: {e}"
    
    def delete_relationship(self, from_id: str, to_id: str, relationship_type: str) -> str:
        """Deletes a specific relationship between two nodes."""
        logging.info(f"Attempting to delete relationship: '{from_id}' -{relationship_type}-> '{to_id}'")
        
        try:
            with self.driver.session() as session:
                query = f"""
                MATCH (from)-[r:{relationship_type}]->(to)
                WHERE (from.id = $from_id OR from.name = $from_id OR elementId(from) = $from_id)
                  AND (to.id = $to_id OR to.name = $to_id OR elementId(to) = $to_id)
                DELETE r
                RETURN count(r) as deleted_count
                """
                result = session.run(query, from_id=from_id, to_id=to_id)
                record = result.single()
                deleted_count = record['deleted_count'] if record else 0
                
                if deleted_count > 0:
                    logging.info(f"Relationship '{relationship_type}' deleted successfully.")
                    return f"Relationship '{relationship_type}' between '{from_id}' and '{to_id}' deleted successfully."
                else:
                    logging.warning("No relationship found to delete.")
                    return "No relationship found to delete."
                    
        except Exception as e:
            logging.error(f"Error deleting relationship: {e}")
            return f"Error deleting relationship: {e}"
    
    def query_graph(self, cypher_query: str, parameters: Dict[str, Any] = None) -> str:
        """
        Execute a custom Cypher query against the graph database.
        
        Args:
            cypher_query: Cypher query string
            parameters: Query parameters
        """
        logging.info(f"Executing custom query: {cypher_query[:100]}...")
        
        if parameters is None:
            parameters = {}
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher_query, parameters)
                records = []
                
                for record in result:
                    # Convert record to dictionary, handling Neo4j objects
                    record_dict = {}
                    for key in record.keys():
                        value = record[key]
                        if hasattr(value, '__dict__'):
                            # Convert Neo4j objects to dictionaries
                            if hasattr(value, 'items'):
                                record_dict[key] = dict(value)
                            else:
                                record_dict[key] = str(value)
                        else:
                            record_dict[key] = value
                    records.append(record_dict)
                
                logging.info(f"Query executed successfully, returned {len(records)} records.")
                return json.dumps(records, indent=2)
                
        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return f"Error executing query: {e}"
    
    def get_contact_network(self, contact_name: str, depth: int = 2) -> str:
        """
        Gets the network of connections for a specific contact up to a certain depth.
        
        Args:
            contact_name: Name of the contact
            depth: How many relationship hops to include (default: 2)
        """
        logging.info(f"Getting network for contact '{contact_name}' with depth {depth}")
        
        try:
            with self.driver.session() as session:
                query = f"""
                MATCH path = (c:Contact {{name: $contact_name}})-[*1..{depth}]-(connected)
                RETURN c as center_contact, 
                       collect(distinct connected) as connected_nodes,
                       collect(distinct relationships(path)) as all_relationships
                """
                result = session.run(query, contact_name=contact_name)
                record = result.single()
                
                if record:
                    network_data = {
                        'center_contact': dict(record['center_contact']),
                        'connected_nodes': [dict(node) for node in record['connected_nodes']],
                        'relationships': []
                    }
                    
                    # Process relationships
                    for rel_list in record['all_relationships']:
                        for rel in rel_list:
                            network_data['relationships'].append({
                                'type': rel.type,
                                'properties': dict(rel)
                            })
                    
                    logging.info(f"Retrieved network with {len(network_data['connected_nodes'])} connected nodes.")
                    return json.dumps(network_data, indent=2)
                else:
                    return f"No contact found with name '{contact_name}'"
                    
        except Exception as e:
            logging.error(f"Error getting contact network: {e}")
            return f"Error getting contact network: {e}"
    
    def find_connections(self, contact1: str, contact2: str, max_depth: int = 3) -> str:
        """
        Finds the shortest path(s) between two contacts.
        
        Args:
            contact1: First contact name
            contact2: Second contact name  
            max_depth: Maximum relationship hops to search
        """
        logging.info(f"Finding connections between '{contact1}' and '{contact2}'")
        
        try:
            with self.driver.session() as session:
                query = f"""
                MATCH (c1:Contact {{name: $contact1}}), (c2:Contact {{name: $contact2}})
                MATCH path = shortestPath((c1)-[*1..{max_depth}]-(c2))
                RETURN path, length(path) as path_length
                ORDER BY path_length
                LIMIT 5
                """
                result = session.run(query, contact1=contact1, contact2=contact2)
                
                paths = []
                for record in result:
                    path_data = {
                        'length': record['path_length'],
                        'nodes': [dict(node) for node in record['path'].nodes],
                        'relationships': [{'type': rel.type, 'properties': dict(rel)} for rel in record['path'].relationships]
                    }
                    paths.append(path_data)
                
                if paths:
                    logging.info(f"Found {len(paths)} connection path(s).")
                    return json.dumps({'paths': paths}, indent=2)
                else:
                    return f"No connections found between '{contact1}' and '{contact2}' within {max_depth} hops."
                    
        except Exception as e:
            logging.error(f"Error finding connections: {e}")
            return f"Error finding connections: {e}"
    
    def add_fact_to_contact(self, contact_id: str, fact_text: str) -> str:
        """Adds a fact as a property to a contact using upsert functionality."""
        try:
            # Get current facts count
            with self.driver.session() as session:
                query = """
                MATCH (c:Contact)
                WHERE elementId(c) = $contact_id OR c.name = $contact_id
                RETURN c, 
                       size([key in keys(c) WHERE key STARTS WITH 'fact_']) as fact_count
                """
                result = session.run(query, contact_id=contact_id)
                record = result.single()
                
                if not record:
                    return f"Error: Contact with ID '{contact_id}' does not exist."
                
                fact_count = record['fact_count']
                if fact_count >= 10:
                    return "Error: All 10 fact slots are full. Please delete an existing fact first."
                
                # Add new fact using upsert pattern
                next_fact_num = fact_count + 1
                update_query = f"""
                MATCH (c:Contact)
                WHERE elementId(c) = $contact_id OR c.name = $contact_id
                SET c.fact_{next_fact_num} = $fact_text,
                    c.updated_at = $timestamp
                RETURN c.name as name
                """
                
                timestamp = datetime.datetime.now().isoformat()
                result = session.run(update_query, contact_id=contact_id, fact_text=fact_text, timestamp=timestamp)
                record = result.single()
                
                if record:
                    logging.info(f"Fact added to contact '{record['name']}' in fact_{next_fact_num}")
                    return f"Fact added to contact '{record['name']}' in fact_{next_fact_num}"
                else:
                    return "Error: Failed to add fact to contact"
                    
        except Exception as e:
            logging.error(f"Error adding fact to contact: {e}")
            return f"Error adding fact to contact: {e}"
    
    def delete_fact_from_contact(self, contact_id: str, fact_number: int) -> str:
        """Deletes a specific fact from a contact."""
        if not (1 <= fact_number <= 10):
            return "Error: Fact number must be between 1 and 10."
        
        logging.info(f"Deleting fact {fact_number} from contact {contact_id}")
        
        try:
            with self.driver.session() as session:
                query = f"""
                MATCH (c:Contact)
                WHERE elementId(c) = $contact_id OR c.name = $contact_id
                REMOVE c.fact_{fact_number}
                SET c.updated_at = $timestamp
                RETURN c.name as name
                """
                
                timestamp = datetime.datetime.now().isoformat()
                result = session.run(query, contact_id=contact_id, timestamp=timestamp)
                record = result.single()
                
                if record:
                    logging.info(f"Fact {fact_number} deleted from contact '{record['name']}'")
                    return f"Fact {fact_number} deleted from contact '{record['name']}' successfully"
                else:
                    return f"No contact found with ID '{contact_id}' to delete fact {fact_number}"
                    
        except Exception as e:
            logging.error(f"Error deleting fact: {e}")
            return f"Error deleting fact: {e}"
    
    def bulk_update_graph(self, nodes: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> str:
        """
        Bulk upsert the graph with multiple nodes and relationships.
        
        Args:
            nodes: List of node dictionaries with 'id', 'label', and optional 'properties'
            relationships: List of relationship dictionaries with 'from', 'to', 'type', and optional 'properties'
        """
        logging.info(f"Bulk upserting graph with {len(nodes)} nodes and {len(relationships)} relationships")
        
        try:
            with self.driver.session() as session:
                nodes_created = 0
                nodes_updated = 0
                relationships_created = 0
                relationships_updated = 0
                
                # Process nodes with upsert
                for node in nodes:
                    node_id = node.get('id')
                    label = node.get('label', 'Entity')
                    properties = node.get('properties', {})
                    
                    if not node_id:
                        logging.warning(f"Skipping node without ID: {node}")
                        continue
                    
                    upsert_properties = properties.copy()
                    upsert_properties['id'] = node_id
                    upsert_properties['updated_at'] = datetime.datetime.now().isoformat()
                    
                    # Use MERGE for upsert
                    query = f"""
                    MERGE (n:{label} {{id: $node_id}})
                    ON CREATE SET n += $upsert_properties, n.created_at = $timestamp
                    ON MATCH SET n += $upsert_properties
                    RETURN CASE WHEN n.created_at = $timestamp THEN 'created' ELSE 'updated' END as action
                    """
                    
                    timestamp = datetime.datetime.now().isoformat()
                    result = session.run(query, node_id=node_id, upsert_properties=upsert_properties, timestamp=timestamp)
                    record = result.single()
                    
                    if record:
                        if record['action'] == 'created':
                            nodes_created += 1
                            logging.debug(f"Node '{node_id}' created with label '{label}'")
                        else:
                            nodes_updated += 1
                            logging.debug(f"Node '{node_id}' updated")
                
                # Process relationships with upsert
                for rel in relationships:
                    from_id = rel.get('from')
                    to_id = rel.get('to')
                    rel_type = rel.get('type', 'RELATED_TO')
                    properties = rel.get('properties', {})
                    
                    if not from_id or not to_id:
                        logging.warning(f"Skipping relationship without from/to IDs: {rel}")
                        continue
                    
                    upsert_properties = properties.copy()
                    upsert_properties['updated_at'] = datetime.datetime.now().isoformat()
                    
                    # Use MERGE for relationship upsert
                    query = f"""
                    MATCH (from), (to)
                    WHERE from.id = $from_id AND to.id = $to_id
                    MERGE (from)-[r:{rel_type}]->(to)
                    ON CREATE SET r += $upsert_properties, r.created_at = $timestamp
                    ON MATCH SET r += $upsert_properties
                    RETURN CASE WHEN r.created_at = $timestamp THEN 'created' ELSE 'updated' END as action
                    """
                    
                    timestamp = datetime.datetime.now().isoformat()
                    result = session.run(query, from_id=from_id, to_id=to_id, upsert_properties=upsert_properties, timestamp=timestamp)
                    record = result.single()
                    
                    if record:
                        if record['action'] == 'created':
                            relationships_created += 1
                            logging.debug(f"Relationship '{from_id}-{rel_type}->{to_id}' created")
                        else:
                            relationships_updated += 1
                            logging.debug(f"Relationship '{from_id}-{rel_type}->{to_id}' updated")
                    else:
                        logging.warning(f"Failed to upsert relationship: {from_id}-{rel_type}->{to_id} (nodes may not exist)")
                
                # Prepare result message
                result_parts = []
                if nodes_created > 0:
                    result_parts.append(f"{nodes_created} nodes created")
                if nodes_updated > 0:
                    result_parts.append(f"{nodes_updated} nodes updated")
                if relationships_created > 0:
                    result_parts.append(f"{relationships_created} relationships created")
                if relationships_updated > 0:
                    result_parts.append(f"{relationships_updated} relationships updated")
                
                if result_parts:
                    final_message = f"Graph bulk upsert completed: {', '.join(result_parts)}."
                    logging.info(final_message)
                    return final_message
                else:
                    logging.info("No valid nodes or relationships provided for bulk upsert.")
                    return "No valid nodes or relationships provided for bulk upsert."
                    
        except Exception as e:
            logging.error(f"Error in bulk graph upsert: {e}")
            return f"Error in bulk graph upsert: {e}"


# Example usage and setup
if __name__ == "__main__":
    # Initialize the tool manager
    tool_manager = Neo4jToolManager(
        uri="bolt://localhost:7687",
        user="neo4j", 
        password="your_password"
    )
    
    try:
        # Example: Add a contact (will create or update)
        result = tool_manager.execute_tool("add_contact", {
            "name": "John Doe",
            "summary": "Software engineer and tech enthusiast",
            "properties": {
                "email": "john.doe@example.com",
                "phone": "+1-555-0123",
                "location": "San Francisco, CA"
            }
        })
        print("Add contact result:", result)
        
        # Example: Add the same contact again with updated info (will update)
        result = tool_manager.execute_tool("add_contact", {
            "name": "John Doe",
            "summary": "Senior Software engineer and tech enthusiast",
            "properties": {
                "email": "john.doe@example.com",
                "phone": "+1-555-0123",
                "location": "San Francisco, CA",
                "skills": ["Python", "JavaScript", "Neo4j"]
            }
        })
        print("Update contact result:", result)
        
        # Example: Add an entity (will create or update)
        result = tool_manager.execute_tool("add_entity", {
            "entity_id": "acme_corp",
            "label": "Company",
            "properties": {
                "name": "Acme Corporation",
                "industry": "Technology",
                "size": "500-1000 employees",
                "founded": "2010"
            }
        })
        print("Add entity result:", result)
        
        # Example: Create a relationship (will create or update)
        result = tool_manager.execute_tool("create_relationship", {
            "from_id": "John Doe",
            "to_id": "acme_corp", 
            "relationship_type": "WORKS_AT",
            "properties": {
                "position": "Senior Software Engineer",
                "start_date": "2022-01-15",
                "department": "Engineering"
            }
        })
        print("Create relationship result:", result)
        
        # Example: Update the same relationship (will update properties)
        result = tool_manager.execute_tool("create_relationship", {
            "from_id": "John Doe",
            "to_id": "acme_corp", 
            "relationship_type": "WORKS_AT",
            "properties": {
                "position": "Principal Software Engineer",  # Updated position
                "start_date": "2022-01-15",
                "department": "Engineering",
                "promotion_date": "2024-01-15"  # New property
            }
        })
        print("Update relationship result:", result)
        
        # Example: Query the graph
        result = tool_manager.execute_tool("query_graph", {
            "cypher_query": """
            MATCH (c:Contact)-[r:WORKS_AT]->(company:Company)
            RETURN c.name as contact_name, 
                   r.position as position,
                   company.name as company_name,
                   r.promotion_date as promotion_date
            """,
            "parameters": {}
        })
        print("Query result:", result)
        
        # Example: Bulk upsert
        result = tool_manager.execute_tool("bulk_update_graph", {
            "nodes": [
                {
                    "id": "jane_smith",
                    "label": "Contact",
                    "properties": {
                        "name": "Jane Smith",
                        "email": "jane@acme.com",
                        "department": "Marketing"
                    }
                },
                {
                    "id": "tech_dept",
                    "label": "Department",
                    "properties": {
                        "name": "Technology Department",
                        "budget": 5000000
                    }
                }
            ],
            "relationships": [
                {
                    "from": "jane_smith",
                    "to": "acme_corp",
                    "type": "WORKS_AT",
                    "properties": {
                        "position": "Marketing Manager",
                        "start_date": "2023-03-01"
                    }
                },
                {
                    "from": "acme_corp",
                    "to": "tech_dept",
                    "type": "HAS_DEPARTMENT",
                    "properties": {
                        "established": "2010"
                    }
                }
            ]
        })
        print("Bulk upsert result:", result)
        
    finally:
        # Always close the connection
        tool_manager.close()