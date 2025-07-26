import datetime
import json
import sqlite3
from typing import Dict, Any, Callable, List


class ToolManager:
    """
    Manages tool registration and execution for the LLM system.
    Provides a modular way to handle database operations and other tools.
    """
    
    def __init__(self, database_name: str = 'contacts.db'):
        self.database_name = database_name
        self.tools: Dict[str, Callable] = {}
        self._register_tools()
    
    def _register_tools(self):
        """Register all available tools."""
        self.tools = {
            "get_current_datetime": self.get_current_datetime,
            "add_contact": self.add_contact,
            "get_contact": self.get_contact,
            "update_contact_summary": self.update_contact_summary,
            "delete_contact": self.delete_contact,
            "add_fact_to_contact": self.add_fact_to_contact,
            "update_fact_for_contact": self.update_fact_for_contact,
            "delete_fact_from_contact": self.delete_fact_from_contact,
            "update_graph": self.update_graph,
        }
    
    def get_available_tools(self) -> List[str]:
        """Return a list of available tool names."""
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
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        func = self.tools[tool_name]
        try:
            return func(**arguments)
        except TypeError as e:
            return f"Error: Incorrect arguments for tool '{tool_name}'. Details: {e}. Arguments provided: {arguments}"
        except Exception as e:
            return f"Error executing tool '{tool_name}': {e}"
    
    def register_tool(self, name: str, func: Callable):
        """
        Register a new tool function.
        
        Args:
            name: Name to register the tool under
            func: Function to execute for this tool
        """
        self.tools[name] = func
    
    def unregister_tool(self, name: str):
        """Remove a tool from the registry."""
        if name in self.tools:
            del self.tools[name]
    
    # --- Database Helper Methods ---
    
    def _get_db_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.database_name)
    
    # --- Tool Implementations ---
    
    def get_current_datetime(self) -> str:
        """
        Returns the current date and time in YYYY-MM-DD HH:MM:SS format.
        """
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def add_contact(self, name: str, summary: str = None) -> str:
        """Adds a new contact to the database."""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO contacts (name, summary) VALUES (?, ?)", (name, summary))
            conn.commit()
            contact_id = cursor.lastrowid
            return f"Contact '{name}' added successfully with ID: {contact_id}."
        except sqlite3.IntegrityError:
            return f"Error: Contact with name '{name}' already exists."
        finally:
            conn.close()
    
    def get_contact(self, contact_id: int = None, name: str = None) -> str:
        """Retrieves contact(s) from the database by ID or name, including all facts."""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        contacts = []
        fact_columns = ", ".join([f"fact_{i}" for i in range(1, 11)])
        select_query = f"SELECT id, name, summary, {fact_columns} FROM contacts"

        if contact_id:
            cursor.execute(f"{select_query} WHERE id = ?", (contact_id,))
        elif name:
            cursor.execute(f"{select_query} WHERE name LIKE ?", (f"%{name}%",))
        else:
            cursor.execute(select_query)

        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        conn.close()

        if not rows:
            return "No contact found matching the criteria."

        for row in rows:
            contact_data = {}
            for i, col_name in enumerate(column_names):
                contact_data[col_name] = row[i]
            contacts.append(contact_data)
        return json.dumps(contacts)
    
    def update_contact_summary(self, contact_id: int, new_summary: str) -> str:
        """Updates a contact's summary in the database."""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE contacts SET summary = ? WHERE id = ?", (new_summary, contact_id))
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        if rows_affected > 0:
            return f"Summary for contact ID {contact_id} updated successfully."
        else:
            return f"No contact found with ID {contact_id} to update."
    
    def delete_contact(self, contact_id: int) -> str:
        """Deletes a contact from the database."""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        if rows_affected > 0:
            return f"Contact with ID {contact_id} deleted successfully."
        else:
            return f"No contact found with ID {contact_id} to delete."
    
    def add_fact_to_contact(self, contact_id: int, fact_text: str) -> str:
        """
        Adds a fact to the next available fact_N column for a given contact.
        Returns an error if all 10 fact columns are full.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            # Check if contact_id exists and get current fact values
            cursor.execute(f"SELECT {', '.join([f'fact_{i}' for i in range(1, 11)])} FROM contacts WHERE id = ?", (contact_id,))
            current_facts = cursor.fetchone()

            if current_facts is None:
                return f"Error: Contact with ID {contact_id} does not exist. Cannot add fact."

            # Find the first available (NULL or empty string) fact column
            available_fact_column = -1
            for i, fact_value in enumerate(current_facts):
                if fact_value is None or (isinstance(fact_value, str) and fact_value.strip() == ""):
                    available_fact_column = i + 1  # Column number (1-indexed)
                    break

            if available_fact_column != -1:
                update_column_name = f"fact_{available_fact_column}"
                cursor.execute(f"UPDATE contacts SET {update_column_name} = ? WHERE id = ?", (fact_text, contact_id))
                conn.commit()
                return f"Fact added to contact ID {contact_id} in column '{update_column_name}'."
            else:
                return f"Error: All 10 fact columns for contact ID {contact_id} are already full. Please update or delete an existing fact."
        except Exception as e:
            return f"Error adding fact to contact: {e}"
        finally:
            conn.close()
    
    def update_fact_for_contact(self, contact_id: int, fact_number: int, new_fact_text: str) -> str:
        """Updates a specific fact (fact_N) for a given contact."""
        if not (1 <= fact_number <= 10):
            return "Error: Fact number must be between 1 and 10."

        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            update_column_name = f"fact_{fact_number}"
            cursor.execute(f"UPDATE contacts SET {update_column_name} = ? WHERE id = ?", (new_fact_text, contact_id))
            conn.commit()
            rows_affected = cursor.rowcount
            if rows_affected > 0:
                return f"Fact {fact_number} for contact ID {contact_id} updated successfully."
            else:
                return f"No contact found with ID {contact_id} to update fact {fact_number}."
        except Exception as e:
            return f"Error updating fact: {e}"
        finally:
            conn.close()
    
    def delete_fact_from_contact(self, contact_id: int, fact_number: int) -> str:
        """Deletes a specific fact (fact_N) for a given contact by setting it to NULL."""
        if not (1 <= fact_number <= 10):
            return "Error: Fact number must be between 1 and 10."

        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            delete_column_name = f"fact_{fact_number}"
            cursor.execute(f"UPDATE contacts SET {delete_column_name} = NULL WHERE id = ?", (contact_id,))
            conn.commit()
            rows_affected = cursor.rowcount
            if rows_affected > 0:
                return f"Fact {fact_number} for contact ID {contact_id} deleted successfully."
            else:
                return f"No contact found with ID {contact_id} to delete fact {fact_number}."
        except Exception as e:
            return f"Error deleting fact: {e}"
        finally:
            conn.close()
    
    def update_graph(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
        """
        Updates the property graph with nodes and edges extracted from conversation.
        
        Args:
            nodes: List of node dictionaries with 'id', 'label', and optional 'properties'
            edges: List of edge dictionaries with 'from', 'to', 'relationship', and optional 'properties'
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Create graph tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS graph_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_node TEXT NOT NULL,
                    to_node TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(from_node, to_node, relationship)
                )
            ''')
            
            nodes_added = 0
            edges_added = 0
            nodes_updated = 0
            edges_updated = 0
            
            # Insert or update nodes
            for node in nodes:
                node_id = node.get('id')
                label = node.get('label')
                properties = json.dumps(node.get('properties', {})) if node.get('properties') else None
                
                if not node_id or not label:
                    continue
                    
                # Check if node exists
                cursor.execute("SELECT id FROM graph_nodes WHERE id = ?", (node_id,))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("""
                        UPDATE graph_nodes 
                        SET label = ?, properties = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (label, properties, node_id))
                    nodes_updated += 1
                else:
                    cursor.execute("""
                        INSERT INTO graph_nodes (id, label, properties) 
                        VALUES (?, ?, ?)
                    """, (node_id, label, properties))
                    nodes_added += 1
            
            # Insert or update edges
            for edge in edges:
                from_node = edge.get('from')
                to_node = edge.get('to')
                relationship = edge.get('relationship')
                properties = json.dumps(edge.get('properties', {})) if edge.get('properties') else None
                
                if not from_node or not to_node or not relationship:
                    continue
                    
                # Check if edge exists
                cursor.execute("""
                    SELECT id FROM graph_edges 
                    WHERE from_node = ? AND to_node = ? AND relationship = ?
                """, (from_node, to_node, relationship))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("""
                        UPDATE graph_edges 
                        SET properties = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE from_node = ? AND to_node = ? AND relationship = ?
                    """, (properties, from_node, to_node, relationship))
                    edges_updated += 1
                else:
                    cursor.execute("""
                        INSERT INTO graph_edges (from_node, to_node, relationship, properties) 
                        VALUES (?, ?, ?, ?)
                    """, (from_node, to_node, relationship, properties))
                    edges_added += 1
            
            conn.commit()
            
            result_parts = []
            if nodes_added > 0:
                result_parts.append(f"{nodes_added} nodes added")
            if nodes_updated > 0:
                result_parts.append(f"{nodes_updated} nodes updated")
            if edges_added > 0:
                result_parts.append(f"{edges_added} edges added")
            if edges_updated > 0:
                result_parts.append(f"{edges_updated} edges updated")
                
            if result_parts:
                return f"Graph updated successfully: {', '.join(result_parts)}."
            else:
                return "No valid nodes or edges provided for graph update."
                
        except Exception as e:
            return f"Error updating graph: {e}"
        finally:
            conn.close()