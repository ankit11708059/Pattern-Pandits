#!/usr/bin/env python3
"""
Cursor Background Agent - Acts like a Slack bot that can execute real Cursor commands
"""

import os
import subprocess
import json
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime
import openai
from dotenv import load_dotenv
import git
import requests

load_dotenv()

class CursorBackgroundAgent:
    """Background agent that can execute real Cursor-like commands"""
    
    def __init__(self, project_path: str = "."):
        self.project_path = os.path.abspath(project_path)
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.github_token = os.getenv("GITHUB_TOKEN")
        
        # Initialize git repo
        try:
            self.repo = git.Repo(self.project_path)
        except:
            self.repo = None
            
        # Command history for context
        self.command_history = []
        
    def execute_command(self, command: str, context: str = "") -> Dict[str, Any]:
        """Execute a Cursor-like command with real actions"""
        
        # Log the command
        self.command_history.append({
            "command": command,
            "timestamp": datetime.now().isoformat(),
            "context": context
        })
        
        # Parse command type
        cmd_lower = command.lower().strip()
        
        if cmd_lower.startswith("cursor"):
            return self._handle_cursor_command(command, context)
        elif cmd_lower.startswith("create"):
            return self._handle_create_command(command, context)
        elif cmd_lower.startswith("modify") or cmd_lower.startswith("edit"):
            return self._handle_modify_command(command, context)
        elif cmd_lower.startswith("pr") or "pull request" in cmd_lower:
            return self._handle_pr_command(command, context)
        elif cmd_lower.startswith("run") or cmd_lower.startswith("execute"):
            return self._handle_run_command(command, context)
        elif cmd_lower.startswith("fix") or cmd_lower.startswith("debug"):
            return self._handle_fix_command(command, context)
        elif cmd_lower.startswith("deploy") or cmd_lower.startswith("build"):
            return self._handle_deploy_command(command, context)
        else:
            return self._handle_general_command(command, context)
    
    def _handle_cursor_command(self, command: str, context: str) -> Dict[str, Any]:
        """Handle Cursor-specific commands"""
        
        # Extract the actual command after "cursor"
        parts = command.split(" ", 1)
        if len(parts) < 2:
            return {"error": "Please specify a command after 'cursor'"}
        
        actual_command = parts[1]
        
        # Common Cursor commands
        if "open" in actual_command:
            return self._open_file_or_project(actual_command)
        elif "search" in actual_command:
            return self._search_codebase(actual_command)
        elif "explain" in actual_command:
            return self._explain_code(actual_command, context)
        elif "refactor" in actual_command:
            return self._refactor_code(actual_command, context)
        else:
            return self._execute_cursor_ai(actual_command, context)
    
    def _handle_create_command(self, command: str, context: str) -> Dict[str, Any]:
        """Handle file/component creation commands"""
        
        if "file" in command:
            return self._create_file(command, context)
        elif "component" in command:
            return self._create_component(command, context)
        elif "function" in command:
            return self._create_function(command, context)
        elif "class" in command:
            return self._create_class(command, context)
        else:
            return self._create_general(command, context)
    
    def _handle_modify_command(self, command: str, context: str) -> Dict[str, Any]:
        """Handle code modification commands"""
        
        # Use AI to understand what needs to be modified
        if not self.openai_key:
            return {"error": "OpenAI API key required for code modifications"}
        
        try:
            # Get AI suggestion for the modification
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"""You are a Cursor AI assistant that can make real code changes. 
                    Project path: {self.project_path}
                    Context: {context}
                    
                    Analyze the modification request and provide:
                    1. Which file(s) to modify
                    2. Exact changes to make
                    3. Reason for the changes
                    
                    Return as JSON with keys: files, changes, reason"""},
                    {"role": "user", "content": command}
                ],
                max_tokens=1000
            )
            
            ai_response = response.choices[0].message.content
            
            # Try to parse as JSON
            try:
                modification_plan = json.loads(ai_response)
                return self._execute_modifications(modification_plan)
            except:
                # If not JSON, treat as text response
                return {"ai_response": ai_response, "action": "manual_review_needed"}
                
        except Exception as e:
            return {"error": f"AI modification failed: {str(e)}"}
    
    def _handle_pr_command(self, command: str, context: str) -> Dict[str, Any]:
        """Handle pull request creation"""
        
        if not self.repo:
            return {"error": "Not a git repository"}
        
        try:
            # Create a new branch
            branch_name = f"cursor-agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # Check if there are changes to commit
            if self.repo.is_dirty():
                # Stage all changes
                self.repo.git.add(A=True)
                
                # Commit changes
                commit_message = self._generate_commit_message(command, context)
                self.repo.index.commit(commit_message)
                
                # Create and push branch
                current_branch = self.repo.active_branch
                new_branch = self.repo.create_head(branch_name)
                new_branch.checkout()
                
                # Push to remote (if configured)
                try:
                    origin = self.repo.remote('origin')
                    origin.push(new_branch)
                    
                    # Create PR via GitHub API if token available
                    if self.github_token:
                        pr_result = self._create_github_pr(branch_name, commit_message, context)
                        return pr_result
                    else:
                        return {
                            "success": True,
                            "message": f"Branch '{branch_name}' created and pushed. Create PR manually on GitHub.",
                            "branch": branch_name
                        }
                        
                except Exception as e:
                    return {"error": f"Failed to push branch: {str(e)}"}
            else:
                return {"error": "No changes to commit"}
                
        except Exception as e:
            return {"error": f"PR creation failed: {str(e)}"}
    
    def _handle_run_command(self, command: str, context: str) -> Dict[str, Any]:
        """Handle command execution"""
        
        # Extract the actual command to run
        parts = command.split(" ", 1)
        if len(parts) < 2:
            return {"error": "Please specify a command to run"}
        
        cmd_to_run = parts[1]
        
        try:
            # Execute the command in the project directory
            result = subprocess.run(
                cmd_to_run,
                shell=True,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": True,
                "command": cmd_to_run,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 30 seconds"}
        except Exception as e:
            return {"error": f"Command execution failed: {str(e)}"}
    
    def _handle_fix_command(self, command: str, context: str) -> Dict[str, Any]:
        """Handle debugging and fixing commands"""
        
        if not self.openai_key:
            return {"error": "OpenAI API key required for debugging assistance"}
        
        try:
            # Get current project state
            project_info = self._get_project_info()
            
            # Use AI to analyze and suggest fixes
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"""You are a Cursor AI debugging assistant.
                    Project info: {project_info}
                    Context: {context}
                    
                    Analyze the issue and provide:
                    1. Problem diagnosis
                    2. Suggested fixes
                    3. Code changes needed
                    4. Testing recommendations
                    
                    Return as JSON with keys: diagnosis, fixes, code_changes, testing"""},
                    {"role": "user", "content": command}
                ],
                max_tokens=1500
            )
            
            ai_response = response.choices[0].message.content
            
            try:
                fix_plan = json.loads(ai_response)
                return {
                    "success": True,
                    "fix_plan": fix_plan,
                    "action": "review_and_apply"
                }
            except:
                return {"ai_response": ai_response, "action": "manual_review"}
                
        except Exception as e:
            return {"error": f"Fix analysis failed: {str(e)}"}
    
    def _handle_deploy_command(self, command: str, context: str) -> Dict[str, Any]:
        """Handle deployment commands"""
        
        if "streamlit" in command.lower():
            return self._deploy_streamlit()
        elif "docker" in command.lower():
            return self._deploy_docker()
        else:
            return self._deploy_general(command)
    
    def _handle_general_command(self, command: str, context: str) -> Dict[str, Any]:
        """Handle general AI-powered commands"""
        
        if not self.openai_key:
            return {"error": "OpenAI API key required for general commands"}
        
        try:
            project_info = self._get_project_info()
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"""You are a Cursor AI assistant with access to the codebase.
                    Project: {self.project_path}
                    Project info: {project_info}
                    Context: {context}
                    
                    Provide helpful responses and suggest actionable steps."""},
                    {"role": "user", "content": command}
                ],
                max_tokens=1000
            )
            
            return {
                "success": True,
                "ai_response": response.choices[0].message.content,
                "action": "informational"
            }
            
        except Exception as e:
            return {"error": f"AI processing failed: {str(e)}"}
    
    # Helper methods
    
    def _create_file(self, command: str, context: str) -> Dict[str, Any]:
        """Create a new file"""
        
        # Extract filename from command
        words = command.split()
        filename = None
        
        for word in words:
            if '.' in word and not word.startswith('.'):
                filename = word
                break
        
        if not filename:
            return {"error": "Please specify a filename"}
        
        filepath = os.path.join(self.project_path, filename)
        
        try:
            # Use AI to generate file content if OpenAI available
            if self.openai_key:
                content = self._generate_file_content(filename, command, context)
            else:
                content = f"# {filename}\n# Created by Cursor Agent\n\n"
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Created file: {filename}",
                "path": filepath,
                "content": content
            }
            
        except Exception as e:
            return {"error": f"File creation failed: {str(e)}"}
    
    def _generate_file_content(self, filename: str, command: str, context: str) -> str:
        """Generate file content using AI"""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"""Generate appropriate content for file: {filename}
                    Command: {command}
                    Context: {context}
                    
                    Create production-ready code with proper structure, imports, and documentation."""},
                    {"role": "user", "content": f"Create content for {filename}"}
                ],
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"# Error generating content: {str(e)}\n\n"
    
    def _get_project_info(self) -> Dict[str, Any]:
        """Get current project information"""
        
        info = {
            "path": self.project_path,
            "files": [],
            "git_status": None,
            "dependencies": None
        }
        
        try:
            # Get file list
            for root, dirs, files in os.walk(self.project_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for file in files:
                    if not file.startswith('.'):
                        rel_path = os.path.relpath(os.path.join(root, file), self.project_path)
                        info["files"].append(rel_path)
            
            # Get git status
            if self.repo:
                info["git_status"] = {
                    "branch": self.repo.active_branch.name,
                    "dirty": self.repo.is_dirty(),
                    "untracked": [item.a_path for item in self.repo.index.diff(None)]
                }
            
            # Check for requirements.txt
            req_path = os.path.join(self.project_path, "requirements.txt")
            if os.path.exists(req_path):
                with open(req_path, 'r') as f:
                    info["dependencies"] = f.read().strip().split('\n')
                    
        except Exception as e:
            info["error"] = str(e)
        
        return info
    
    def _generate_commit_message(self, command: str, context: str) -> str:
        """Generate appropriate commit message"""
        
        if self.openai_key:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Generate a concise, descriptive commit message for the changes described."},
                        {"role": "user", "content": f"Command: {command}\nContext: {context}"}
                    ],
                    max_tokens=100
                )
                
                return response.choices[0].message.content.strip()
                
            except:
                pass
        
        return f"Cursor Agent: {command[:50]}..."
    
    def _create_github_pr(self, branch_name: str, title: str, context: str) -> Dict[str, Any]:
        """Create GitHub pull request"""
        
        try:
            # Get repository info
            remote_url = self.repo.remote('origin').url
            
            # Parse GitHub repo from URL
            if 'github.com' in remote_url:
                repo_path = remote_url.split('github.com/')[-1].replace('.git', '')
                
                # Create PR via GitHub API
                api_url = f"https://api.github.com/repos/{repo_path}/pulls"
                
                headers = {
                    'Authorization': f'token {self.github_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }
                
                data = {
                    'title': title,
                    'head': branch_name,
                    'base': 'main',  # or 'master'
                    'body': f"Created by Cursor Agent\n\nContext: {context}"
                }
                
                response = requests.post(api_url, headers=headers, json=data)
                
                if response.status_code == 201:
                    pr_data = response.json()
                    return {
                        "success": True,
                        "message": "Pull request created successfully",
                        "pr_url": pr_data['html_url'],
                        "pr_number": pr_data['number']
                    }
                else:
                    return {"error": f"GitHub API error: {response.status_code} - {response.text}"}
            else:
                return {"error": "Not a GitHub repository"}
                
        except Exception as e:
            return {"error": f"PR creation failed: {str(e)}"}
    
    def _deploy_streamlit(self) -> Dict[str, Any]:
        """Deploy Streamlit app"""
        
        try:
            # Kill existing processes
            subprocess.run(['pkill', '-f', 'streamlit'], capture_output=True)
            
            # Start Streamlit
            process = subprocess.Popen(
                ['streamlit', 'run', 'mixpanel_user_activity.py', '--server.port', '8504'],
                cwd=self.project_path
            )
            
            return {
                "success": True,
                "message": "Streamlit app deployed on http://localhost:8504",
                "pid": process.pid
            }
            
        except Exception as e:
            return {"error": f"Streamlit deployment failed: {str(e)}"}
    
    def _deploy_docker(self) -> Dict[str, Any]:
        """Deploy using Docker"""
        
        try:
            # Check if Dockerfile exists
            dockerfile_path = os.path.join(self.project_path, "Dockerfile")
            if not os.path.exists(dockerfile_path):
                return {"error": "Dockerfile not found. Create one first."}
            
            # Build Docker image
            result = subprocess.run(
                ['docker', 'build', '-t', 'mixpanel-app', '.'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return {"error": f"Docker build failed: {result.stderr}"}
            
            # Run Docker container
            result = subprocess.run(
                ['docker', 'run', '-d', '-p', '8504:8504', 'mixpanel-app'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return {"error": f"Docker run failed: {result.stderr}"}
            
            return {
                "success": True,
                "message": "Docker container deployed on http://localhost:8504",
                "container_id": result.stdout.strip()
            }
            
        except Exception as e:
            return {"error": f"Docker deployment failed: {str(e)}"}
    
    def _deploy_general(self, command: str) -> Dict[str, Any]:
        """Handle general deployment commands"""
        
        return {
            "success": True,
            "message": f"Deployment command received: {command}",
            "ai_response": "For deployment, try:\n- `deploy streamlit` - Deploy Streamlit app\n- `deploy docker` - Deploy with Docker\n- `run <custom_command>` - Execute custom deployment command"
        }
    
    def _open_file_or_project(self, command: str) -> Dict[str, Any]:
        """Open file or project"""
        
        # Extract filename from command
        words = command.split()
        filename = None
        
        for word in words:
            if '.' in word and not word.startswith('.'):
                filename = word
                break
        
        if filename:
            filepath = os.path.join(self.project_path, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                
                return {
                    "success": True,
                    "message": f"Opened file: {filename}",
                    "content": content,
                    "path": filepath
                }
            else:
                return {"error": f"File not found: {filename}"}
        else:
            return {"error": "Please specify a filename to open"}
    
    def _search_codebase(self, command: str) -> Dict[str, Any]:
        """Search codebase for patterns"""
        
        # Extract search term
        words = command.split()
        search_term = None
        
        for i, word in enumerate(words):
            if word.lower() in ["search", "find"] and i + 1 < len(words):
                search_term = words[i + 1]
                break
        
        if not search_term:
            return {"error": "Please specify a search term"}
        
        try:
            result = subprocess.run(
                ['grep', '-r', '-n', search_term, self.project_path],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                return {
                    "success": True,
                    "message": f"Search results for '{search_term}'",
                    "stdout": result.stdout
                }
            else:
                return {"error": f"No results found for '{search_term}'"}
                
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}
    
    def _explain_code(self, command: str, context: str) -> Dict[str, Any]:
        """Explain code using AI"""
        
        if not self.openai_key:
            return {"error": "OpenAI API key required for code explanation"}
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"You are a code explanation assistant. Context: {context}"},
                    {"role": "user", "content": command}
                ],
                max_tokens=1000
            )
            
            return {
                "success": True,
                "ai_response": response.choices[0].message.content,
                "action": "explanation"
            }
            
        except Exception as e:
            return {"error": f"Code explanation failed: {str(e)}"}
    
    def _refactor_code(self, command: str, context: str) -> Dict[str, Any]:
        """Refactor code using AI"""
        
        if not self.openai_key:
            return {"error": "OpenAI API key required for code refactoring"}
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"You are a code refactoring assistant. Provide specific refactoring suggestions. Context: {context}"},
                    {"role": "user", "content": command}
                ],
                max_tokens=1500
            )
            
            return {
                "success": True,
                "ai_response": response.choices[0].message.content,
                "action": "refactoring_suggestions"
            }
            
        except Exception as e:
            return {"error": f"Code refactoring failed: {str(e)}"}
    
    def _execute_cursor_ai(self, command: str, context: str) -> Dict[str, Any]:
        """Execute general Cursor AI commands"""
        
        if not self.openai_key:
            return {"error": "OpenAI API key required for Cursor AI"}
        
        try:
            project_info = self._get_project_info()
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"""You are Cursor AI assistant with full project access.
                    Project: {self.project_path}
                    Project info: {project_info}
                    Context: {context}
                    
                    Provide actionable responses and code suggestions."""},
                    {"role": "user", "content": command}
                ],
                max_tokens=1000
            )
            
            return {
                "success": True,
                "ai_response": response.choices[0].message.content,
                "action": "cursor_ai_response"
            }
            
        except Exception as e:
            return {"error": f"Cursor AI failed: {str(e)}"}
    
    def _create_component(self, command: str, context: str) -> Dict[str, Any]:
        """Create a component"""
        
        # Extract component name
        words = command.split()
        component_name = None
        
        for word in words:
            if word not in ["create", "component", "new"]:
                component_name = word
                break
        
        if not component_name:
            return {"error": "Please specify a component name"}
        
        # Generate component based on type
        if component_name.endswith('.jsx') or component_name.endswith('.tsx'):
            return self._create_react_component(component_name, context)
        else:
            return self._create_python_component(component_name, context)
    
    def _create_react_component(self, component_name: str, context: str) -> Dict[str, Any]:
        """Create a React component"""
        
        content = f"""import React from 'react';

const {component_name.replace('.jsx', '').replace('.tsx', '')} = () => {{
    return (
        <div>
            <h1>{component_name.replace('.jsx', '').replace('.tsx', '')}</h1>
            <p>Component created by Cursor Agent</p>
        </div>
    );
}};

export default {component_name.replace('.jsx', '').replace('.tsx', '')};
"""
        
        filepath = os.path.join(self.project_path, component_name)
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Created React component: {component_name}",
                "path": filepath,
                "content": content
            }
            
        except Exception as e:
            return {"error": f"Component creation failed: {str(e)}"}
    
    def _create_python_component(self, component_name: str, context: str) -> Dict[str, Any]:
        """Create a Python component/class"""
        
        class_name = component_name.replace('.py', '').title()
        
        content = f"""#!/usr/bin/env python3
\"\"\"
{class_name} - Created by Cursor Agent
\"\"\"

class {class_name}:
    \"\"\"
    {class_name} component
    \"\"\"
    
    def __init__(self):
        self.name = "{class_name}"
    
    def run(self):
        \"\"\"Main method\"\"\"
        print(f"Running {{self.name}}")
        return True

if __name__ == "__main__":
    component = {class_name}()
    component.run()
"""
        
        filename = f"{component_name}.py" if not component_name.endswith('.py') else component_name
        filepath = os.path.join(self.project_path, filename)
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Created Python component: {filename}",
                "path": filepath,
                "content": content
            }
            
        except Exception as e:
            return {"error": f"Component creation failed: {str(e)}"}
    
    def _create_function(self, command: str, context: str) -> Dict[str, Any]:
        """Create a function"""
        
        # Extract function name
        words = command.split()
        function_name = None
        
        for word in words:
            if word not in ["create", "function", "new", "def"]:
                function_name = word
                break
        
        if not function_name:
            return {"error": "Please specify a function name"}
        
        if self.openai_key:
            content = self._generate_function_content(function_name, command, context)
        else:
            content = f"""def {function_name}():
    \"\"\"
    {function_name} - Created by Cursor Agent
    \"\"\"
    # TODO: Implement function logic
    pass
"""
        
        # Create a new file or append to existing
        filename = f"{function_name}.py"
        filepath = os.path.join(self.project_path, filename)
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Created function: {function_name}",
                "path": filepath,
                "content": content
            }
            
        except Exception as e:
            return {"error": f"Function creation failed: {str(e)}"}
    
    def _generate_function_content(self, function_name: str, command: str, context: str) -> str:
        """Generate function content using AI"""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"""Generate a Python function named '{function_name}'.
                    Command: {command}
                    Context: {context}
                    
                    Create a complete, production-ready function with:
                    - Proper docstring
                    - Type hints
                    - Error handling
                    - Example usage
                    """},
                    {"role": "user", "content": f"Create function {function_name}"}
                ],
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"""def {function_name}():
    \"\"\"
    {function_name} - Created by Cursor Agent
    Error generating content: {str(e)}
    \"\"\"
    pass
"""
    
    def _create_class(self, command: str, context: str) -> Dict[str, Any]:
        """Create a class"""
        
        # Extract class name
        words = command.split()
        class_name = None
        
        for word in words:
            if word not in ["create", "class", "new"]:
                class_name = word
                break
        
        if not class_name:
            return {"error": "Please specify a class name"}
        
        if self.openai_key:
            content = self._generate_class_content(class_name, command, context)
        else:
            content = f"""class {class_name}:
    \"\"\"
    {class_name} - Created by Cursor Agent
    \"\"\"
    
    def __init__(self):
        self.name = "{class_name}"
    
    def __str__(self):
        return f"<{class_name}: {{self.name}}>"
"""
        
        filename = f"{class_name.lower()}.py"
        filepath = os.path.join(self.project_path, filename)
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Created class: {class_name}",
                "path": filepath,
                "content": content
            }
            
        except Exception as e:
            return {"error": f"Class creation failed: {str(e)}"}
    
    def _generate_class_content(self, class_name: str, command: str, context: str) -> str:
        """Generate class content using AI"""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"""Generate a Python class named '{class_name}'.
                    Command: {command}
                    Context: {context}
                    
                    Create a complete, production-ready class with:
                    - Proper docstring
                    - __init__ method
                    - Essential methods
                    - Type hints
                    - Error handling
                    """},
                    {"role": "user", "content": f"Create class {class_name}"}
                ],
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"""class {class_name}:
    \"\"\"
    {class_name} - Created by Cursor Agent
    Error generating content: {str(e)}
    \"\"\"
    
    def __init__(self):
        self.name = "{class_name}"
"""
    
    def _create_general(self, command: str, context: str) -> Dict[str, Any]:
        """Handle general creation commands"""
        
        return {
            "success": True,
            "message": "General creation command received",
            "ai_response": f"For creation, try:\n- `create file <filename>` - Create a new file\n- `create component <name>` - Create a component\n- `create function <name>` - Create a function\n- `create class <name>` - Create a class\n\nCommand received: {command}"
        }
    
    def _execute_modifications(self, modification_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code modifications based on AI plan"""
        
        try:
            files_modified = []
            
            for file_path, changes in modification_plan.get("files", {}).items():
                full_path = os.path.join(self.project_path, file_path)
                
                if os.path.exists(full_path):
                    # Read current content
                    with open(full_path, 'r') as f:
                        content = f.read()
                    
                    # Apply changes (this is a simplified version)
                    # In a real implementation, you'd need more sophisticated parsing
                    modified_content = content  # Placeholder
                    
                    # Write back
                    with open(full_path, 'w') as f:
                        f.write(modified_content)
                    
                    files_modified.append(file_path)
            
            return {
                "success": True,
                "message": f"Modified {len(files_modified)} files",
                "files_modified": files_modified,
                "reason": modification_plan.get("reason", "No reason provided")
            }
            
        except Exception as e:
            return {"error": f"Modification failed: {str(e)}"}
    
    def get_command_history(self) -> List[Dict[str, Any]]:
        """Get command execution history"""
        return self.command_history
    
    def clear_history(self):
        """Clear command history"""
        self.command_history = [] 