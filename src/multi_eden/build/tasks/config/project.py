"""
Project ID management tasks.
"""
from pathlib import Path
from invoke import task


@task(help={
    'env_name': 'Environment name (e.g., dev, prod, integration-test)',
    'project_id': 'Google Cloud Project ID'
})
def register_project(ctx, env_name, project_id):
    """
    Register a project ID for an environment in .projects file.
    
    Args:
        env_name: Environment name (e.g., 'dev', 'prod', 'integration-test')
        project_id: Google Cloud Project ID
    """
    projects_file = Path(".projects")
    
    # Create .projects file if it doesn't exist
    if not projects_file.exists():
        projects_file.write_text("# Project IDs for different environments\n")
        print(f"✅ Created .projects file")
    
    # Read existing content
    lines = projects_file.read_text().splitlines()
    
    # Check if environment already exists
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{env_name}="):
            lines[i] = f"{env_name}={project_id}"
            updated = True
            break
    
    # Add new environment if not found
    if not updated:
        lines.append(f"{env_name}={project_id}")
    
    # Write back to file
    projects_file.write_text("\n".join(lines) + "\n")
    print(f"✅ Registered {env_name}={project_id}")
    
    # Ensure .gitignore includes .projects
    gitignore_file = Path(".gitignore")
    if gitignore_file.exists():
        gitignore_content = gitignore_file.read_text()
        if ".projects" not in gitignore_content:
            gitignore_file.write_text(gitignore_content + "\n# Project IDs (sensitive)\n.projects\n")
            print("✅ Added .projects to .gitignore")
    else:
        gitignore_file.write_text("# Project IDs (sensitive)\n.projects\n")
        print("✅ Created .gitignore with .projects entry")